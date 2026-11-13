"""Configuração de identidade e integração do Vértice."""

import os

NOME_APP = "Vértice"
NOME_ESCOLA = ""

# URL base da API FastAPI do Vértice (Fase 5 — Integração Frontend/Backend)
API_BASE_URL = os.environ.get(
    "VERTICE_API_URL",
    "http://127.0.0.1:8000/api/v1",
).rstrip("/")

