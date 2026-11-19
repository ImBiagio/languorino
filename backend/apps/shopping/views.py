from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import formats
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.plans.models import PlanShare
from apps.recipes.models import Category
from apps.recipes.services import match_ingredient

from .models import RecurringItem, ShoppingItem, ShoppingList
from .recurring import suggestions
from .serializers import (
    RecurringItemSerializer,
    ShoppingItemSerializer,
    ShoppingListCreateSerializer,
    ShoppingListDetailSerializer,
    ShoppingListSerializer,
)
from .services import fill_from_plan


def lists_of(user):
    """Le liste che ``user`` usa: le sue e quelle di chi gli fa vedere il
    piano (ADR 0025). La spesa e' della casa: chi vede il piano la fa insieme.
    Con una sottoquery e non con un join: un join coi PlanShare moltiplicherebbe
    i conteggi delle voci per le persone con cui si condivide."""
    sharing = PlanShare.objects.filter(viewer=user).values("owner")
    # Le voci "ce l'ho gia'" non contano: non si comprano.
    to_buy = Q(items__in_pantry=False)
    lists = ShoppingList.objects.filter(Q(owner=user) | Q(owner__in=sharing))
    return lists.select_related("owner").annotate(
        item_count=Count("items", filter=to_buy),
        checked_count=Count("items", filter=to_buy & Q(items__checked=True)),
    )


def _detail(request, shopping_list: ShoppingList, code=status.HTTP_200_OK) -> Response:
    shopping_list = lists_of(request.user).prefetch_related("items").get(pk=shopping_list.pk)
    data = ShoppingListDetailSerializer(shopping_list, context={"request": request}).data
    return Response(data, status=code)


class ShoppingListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ShoppingListSerializer(many=True)})
    def get(self, request):
        lists = lists_of(request.user)
        if status_ := request.query_params.get("status"):
            lists = lists.filter(status=status_)
        data = ShoppingListSerializer(lists[:30], many=True, context={"request": request}).data
        return Response(data)

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
                include_recurring=values["include_recurring"],
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
        serializer = ShoppingListSerializer(
            shopping_list, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        recurring = serializer.validated_data.get("include_recurring")
        with transaction.atomic():
            changed = recurring is not None and recurring != shopping_list.include_recurring
            serializer.save()
            if changed:
                # Accesi o spenti i ricorrenti: si aggiungono o si tolgono subito.
                fill_from_plan(shopping_list)
        return _detail(request, shopping_list)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        # Eliminare resta di chi ha fatto la lista: chi la condivide la usa.
        shopping_list = get_object_or_404(lists_of(request.user), pk=pk)
        if shopping_list.owner_id != request.user.id:
            raise PermissionDenied(_("Solo chi ha fatto la lista può eliminarla."))
        shopping_list.delete(hard=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShoppingListRegenerateView(APIView):
    """Ricalcola dal piano (dopo un cambio di pasti) e dai ricorrenti, senza
    toccare le voci a mano."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: ShoppingListDetailSerializer})
    def post(self, request, pk):
        shopping_list = get_object_or_404(lists_of(request.user), pk=pk)
        if shopping_list.plan is None and not shopping_list.include_recurring:
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
        # Il catalogo di chi ha fatto la lista: anche se aggiunge chi la condivide.
        ingredient = match_ingredient(serializer.validated_data["label"], shopping_list.owner)
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
        shopping_list = get_object_or_404(lists_of(request.user), pk=pk)
        return get_object_or_404(ShoppingItem, pk=item_id, shopping_list=shopping_list)

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


# --- ricorrenti (ADR 0024) ---------------------------------------------------------------


def _recurring_save(serializer, user, **extra):
    """Il ricorrente col suo ingrediente del catalogo, se il nome c'e'."""
    label = serializer.validated_data.get("label")
    if label is not None:
        extra["ingredient"] = match_ingredient(label, user)
    return serializer.save(**extra)


class RecurringItemListView(APIView):
    """I ricorrenti dell'utente; si aggiungono uno alla volta o tutti insieme
    (i suggerimenti scelti dal piano alimentare)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: RecurringItemSerializer(many=True)})
    def get(self, request):
        items = RecurringItem.objects.filter(owner=request.user)
        return Response(RecurringItemSerializer(items, many=True).data)

    @extend_schema(
        request=RecurringItemSerializer(many=True),
        responses={201: RecurringItemSerializer(many=True)},
    )
    def post(self, request):
        many = isinstance(request.data, list)
        rows = request.data if many else [request.data]
        serializers_ = [RecurringItemSerializer(data=row) for row in rows[:50]]
        for serializer in serializers_:
            serializer.is_valid(raise_exception=True)
        last = (
            RecurringItem.objects.filter(owner=request.user)
            .order_by("-position")
            .values_list("position", flat=True)
            .first()
            or 0
        )
        with transaction.atomic():
            items = [
                _recurring_save(serializer, request.user, owner=request.user, position=last + n)
                for n, serializer in enumerate(serializers_, start=1)
            ]
        data = RecurringItemSerializer(items, many=True).data
        return Response(data if many else data[0], status=status.HTTP_201_CREATED)


class RecurringSuggestionsView(APIView):
    """Cosa proporre come ricorrente: gli alimenti dei pasti del piano
    alimentare che la preparazione non prepara (colazione, merende)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response(suggestions(request.user))


class RecurringItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=RecurringItemSerializer, responses={200: RecurringItemSerializer})
    def patch(self, request, item_id):
        item = get_object_or_404(RecurringItem, pk=item_id, owner=request.user)
        serializer = RecurringItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        _recurring_save(serializer, request.user)
        return Response(serializer.data)

    @extend_schema(responses={204: None})
    def delete(self, request, item_id):
        get_object_or_404(RecurringItem, pk=item_id, owner=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
