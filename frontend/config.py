"""Configuração de identidade e integração do Vértice."""

import os
import streamlit as st

NOME_APP = "Vértice"
NOME_ESCOLA = ""

try:
    api_url = st.secrets.get("VERTICE_API_URL", "")
except Exception:
    api_url = ""

# URL base da API FastAPI do Vértice (Fase 5 — Integração Frontend/Backend)
if not api_url:
    api_url = os.environ.get("VERTICE_API_URL", "")

if not api_url:
    api_url = "http://127.0.0.1:8000/api/v1"

API_BASE_URL = api_url.rstrip("/")

