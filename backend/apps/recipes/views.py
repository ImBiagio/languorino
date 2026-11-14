from __future__ import annotations

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.client import is_enabled
from apps.jobs.files import PDF, sniff
from apps.jobs.models import Job
from apps.jobs.serializers import JobSerializer
from apps.jobs.views import enqueue_job

from .books import BookRejected, page_count
from .images import ImageRejected, clear_image, images_today, set_image
from .matching import normalize, variants
from .models import Recipe, RecipeBook, RecipeIngredient, Tag
from .serializers import (
    IngredientSerializer,
    RecipeBookSerializer,
    RecipeListSerializer,
    RecipeSerializer,
    SharedRecipeSerializer,
    TagSerializer,
)
from .services import visible_ingredients
from .sharing import copy_recipe, share, unshare
from .tasks import enqueue_book, start_book_images

SEARCH_LIMIT = 12


class IngredientSearchView(APIView):
    """Suggerimenti mentre si scrive un ingrediente nel form."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[OpenApiParameter("q", str)],
        responses={200: IngredientSerializer(many=True)},
    )
    def get(self, request):
        query = normalize(request.query_params.get("q", ""))
        if len(query) < 2:
            return Response([])
        exact = set(variants(query))
        candidates = list(
            visible_ingredients(request.user).filter(search_text__icontains=query)[:80]
        )

        # Prima chi corrisponde esattamente, poi chi ha una chiave che inizia
        # con la ricerca, poi il resto; a parita' i nomi piu' corti.
        def rank(ingredient):
            if exact & set(ingredient.keys):
                group = 0
            elif any(key.startswith(query) for key in ingredient.keys):
                group = 1
            else:
                group = 2
            return (group, len(ingredient.name), ingredient.name)

        candidates.sort(key=rank)
        return Response(IngredientSerializer(candidates[:SEARCH_LIMIT], many=True).data)


def recipes_of(user):
    return (
        Recipe.objects.filter(owner=user)
        .select_related("book")
        .prefetch_related(
            "tags",
            Prefetch(
                "ingredients",
                queryset=RecipeIngredient.objects.select_related("ingredient").order_by("position"),
            ),
        )
    )


class RecipeListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    # I filtri li applica get_queryset: niente filtri automatici di django-filter.
    filter_backends: list = []

    def get_serializer_class(self):
        return RecipeSerializer if self.request.method == "POST" else RecipeListSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="titolo, ingrediente o tag"),
            OpenApiParameter("tag", str, many=True, description="tutti i tag indicati"),
            OpenApiParameter("slot", str),
            OpenApiParameter("max_minutes", int),
            OpenApiParameter("difficulty", str),
            OpenApiParameter("in_cookbook", bool),
            OpenApiParameter("book", str, description="solo le ricette di un ricettario PDF"),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        params = self.request.query_params
        recipes = recipes_of(self.request.user)
        if book := params.get("book"):
            # Un ricettario PDF mostra tutte le sue ricette, salvate o no.
            recipes = recipes.filter(book_id=book)
        else:
            # Ricette dei PDF e del piano mai salvate non sono nel ricettario.
            recipes = recipes.filter(in_cookbook=params.get("in_cookbook", "true") != "false")
        if query := " ".join(params.get("q", "").split()):
            key = normalize(query)
            recipes = recipes.filter(
                Q(title__icontains=query)
                | Q(ingredients__ingredient__search_text__icontains=key)
                | Q(tags__name__icontains=query)
            )
        for tag in params.getlist("tag"):
            recipes = recipes.filter(tags__name__iexact=tag)
        if slot := params.get("slot"):
            recipes = recipes.filter(meal_slots__contains=[slot])
        if difficulty := params.get("difficulty"):
            recipes = recipes.filter(difficulty=difficulty)
        if (minutes := params.get("max_minutes", "")).isdigit():
            recipes = recipes.alias(total=F("prep_minutes") + F("cook_minutes")).filter(
                total__lte=int(minutes)
            )
        return recipes.distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class RecipeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RecipeSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_queryset(self):
        return recipes_of(self.request.user)

    def perform_update(self, serializer):
        serializer.save()
        # Le relazioni appena riscritte non sono nella cache del prefetch.
        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)


class TagListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: TagSerializer(many=True)})
    def get(self, request):
        alive = Q(recipes__deleted_at__isnull=True, recipes__in_cookbook=True)
        tags = Tag.objects.filter(owner=request.user).annotate(
            recipe_count=Count("recipes", filter=alive)
        )
        return Response(TagSerializer(tags, many=True).data)


class TagDetailView(APIView):
    """Togliere un tag lo stacca da tutte le ricette: le ricette restano."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        deleted = Tag.objects.filter(owner=request.user, pk=pk).first()
        if deleted is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        deleted.delete(hard=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipeSaveView(APIView):
    """Una ricetta di un ricettario PDF entra nel ricettario dell'utente."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: RecipeSerializer})
    def post(self, request, pk):
        recipe = get_object_or_404(recipes_of(request.user), pk=pk)
        recipe.in_cookbook = True
        recipe.status = Recipe.Status.CONFIRMED
        recipe.save(update_fields=["in_cookbook", "status", "updated_at"])
        return Response(RecipeSerializer(recipe, context={"request": request}).data)


def books_of(user):
    alive = Q(recipes__deleted_at__isnull=True)
    return RecipeBook.objects.filter(owner=user).annotate(
        recipe_count=Count("recipes", filter=alive),
        saved_count=Count("recipes", filter=alive & Q(recipes__in_cookbook=True)),
        without_image=Count("recipes", filter=alive & Q(recipes__image="")),
    )


class RecipeBookListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def get_throttles(self):
        self.throttle_scope = "ai" if self.request.method == "POST" else None
        return super().get_throttles()

    @extend_schema(responses={200: RecipeBookSerializer(many=True)})
    def get(self, request):
        return Response(RecipeBookSerializer(books_of(request.user), many=True).data)

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                    "title": {"type": "string"},
                },
            }
        },
        responses={202: RecipeBookSerializer},
    )
    def post(self, request):
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": _("Carica un PDF.")})
        data = upload.read()
        if sniff(data[:16]) != PDF:
            raise serializers.ValidationError({"file": _("Il file non è un PDF.")})
        if len(data) > settings.BOOK_MAX_BYTES:
            raise serializers.ValidationError(
                {
                    "file": _("Il PDF è troppo grande (massimo %(mb)d MB).")
                    % {"mb": settings.BOOK_MAX_BYTES // (1024 * 1024)}
                }
            )
        try:
            pages = page_count(data)
        except BookRejected as exc:
            raise serializers.ValidationError({"file": str(exc)}) from exc
        if not pages or pages > settings.BOOK_MAX_PAGES:
            raise serializers.ValidationError(
                {
                    "file": _("Il PDF deve avere da 1 a %(n)d pagine.")
                    % {"n": settings.BOOK_MAX_PAGES}
                }
            )
        name = (upload.name or "")[:200]
        default_title = name.rsplit(".", 1)[0].replace("_", " ").strip() or _("Ricettario")
        title = " ".join((request.data.get("title") or default_title).split())[:120]
        with transaction.atomic():
            book = RecipeBook(
                owner=request.user,
                title=title,
                original_name=name,
                size=len(data),
                page_count=pages,
                language=(get_language() or "it")[:2],
            )
            book.file.save("upload.pdf", ContentFile(data), save=False)
            book.save()
            enqueue_book(book)
        return Response(
            RecipeBookSerializer(books_of(request.user).get(pk=book.pk)).data,
            status=status.HTTP_202_ACCEPTED,
        )


class RecipeBookDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: RecipeBookSerializer})
    def get(self, request, pk):
        return Response(RecipeBookSerializer(get_object_or_404(books_of(request.user), pk=pk)).data)

    @extend_schema(request=RecipeBookSerializer, responses={200: RecipeBookSerializer})
    def patch(self, request, pk):
        book = get_object_or_404(books_of(request.user), pk=pk)
        serializer = RecipeBookSerializer(book, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(RecipeBookSerializer(books_of(request.user).get(pk=pk)).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        """Via il PDF e le sue ricette non salvate; quelle salvate restano."""
        book = get_object_or_404(RecipeBook, pk=pk, owner=request.user)
        with transaction.atomic():
            for recipe in book.recipes.filter(in_cookbook=False):
                recipe.delete(hard=True)
            book.file.delete(save=False)
            book.delete(hard=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipeBookRetryView(APIView):
    """Riprende la lettura dalla pagina a cui si era fermata."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "ai"

    @extend_schema(request=None, responses={202: RecipeBookSerializer})
    def post(self, request, pk):
        book = get_object_or_404(RecipeBook, pk=pk, owner=request.user)
        if book.status != RecipeBook.Status.FAILED:
            raise serializers.ValidationError(
                {"detail": _("Si può riprendere solo una lettura interrotta.")}
            )
        with transaction.atomic():
            book.status = RecipeBook.Status.QUEUED
            book.error = ""
            book.save(update_fields=["status", "error", "updated_at"])
            enqueue_book(book)
        return Response(
            RecipeBookSerializer(books_of(request.user).get(pk=pk)).data,
            status=status.HTTP_202_ACCEPTED,
        )


# --- immagini (ADR 0011) ------------------------------------------------------------------

PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


class RecipeImageView(APIView):
    """Foto vera della ricetta (POST multipart ``file``) o via l'immagine (DELETE)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
            }
        },
        responses={200: RecipeSerializer},
    )
    def post(self, request, pk):
        recipe = get_object_or_404(recipes_of(request.user), pk=pk)
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": _("Scegli una foto.")})
        data = upload.read()
        if sniff(data[:16]) not in PHOTO_TYPES:
            raise serializers.ValidationError(
                {"file": _("Serve una foto JPEG, PNG o WebP (le HEIC dell'iPhone non ancora).")}
            )
        if len(data) > settings.JOB_MAX_IMAGE_BYTES:
            raise serializers.ValidationError(
                {
                    "file": _("Foto troppo grande (massimo %(mb)d MB).")
                    % {"mb": settings.JOB_MAX_IMAGE_BYTES // (1024 * 1024)}
                }
            )
        try:
            set_image(recipe, data, Recipe.ImageSource.PHOTO)
        except ImageRejected as exc:
            raise serializers.ValidationError({"file": str(exc)}) from exc
        recipe = recipes_of(request.user).get(pk=pk)
        return Response(RecipeSerializer(recipe, context={"request": request}).data)

    @extend_schema(responses={200: RecipeSerializer})
    def delete(self, request, pk):
        recipe = get_object_or_404(recipes_of(request.user), pk=pk)
        clear_image(recipe)
        recipe = recipes_of(request.user).get(pk=pk)
        return Response(RecipeSerializer(recipe, context={"request": request}).data)


class RecipeImageDrawView(APIView):
    """Gemini disegna l'immagine della ricetta, in un job (ADR 0011)."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "ai"

    @extend_schema(request=None, responses={202: JobSerializer})
    def post(self, request, pk):
        recipe = get_object_or_404(recipes_of(request.user), pk=pk)
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if recipe.image_source == Recipe.ImageSource.PHOTO:
            raise serializers.ValidationError(
                {"detail": _("Ha già una foto vera: toglila prima di farne disegnare una.")}
            )
        if images_today(request.user) >= settings.AI_IMAGES_PER_DAY:
            raise serializers.ValidationError(
                {
                    "detail": _(
                        "Per oggi hai finito le immagini (%(n)d al giorno). Riprova domani."
                    )
                    % {"n": settings.AI_IMAGES_PER_DAY}
                }
            )
        with transaction.atomic():
            job = Job.objects.create(
                owner=request.user,
                kind=Job.Kind.RECIPE_IMAGE,
                input={"recipe": str(recipe.id), "language": (get_language() or "it")[:2]},
            )
            enqueue_job(job)
        job.refresh_from_db()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class RecipeNutritionView(APIView):
    """Calorie e macro stimati da Gemini dagli ingredienti, in un job (ADR 0018)."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "ai"

    @extend_schema(request=None, responses={202: JobSerializer})
    def post(self, request, pk):
        recipe = get_object_or_404(recipes_of(request.user), pk=pk)
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not recipe.ingredients.exists():
            raise serializers.ValidationError(
                {"detail": _("Senza ingredienti non posso stimare calorie e macro.")}
            )
        with transaction.atomic():
            job = Job.objects.create(
                owner=request.user,
                kind=Job.Kind.RECIPE_NUTRITION,
                input={"recipe": str(recipe.id), "language": (get_language() or "it")[:2]},
            )
            enqueue_job(job)
        job.refresh_from_db()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


# --- condivisione (ADR 0012) ----------------------------------------------------------------


class RecipeShareView(APIView):
    """Crea il link (POST, ``renew`` per un link nuovo che spegne il vecchio) o lo spegne."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: RecipeSerializer})
    def post(self, request, pk):
        recipe = get_object_or_404(recipes_of(request.user), pk=pk)
        share(recipe, renew=bool(request.data.get("renew")))
        return Response(RecipeSerializer(recipe, context={"request": request}).data)

    @extend_schema(responses={200: RecipeSerializer})
    def delete(self, request, pk):
        recipe = get_object_or_404(recipes_of(request.user), pk=pk)
        unshare(recipe)
        return Response(RecipeSerializer(recipe, context={"request": request}).data)


def shared_recipe(token: str) -> Recipe:
    return get_object_or_404(
        Recipe.objects.select_related("owner").prefetch_related(
            "tags",
            Prefetch(
                "ingredients",
                queryset=RecipeIngredient.objects.select_related("ingredient").order_by("position"),
            ),
        ),
        share_token=token,
    )


class SharedRecipeView(APIView):
    """La pagina pubblica: chiunque abbia il link, anche senza account."""

    permission_classes = [AllowAny]
    throttle_scope = "public"

    @extend_schema(responses={200: SharedRecipeSerializer})
    def get(self, request, token):
        recipe = shared_recipe(token)
        return Response(SharedRecipeSerializer(recipe, context={"request": request}).data)


class SharedRecipeCopyView(APIView):
    """ "Copia nel mio ricettario": serve l'account."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "public"

    @extend_schema(request=None, responses={201: RecipeSerializer})
    def post(self, request, token):
        recipe = shared_recipe(token)
        if recipe.owner_id == request.user.id:
            raise serializers.ValidationError({"detail": _("È già nel tuo ricettario.")})
        copy = copy_recipe(recipe, request.user)
        copy = recipes_of(request.user).get(pk=copy.pk)
        return Response(
            RecipeSerializer(copy, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class RecipeBookImagesView(APIView):
    """Cerca le foto delle ricette nel PDF e fa disegnare le altre (ADR 0015).
    Per i ricettari letti prima che lo si facesse da solo, o per riprovare."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "ai"

    @extend_schema(request=None, responses={202: RecipeBookSerializer})
    def post(self, request, pk):
        book = get_object_or_404(books_of(request.user), pk=pk)
        if not is_enabled():
            return Response(
                {"detail": _("La lettura con l'intelligenza artificiale non è configurata.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if book.status != RecipeBook.Status.READY:
            raise serializers.ValidationError(
                {"detail": _("Prima finisco di leggere il ricettario.")}
            )
        if book.images_status in (
            RecipeBook.ImagesStatus.SEARCHING,
            RecipeBook.ImagesStatus.DRAWING,
        ):
            raise serializers.ValidationError({"detail": _("Ci sto già lavorando.")})
        with transaction.atomic():
            start_book_images(book)
        book = books_of(request.user).get(pk=pk)
        return Response(RecipeBookSerializer(book).data, status=status.HTTP_202_ACCEPTED)
