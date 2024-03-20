import uuid

import pytest
from faker import Faker

import grannymail.db.repositories as repos
import grannymail.domain.models as m
from grannymail.services.unit_of_work import SupabaseUnitOfWork


class TestRepositoryBase:
    def test_add_successfully_returns_added_entity(self):
        # Arrange
        with pytest.raises(TypeError):
            repos.RepositoryBase()


def get_time():
    return "2024-01-26T17:17:17.123+00:00"


class TestUserRepository:
    def test_init(self):
        # Arrange
        client = SupabaseUnitOfWork().create_client()
        user_repo = repos.UserRepository(client)

        assert user_repo.__table__ == "users"
        assert user_repo.__id_col__ == "user_id"
        assert user_repo.__data_type__ == m.User

    def test_add_user(self):
        # Arrange
        client = SupabaseUnitOfWork().create_client()
        user_repo = repos.UserRepository(client)

        # Act
        user_id = str(uuid.uuid4())
        user = user_repo.add(m.User(user_id=user_id, created_at=get_time()))

        # Assert
        assert user == m.User(user_id=user_id, created_at=get_time())

    def test_fail_add_user_duplicate_email(self):
        client = SupabaseUnitOfWork().create_client()
        user_repo = repos.UserRepository(client)

        # Act
        email = Faker().email()
        user_repo.add(
            m.User(user_id=str(uuid.uuid4()), email=email, created_at=get_time())
        )

        with pytest.raises(repos.DuplicateEntryError):
            user_repo.add(
                m.User(user_id=str(uuid.uuid4()), email=email, created_at=get_time())
            )

    def test_maybe_get_one_user(self):
        client = SupabaseUnitOfWork().create_client()
        user_repo = repos.UserRepository(client)

        # Act
        user_id = str(uuid.uuid4())
        user = user_repo.add(m.User(user_id=user_id, created_at=get_time()))

        user_retrieved = user_repo.maybe_get_one(id=user.user_id)
        assert user == user_retrieved

    def test_get_user(self):
        client = SupabaseUnitOfWork().create_client()
        user_repo = repos.UserRepository(client)

        # Act
        user_id = str(uuid.uuid4())
        user = user_repo.add(m.User(user_id=user_id, created_at=get_time()))

        user_retrieved = user_repo.maybe_get_one(id=user.user_id)
        assert user == user_retrieved

    def test_get_all(self):
        client = SupabaseUnitOfWork().create_client()
        user_repo = repos.UserRepository(client)

        # Act
        user1 = user_repo.add(m.User(user_id=str(uuid.uuid4()), created_at=get_time()))
        user2 = user_repo.add(m.User(user_id=str(uuid.uuid4()), created_at=get_time()))

        users_retrieved = user_repo.get_all()
        assert user1 in users_retrieved
        assert user2 in users_retrieved

    def test_update_user(self):
        client = SupabaseUnitOfWork().create_client()
        user_repo = repos.UserRepository(client)

        # Act
        user = user_repo.add(m.User(user_id=str(uuid.uuid4()), created_at=get_time()))

        user.email = Faker().email()
        user_updated = user_repo.update(user)
        assert user_updated == user

    def test_delete_user(self):
        client = SupabaseUnitOfWork().create_client()
        user_repo = repos.UserRepository(client)

        # Act
        user = user_repo.add(m.User(user_id=str(uuid.uuid4()), created_at=get_time()))

        user_repo.delete(user.user_id)
        user_retrieved = user_repo.maybe_get_one(id=user.user_id)
        assert user_retrieved is None
