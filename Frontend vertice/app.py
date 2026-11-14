
"""Ponto de entrada do Vértice."""

import streamlit as st

from components import auth_animada
from components.estilos import carregar_estilos
from components.layout import render_header, render_sidebar
from config import NOME_APP
from pages import (
    assistente_ia,
    atribuicao,
    entrada_dados,
    estudantes,
    mapa_acertos,
    modelos_prova,
    participacao,
    perfil,
    visao_geral,
)


st.set_page_config(
    page_title=NOME_APP,
    page_icon="assets/icons/capelo.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

carregar_estilos()

st.session_state.setdefault("logado", False)
st.session_state.setdefault("tela_auth", "login")
st.session_state.setdefault("perfil", "professor")


def obter_papel_canonico() -> str:
    """Retorna o papel canônico do usuário autenticado (`administrador`, `gestor` ou `professor`)."""
    usuario_api = st.session_state.get("usuario_api")
    if isinstance(usuario_api, dict) and usuario_api.get("papel"):
        papel = str(usuario_api["papel"]).strip().lower()
    else:
        papel = str(
            st.session_state.get("papel_api")
            or st.session_state.get("perfil")
            or "professor"
        ).strip().lower()
    if papel in ("administrador", "gestor", "professor"):
        return papel
    return "professor"


def montar_paginas_internas():
    """Define as páginas e os acessos conforme os papéis canônicos do backend."""

    papel = obter_papel_canonico()

    pagina_perfil = st.Page(
        perfil.render,
        title="Meu Perfil",
        url_path="perfil",
    )

    if papel == "administrador":
        pagina_atribuicao = st.Page(
            atribuicao.render,
            title="Atribuir turmas",
            url_path="atribuir-turmas",
            default=True,
        )
        paginas_menu = [pagina_atribuicao, pagina_perfil]
        return list(paginas_menu), list(paginas_menu)

    pagina_mapa = st.Page(
        mapa_acertos.render,
        title="Mapa de Acertos",
        url_path="mapa-de-acertos",
    )

    pagina_modelos = st.Page(
        modelos_prova.render,
        title="Modelos de Planilha",
        url_path="modelos-de-prova",
    )

    st.session_state["pagina_mapa_acertos"] = pagina_mapa
    st.session_state["pagina_modelos_prova"] = pagina_modelos

    paginas_menu = [
        st.Page(
            visao_geral.render,
            title="Visão geral",
            url_path="visao-geral",
            default=True,
        ),
        st.Page(
            estudantes.render,
            title="Estudantes",
            url_path="estudantes",
        ),
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
        pagina_mapa,
        st.Page(
            participacao.render,
            title="Participação",
            url_path="participacao",
        ),
    ]

    if papel == "gestor":
        paginas_menu.append(
            st.Page(
                atribuicao.render,
                title="Atribuir turmas",
                url_path="atribuir-turmas",
            )
        )

    paginas_menu.append(pagina_perfil)
    paginas_navegacao = paginas_menu + [pagina_modelos]
    return paginas_navegacao, paginas_menu


if st.session_state["logado"]:

    paginas_navegacao, paginas_menu = montar_paginas_internas()

    pagina_atual = st.navigation(
        paginas_navegacao,
        position="hidden",
    )

    # A página vem primeiro no fluxo do Streamlit.
    # Cabeçalho e menu são posicionados de forma fixa pelo CSS.
    pagina_atual.run()

    render_header(paginas_menu)
    render_sidebar(paginas_menu, pagina_atual)

else:

    pagina_auth = st.Page(
        auth_animada.render,
        title=NOME_APP,
        default=True,
    )

    st.navigation(
        [pagina_auth],
        position="hidden",
    ).run()
