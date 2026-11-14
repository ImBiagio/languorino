"""Profili pubblici, voti e commenti (ADR 0017)."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recipes.models import RecipeIngredient
from apps.recipes.serializers import RecipeListSerializer
from apps.recipes.views import shared_recipe

from .models import Comment, CommentImage, Rating
from .profiles import public_recipes
from .serializers import CommentSerializer
from .services import add_comment, can_delete, delete_comment, rate, rating_summary

MAX_THREADS = 200


def _public_handles(user_ids) -> dict:
    """Gli autori con il profilo pubblico (almeno una ricetta pubblica)."""
    from apps.recipes.models import Recipe

    owners = set(
        Recipe.objects.filter(
            owner_id__in=set(user_ids),
            visibility=Recipe.Visibility.PUBLIC,
            share_token__isnull=False,
            in_cookbook=True,
            owner__handle__isnull=False,
        ).values_list("owner_id", "owner__handle")
    )
    return dict(owners)


def comments_payload(recipe, request) -> list[dict]:
    """I fili dei commenti, dal piu' recente; le risposte in ordine di arrivo.
    Un commento eliminato resta solo se ha risposte vive."""
    queryset = (
        Comment.all_objects.filter(recipe=recipe)
        .select_related("author", "recipe")
        .prefetch_related(Prefetch("images", queryset=CommentImage.objects.order_by("position")))
        .order_by("created_at")
    )
    roots, replies = [], defaultdict(list)
    for comment in queryset:
        if comment.parent_id is None:
            roots.append(comment)
        elif not comment.is_deleted:
            replies[comment.parent_id].append(comment)
    roots = [root for root in roots if not root.is_deleted or replies.get(root.id)]
    roots = list(reversed(roots))[:MAX_THREADS]
    authors = {comment.author_id for comment in roots} | {
        reply.author_id for items in replies.values() for reply in items
    }
    stars = dict(
        Rating.objects.filter(recipe=recipe, user_id__in=authors).values_list("user_id", "stars")
    )
    context = {
        "request": request,
        "replies": replies,
        "stars": stars,
        "public_handles": _public_handles(authors),
    }
    return CommentSerializer(roots, many=True, context=context).data


class PublicProfileView(APIView):
    """``/u/<handle>``: nome e ricette pubbliche. Senza ricette pubbliche il
    profilo non esiste (404), anche se l'indirizzo c'e'."""

    permission_classes = [AllowAny]
    throttle_scope = "public"

    def get(self, request, handle):
        user = get_object_or_404(get_user_model(), handle=handle.lower(), is_active=True)
        recipes = (
            public_recipes(user)
            .select_related("book")
            .prefetch_related(
                "tags",
                Prefetch(
                    "ingredients",
                    queryset=RecipeIngredient.objects.select_related("ingredient"),
                ),
            )
            .annotate(rating_average=Avg("ratings__stars"), rating_count=Count("ratings"))
            .order_by("-created_at")
        )
        if not recipes:
            raise Http404
        # Card senza avvisi dal profilo di chi guarda: e' la pagina di un altro.
        cards = RecipeListSerializer(
            recipes, many=True, context={"preference_index": _NoWarnings()}
        )
        data = []
        for recipe, card in zip(recipes, cards.data, strict=True):
            card = {key: value for key, value in card.items() if key != "warnings"}
            card["share_token"] = recipe.share_token
            card["rating_average"] = (
                round(float(recipe.rating_average), 1) if recipe.rating_average else None
            )
            card["rating_count"] = recipe.rating_count
            data.append(card)
        return Response(
            {
                "handle": user.handle,
                "name": user.display_name,
                "since": user.date_joined.date(),
                "is_me": request.user.is_authenticated and request.user.pk == user.pk,
                "recipes": data,
            }
        )


class _NoWarnings:
    def warnings(self, recipe, allergens):
        return []


class RecipeCommentsView(APIView):
    """GET i commenti di una ricetta condivisa (anche senza account); POST un
    commento o una risposta (multipart ``text``, ``parent``, ``images``)."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get_throttles(self):
        self.throttle_scope = "comments" if self.request.method == "POST" else "public"
        return super().get_throttles()

    def get(self, request, token):
        recipe = shared_recipe(token)
        return Response(comments_payload(recipe, request))

    @extend_schema(request=None, responses={201: CommentSerializer(many=True)})
    def post(self, request, token):
        recipe = shared_recipe(token)
        add_comment(
            recipe,
            request.user,
            request.data.get("text", ""),
            parent_id=request.data.get("parent") or None,
            uploads=request.FILES.getlist("images"),
        )
        return Response(comments_payload(recipe, request), status=status.HTTP_201_CREATED)


class CommentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        comment = get_object_or_404(Comment.objects.select_related("recipe"), pk=pk)
        if not can_delete(comment, request.user):
            raise Http404
        delete_comment(comment)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipeRatingView(APIView):
    """PUT ``{stars}`` da 1 a 5, DELETE per togliere il voto."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "public"

    def put(self, request, token):
        recipe = shared_recipe(token)
        try:
            stars = int(request.data.get("stars"))
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError({"stars": "1-5"}) from exc
        rate(recipe, request.user, stars)
        return Response(rating_summary(recipe, request.user))

    def delete(self, request, token):
        recipe = shared_recipe(token)
        Rating.objects.filter(recipe=recipe, user=request.user).delete()
        return Response(rating_summary(recipe, request.user))
