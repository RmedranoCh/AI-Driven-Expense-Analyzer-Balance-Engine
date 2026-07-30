import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.session import Base


@pytest.fixture
def mock_groq_key():
    with patch("app.ai._common.get_groq_key", return_value="test-key-123"):
        yield


@pytest.fixture
def mock_groq_client():
    with patch("app.ai.extractor.Groq") as mock:
        instance = mock.return_value
        instance.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content='{"proveedor": "mock", "items": []}'))
        ]
        yield instance


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
