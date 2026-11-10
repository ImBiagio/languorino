from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import formats
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recipes.models import Category
from apps.recipes.services import match_ingredient

from .models import ShoppingItem, ShoppingList
from .serializers import (
    ShoppingItemSerializer,
    ShoppingListCreateSerializer,
    ShoppingListDetailSerializer,
    ShoppingListSerializer,
)
from .services import fill_from_plan


def lists_of(user):
    # Le voci "ce l'ho gia'" non contano: non si comprano.
    to_buy = Q(items__in_pantry=False)
    return ShoppingList.objects.filter(owner=user).annotate(
        item_count=Count("items", filter=to_buy),
        checked_count=Count("items", filter=to_buy & Q(items__checked=True)),
    )


def _detail(request, shopping_list: ShoppingList, code=status.HTTP_200_OK) -> Response:
    shopping_list = lists_of(request.user).prefetch_related("items").get(pk=shopping_list.pk)
    return Response(ShoppingListDetailSerializer(shopping_list).data, status=code)


class ShoppingListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ShoppingListSerializer(many=True)})
    def get(self, request):
        lists = lists_of(request.user)
        if status_ := request.query_params.get("status"):
            lists = lists.filter(status=status_)
        return Response(ShoppingListSerializer(lists[:30], many=True).data)

    @extend_schema(
        request=ShoppingListCreateSerializer, responses={201: ShoppingListDetailSerializer}
    )
    def post(self, request):
        data = ShoppingListCreateSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        values = data.validated_data
        title = " ".join((values.get("title") or "").split())
        if not title:
            if values["plan"]:
                # In italiano i mesi vanno minuscoli ("16 novembre"); Django li
                # scrive con la maiuscola. In inglese restano come sono.
                def day(value):
                    text = formats.date_format(value, "j F")
                    return text.lower() if (get_language() or "it").startswith("it") else text

                title = _("Spesa dal %(start)s al %(end)s") % {
                    "start": day(values["date_from"]),
                    "end": day(values["date_to"]),
                }
            else:
                title = _("Spesa")
        with transaction.atomic():
            shopping_list = ShoppingList.objects.create(
                owner=request.user,
                title=title[:120],
                plan=values["plan"],
                date_from=values.get("date_from"),
                date_to=values.get("date_to"),
            )
            fill_from_plan(shopping_list)
        return _detail(request, shopping_list, status.HTTP_201_CREATED)


class ShoppingListDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ShoppingListDetailSerializer})
    def get(self, request, pk):
        return _detail(request, get_object_or_404(lists_of(request.user), pk=pk))

    @extend_schema(request=ShoppingListSerializer, responses={200: ShoppingListDetailSerializer})
    def patch(self, request, pk):
        shopping_list = get_object_or_404(lists_of(request.user), pk=pk)
        serializer = ShoppingListSerializer(shopping_list, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return _detail(request, shopping_list)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        get_object_or_404(lists_of(request.user), pk=pk).delete(hard=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShoppingListRegenerateView(APIView):
    """Ricalcola dal piano (dopo un cambio di pasti), senza toccare le voci a mano."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: ShoppingListDetailSerializer})
    def post(self, request, pk):
        shopping_list = get_object_or_404(lists_of(request.user), pk=pk)
        if shopping_list.plan is None:
            raise serializers.ValidationError({"detail": _("Questa lista non viene da un piano.")})
        fill_from_plan(shopping_list)
        return _detail(request, shopping_list)


class ShoppingItemListView(APIView):
    """Aggiungere una voce a mano: il reparto si prende dal catalogo se il nome c'e'."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShoppingItemSerializer, responses={201: ShoppingItemSerializer})
    def post(self, request, pk):
        shopping_list = get_object_or_404(lists_of(request.user), pk=pk)
        serializer = ShoppingItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ingredient = match_ingredient(serializer.validated_data["label"], request.user)
        last = shopping_list.items.order_by("-position").values_list("position", flat=True).first()
        item = serializer.save(
            shopping_list=shopping_list,
            ingredient=ingredient,
            category=ingredient.category if ingredient else Category.OTHER,
            manual=True,
            position=(last or 0) + 1,
        )
        return Response(ShoppingItemSerializer(item).data, status=status.HTTP_201_CREATED)


class ShoppingItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _item(self, request, pk, item_id) -> ShoppingItem:
        return get_object_or_404(
            ShoppingItem, pk=item_id, shopping_list_id=pk, shopping_list__owner=request.user
        )

    @extend_schema(request=ShoppingItemSerializer, responses={200: ShoppingItemSerializer})
    def patch(self, request, pk, item_id):
        item = self._item(request, pk, item_id)
        serializer = ShoppingItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # Spuntare non e' "modificare": cambiare nome o quantita' si'.
        if {"label", "quantity", "unit"} & set(serializer.validated_data):
            serializer.validated_data["edited"] = True
        serializer.save()
        return Response(serializer.data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk, item_id):
        self._item(request, pk, item_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
