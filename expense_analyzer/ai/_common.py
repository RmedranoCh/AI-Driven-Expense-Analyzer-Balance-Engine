import os

import streamlit as st
from streamlit.errors import StreamlitAPIException

MODELO_VISION_POR_DEFECTO = "qwen/qwen3.8-27b"
MODELO_TEXTO_POR_DEFECTO = "openai/gpt-oss-120b"
MODELO_CLASIFICACION_POR_DEFECTO = "openai/gpt-oss-120b"

MODELOS_TEXTO_SOPORTADOS = (
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
)


def get_groq_key():
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        return st.secrets["GROQ_API_KEY"]
    except (KeyError, FileNotFoundError, StreamlitAPIException):
        raise RuntimeError("GROQ_API_KEY not found in env or Streamlit secrets")
