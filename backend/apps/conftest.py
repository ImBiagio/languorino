from __future__ import annotations

import factory
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"utente{n}@templatino.test")
    display_name = factory.Sequence(lambda n: f"Utente {n}")
    is_active = True

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or "password-di-prova")
        if create:
            obj.save()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def other_user(db):
    return UserFactory()



@pytest.fixture
def api(db):
    def _client(as_user=None):
        client = APIClient()
        if as_user is not None:
            client.force_authenticate(user=as_user)
        return client

    return _client
