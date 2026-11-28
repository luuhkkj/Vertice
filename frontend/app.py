"""Ponto de entrada do Vértice."""

import logging

import streamlit as st

from pages import login as auth_animada
from components.estilos import carregar_estilos
from components.layout import render_header, render_sidebar
from config import NOME_APP
from pages import (
    administracao_tecnica,
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

logger = logging.getLogger(__name__)
_EXCECOES_CONTROLE_STREAMLIT = (
    "RerunException",
    "StopException",
    "ScriptControlException",
)


st.set_page_config(
    page_title=NOME_APP,
    page_icon="assets/icons/capelo.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

carregar_estilos()

st.session_state.setdefault("logado", False)
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
        paginas_menu = [
            st.Page(
                administracao_tecnica.render,
                title="Visão geral",
                url_path="visao-geral",
                default=True,
            ),
            st.Page(
                administracao_tecnica.render_usuarios_e_contas,
                title="Usuários e Contas",
                url_path="usuarios-e-contas",
            ),
            st.Page(
                administracao_tecnica.render_estrutura,
                title="Escolas, Turmas e Disciplinas",
                url_path="escolas-turmas-disciplinas",
            ),
            st.Page(
                administracao_tecnica.render_credenciais_ml,
                title="Credenciais ML",
                url_path="credenciais-ml",
            ),
            st.Page(
                administracao_tecnica.render_auditoria,
                title="Auditoria Técnica e IA",
                url_path="auditoria-tecnica-ia",
            ),
            pagina_perfil,
        ]
        return list(paginas_menu), list(paginas_menu)

    pagina_modelos = st.Page(
        modelos_prova.render,
        title="Modelos de Planilha",
        url_path="modelos-de-prova",
    )
    st.session_state["pagina_modelos_prova"] = pagina_modelos

    if papel == "professor":
        pagina_mapa = st.Page(
            mapa_acertos.render,
            title="Mapa de Acertos",
            url_path="mapa-de-acertos",
        )
        st.session_state["pagina_mapa_acertos"] = pagina_mapa
    else:
        pagina_mapa = None
        st.session_state.pop("pagina_mapa_acertos", None)

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
    ]

    if papel == "gestor":
        paginas_menu.append(
            st.Page(
                entrada_dados.render,
                title="Entrada de Dados",
                url_path="entrada-de-dados",
            )
        )

    paginas_menu.append(
        st.Page(
            assistente_ia.render,
            title="Assistente IA",
            url_path="assistente-ia",
        )
    )

    if papel == "professor":
        paginas_menu.extend(
            [
                pagina_mapa,
                st.Page(
                    participacao.render,
                    title="Participação",
                    url_path="participacao",
                ),
            ]
        )

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


def executar_navegacao_autenticada() -> None:
    """
    Renderiza o cabeçalho e o menu lateral personalizado antes da execução da página
    selecionada, garantindo que a navegação permaneça visível mesmo se ocorrer uma exceção.
    """
    paginas_navegacao, paginas_menu = montar_paginas_internas()

    pagina_atual = st.navigation(
        paginas_navegacao,
        position="hidden",
    )

    # Cabeçalho e menu lateral são posicionados de forma fixa pelo CSS;
    # renderizá-los antes da página impede o desaparecimento da navegação em caso de erro.
    render_header(paginas_menu)
    render_sidebar(paginas_menu, pagina_atual)

    try:
        papel = obter_papel_canonico()
        if papel in ("gestor", "professor"):
            with st.container(key=f"{papel}_workspace"):
                pagina_atual.run()
        else:
            pagina_atual.run()
    except Exception as exc:
        if type(exc).__name__ in _EXCECOES_CONTROLE_STREAMLIT:
            raise
        logger.exception(
            "Erro inesperado ao renderizar a página '%s'.",
            getattr(pagina_atual, "title", ""),
        )
        st.error(
            "Ocorreu um erro inesperado ao carregar esta página. "
            "Use o menu lateral para navegar para outra seção ou tente novamente."
        )
        st.caption(f"Detalhe técnico ({type(exc).__name__}): {exc}")


if st.session_state["logado"]:
    executar_navegacao_autenticada()
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
