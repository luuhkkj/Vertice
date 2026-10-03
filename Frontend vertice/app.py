"""Ponto de entrada do Vértice."""

import streamlit as st

from components.estilos import carregar_estilos
from components.layout import render_header, render_sidebar
from config import NOME_APP, PERFIL_ATUAL
from pages import (
    assistente_ia,
    atribuicao,
    cadastro,
    entrada_dados,
    estudantes,
    login,
    mapa_acertos,
    participacao,
    visao_geral,
)

st.set_page_config(page_title=NOME_APP, page_icon="🎓", layout="wide")
carregar_estilos()

st.session_state.setdefault("logado", False)
st.session_state.setdefault("tela_auth", "login")


def montar_paginas_internas():
    """Monta as páginas disponíveis para o perfil atual."""
    paginas = [
        st.Page(
            visao_geral.render,
            title="Visão geral",
            url_path="visao-geral",
            default=True,
        ),
        st.Page(estudantes.render, title="Estudantes", url_path="estudantes"),
        st.Page(
            entrada_dados.render,
            title="Entrada de Dados",
            url_path="entrada-de-dados",
        ),
        st.Page(
            assistente_ia.render,
            title="Assistente IA",
            url_path="assistente-ia",
        ),
        st.Page(
            mapa_acertos.render,
            title="Mapa de Acertos",
            url_path="mapa-de-acertos",
        ),
        st.Page(
            participacao.render,
            title="Participação",
            url_path="participacao",
        ),
    ]

    if PERFIL_ATUAL == "coordenador":
        paginas.append(
            st.Page(
                atribuicao.render,
                title="Atribuir turmas",
                url_path="atribuir-turmas",
            )
        )

    return paginas


if st.session_state["logado"]:
    paginas = montar_paginas_internas()
    pagina_atual = st.navigation(paginas, position="hidden")
    render_header()
    render_sidebar(paginas, pagina_atual)
    pagina_atual.run()
else:
    # A autenticação também usa st.navigation para esconder o menu automático de pages/.
    tela_auth = cadastro if st.session_state["tela_auth"] == "cadastro" else login
    pagina_auth = st.Page(tela_auth.render, title=NOME_APP, default=True)
    st.navigation([pagina_auth], position="hidden").run()
