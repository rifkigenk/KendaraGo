from pathlib import Path

import pytest

from app import create_app
from config import TestingConfig
from extensions import db


@pytest.fixture()
def app(tmp_path):
    class LocalTestingConfig(TestingConfig):
        SECRET_KEY = "a" * 64
        WTF_CSRF_SECRET_KEY = "b" * 64
        PAYMENT_DEADLINE_HOURS = 2

    LocalTestingConfig.PUBLIC_UPLOAD_FOLDER = Path(tmp_path) / "public"
    LocalTestingConfig.PRIVATE_UPLOAD_FOLDER = Path(tmp_path) / "private"
    application = create_app(LocalTestingConfig)

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()
