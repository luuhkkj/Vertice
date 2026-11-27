"""Cores usadas nos gráficos (Plotly), que não entendem as variáveis do CSS.

Mantenha estas cores iguais às de styles/base.css.
"""
AZUL = "#4e67ca"
AZUL_ESCURO = "#1e3a5f"
VERDE = "#43a047"
LARANJA = "#f59e0b"
VERMELHO = "#e53935"
GRAFITE = "#232020"
FONTE = "Inter, Segoe UI, Roboto, Arial, sans-serif"

SEQUENCIA_CORES = [AZUL, LARANJA, VERDE, VERMELHO]

COR_POR_CATEGORIA = {
    "Baixo": VERDE, "Atenção": LARANJA, "Alto": VERMELHO,
    "Fácil": VERDE, "Adequada": AZUL, "Difícil": VERMELHO,
    "Ótima": VERDE, "Boa": AZUL, "Crítica": VERMELHO,
}