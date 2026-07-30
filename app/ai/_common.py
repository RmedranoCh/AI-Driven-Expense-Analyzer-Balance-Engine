import os
import streamlit as st

def get_groq_key():
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        return st.secrets["GROQ_API_KEY"]
    except (KeyError, FileNotFoundError):
        raise RuntimeError("GROQ_API_KEY not found in env or Streamlit secrets")
