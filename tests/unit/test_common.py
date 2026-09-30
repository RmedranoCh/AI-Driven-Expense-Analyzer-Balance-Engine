import os
import pytest
from unittest.mock import patch


def test_get_groq_key_from_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-key-456")
    from expense_analyzer.ai._common import get_groq_key
    assert get_groq_key() == "env-key-456"


def test_get_groq_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with patch("expense_analyzer.ai._common.st.secrets", {}):
        from expense_analyzer.ai._common import get_groq_key
        with pytest.raises(RuntimeError, match="GROQ_API_KEY not found"):
            get_groq_key()


def test_modelo_de_vision_actual():
    from expense_analyzer.ai import _common
    assert _common.MODELO_VISION_POR_DEFECTO == "qwen/qwen3.8-27b"


def test_modelos_de_texto_soportados_incluyen_el_de_vision_por_defecto():
    from expense_analyzer.ai import _common
    assert _common.MODELO_VISION_POR_DEFECTO in _common.MODELOS_TEXTO_SOPORTADOS


def test_modelo_de_clasificacion_soportado():
    from expense_analyzer.ai import _common
    assert _common.MODELO_CLASIFICACION_POR_DEFECTO in _common.MODELOS_TEXTO_SOPORTADOS
