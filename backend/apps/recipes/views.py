from __future__ import annotations

from django.db.models import Count, F, Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .matching import normalize, variants
from .models import Recipe, RecipeIngredient, Tag
from .serializers import IngredientSerializer, RecipeListSerializer, RecipeSerializer, TagSerializer
from .services import visible_ingredients

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
    return Recipe.objects.filter(owner=user).prefetch_related(
        "tags",
        Prefetch(
            "ingredients",
            queryset=RecipeIngredient.objects.select_related("ingredient").order_by("position"),
        ),
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
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        params = self.request.query_params
        recipes = recipes_of(self.request.user)
        # Le ricette scritte dal piano e mai salvate non sono nel ricettario.
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
