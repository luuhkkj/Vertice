"""Componentes compartilhados pelas telas de autenticação."""

import base64
from pathlib import Path

import streamlit as st

PASTA_ICONS = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _arquivo_base64(nome):
    """Lê um arquivo de ícone e devolve o conteúdo em base64."""
    caminho = PASTA_ICONS / nome
    if not caminho.exists():
        return None
    return base64.b64encode(caminho.read_bytes()).decode("utf-8")


def painel_boas_vindas():
    """Renderiza o painel de boas-vindas do login institucional."""
    capelo = _arquivo_base64("capelo.svg")

    with st.container(key="painel_creme"):
        with st.container(key="auth_bloco_esquerdo"):
            if capelo:
                st.html(
                    f"""
<div class="auth-capelo">
    <img src="data:image/svg+xml;base64,{capelo}" alt="Vértice">
</div>
"""
                )

            st.html(
                """
<div class="auth-textos">
    <div class="auth-titulo">Olá! Bem-vindo(a)<br>ao Vértice</div>
</div>
"""
            )
