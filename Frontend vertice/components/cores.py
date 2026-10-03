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

# Cores para séries sem significado próprio (ex.: uma linha por série)
SEQUENCIA_CORES = [AZUL, LARANJA, VERDE, VERMELHO]

# Semáforo: a cor de cada categoria que aparece nos gráficos.
COR_POR_CATEGORIA = {
    # Nível de risco (Visão geral)
    "Baixo": VERDE, "Atenção": LARANJA, "Alto": VERMELHO,
    # Dificuldade da questão (Mapa de Acertos)
    "Fácil": VERDE, "Adequada": AZUL, "Difícil": VERMELHO,
    # Situação da entrega por turma (Participação)
    "Ótima": VERDE, "Boa": AZUL, "Crítica": VERMELHO,
}