import uuid
import pytest
import grannymail.db.repositories as repos
import grannymail.core.models as dbc
from faker import Faker

# from grannymail.db.models import User


class TestRepositoryBase:
    def test_add_successfully_returns_added_entity(self):
        # Arrange
        with pytest.raises(TypeError):
            repos.RepositoryBase()


class TestUserRepository:
    def test_init(self):
        # Arrange
        client = repos.create_supabase_client()
        user_repo = repos.UserRepository(client)

        assert user_repo.__table__ == "users"
        assert user_repo.__id_col__ == "user_id"
        assert user_repo.__data_type__ == dbc.User

    def test_add_user(self):
        # Arrange
        client = repos.create_supabase_client()
        user_repo = repos.UserRepository(client)

        # Act
        user_id = str(uuid.uuid4())
        user = user_repo.add(dbc.User(user_id=user_id))

        # Assert
        assert user == dbc.User(user_id=user_id)

    def test_fail_add_user_duplicate_email(self):
        client = repos.create_supabase_client()
        user_repo = repos.UserRepository(client)

        # Act
        email = Faker().email()
        user_repo.add(dbc.User(user_id=str(uuid.uuid4()), email=email))

        with pytest.raises(repos.DuplicateEntryError):
            user_repo.add(dbc.User(user_id=str(uuid.uuid4()), email=email))

    def test_maybe_get_one_user(self):
        client = repos.create_supabase_client()
        user_repo = repos.UserRepository(client)

        # Act
        user_id = str(uuid.uuid4())
        user = user_repo.add(dbc.User(user_id=user_id))

        user_retrieved = user_repo.maybe_get_one(id=user.user_id)
        assert user == user_retrieved

    def test_get_user(self):
        client = repos.create_supabase_client()
        user_repo = repos.UserRepository(client)

        # Act
        user_id = str(uuid.uuid4())
        user = user_repo.add(dbc.User(user_id=user_id))

        user_retrieved = user_repo.maybe_get_one(id=user.user_id)
        assert user == user_retrieved

    def test_get_all(self):
        client = repos.create_supabase_client()
        user_repo = repos.UserRepository(client)

        # Act
        user1 = user_repo.add(dbc.User(user_id=str(uuid.uuid4())))
        user2 = user_repo.add(dbc.User(user_id=str(uuid.uuid4())))

        users_retrieved = user_repo.get_all()
        assert user1 in users_retrieved
        assert user2 in users_retrieved

    def test_update_user(self):
        client = repos.create_supabase_client()
        user_repo = repos.UserRepository(client)

        # Act
        user = user_repo.add(dbc.User(user_id=str(uuid.uuid4())))

        user.email = Faker().email()
        user_updated = user_repo.update(user)
        assert user_updated == user

    def test_delete_user(self):
        client = repos.create_supabase_client()
        user_repo = repos.UserRepository(client)

        # Act
        user = user_repo.add(dbc.User(user_id=str(uuid.uuid4())))

        user_repo.delete(user)
        user_retrieved = user_repo.maybe_get_one(id=user.user_id)
        assert user_retrieved is None
