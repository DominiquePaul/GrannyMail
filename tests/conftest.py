import pytest

from whatsgranny import create_app


@pytest.fixture()
def app():
    app = create_app()

    yield app

    # potentially add teardown


@pytest.fixture()
def client(app):
    # allows to simulate requests
    return app.test_client()
