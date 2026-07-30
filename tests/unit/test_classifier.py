import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def classifier():
    with patch("app.ai.classifier.get_groq_key", return_value="key"):
        with patch("app.ai.classifier.Groq"):
            from app.ai.classifier import ExpenseClassifier
            return ExpenseClassifier()


class TestClassifierInit:
    def test_categorias_validas_not_empty(self, classifier):
        assert len(classifier.categorias_validas) == 9

    def test_categorias_validas_include_otros(self, classifier):
        assert "Otros" in classifier.categorias_validas

    def test_categorias_validas_are_unique(self, classifier):
        assert len(classifier.categorias_validas) == len(set(classifier.categorias_validas))


class TestClassifyBatch:
    def test_empty_list_returns_empty(self, classifier):
        assert classifier.classify_batch([]) == []

    def test_valid_category_passes_through(self, classifier):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(
                content='{"clasificaciones": [{"item_id": 0, "categoria": "Infraestructura Cloud & Hosting"}]}'
            ))
        ]
        classifier.client.chat.completions.create.return_value = mock_response

        result = classifier.classify_batch(["Servidor EC2"])
        assert result == ["Infraestructura Cloud & Hosting"]

    def test_invalid_category_falls_to_otros(self, classifier):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(
                content='{"clasificaciones": [{"item_id": 0, "categoria": "Categoria Inexistente"}]}'
            ))
        ]
        classifier.client.chat.completions.create.return_value = mock_response

        result = classifier.classify_batch(["Algo raro"])
        assert result == ["Otros"]

    def test_missing_item_id_falls_to_otros(self, classifier):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(
                content='{"clasificaciones": [{"item_id": 5, "categoria": "Otros"}]}'
            ))
        ]
        classifier.client.chat.completions.create.return_value = mock_response

        result = classifier.classify_batch(["Item A"])
        assert result == ["Otros"]

    def test_multiple_items_mixed_validity(self, classifier):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(
                content='{"clasificaciones": ['
                        '{"item_id": 0, "categoria": "Infraestructura Cloud & Hosting"},'
                        '{"item_id": 1, "categoria": "Categoria Invalida"},'
                        '{"item_id": 2, "categoria": "Otros"}'
                        ']}'
            ))
        ]
        classifier.client.chat.completions.create.return_value = mock_response

        result = classifier.classify_batch(["AWS", "Algo raro", "Item genérico"])
        assert result == ["Infraestructura Cloud & Hosting", "Otros", "Otros"]

    def test_api_error_returns_all_otros(self, classifier):
        classifier.client.chat.completions.create.side_effect = Exception("API Error")

        result = classifier.classify_batch(["A", "B", "C"])
        assert result == ["Otros", "Otros", "Otros"]
