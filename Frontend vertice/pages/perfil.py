
"""Tela: Perfil do usuário."""

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina
from data.atribuicoes import listar_atribuicoes


def render():
    """Mostra as informações do perfil conectado."""

    if not st.session_state.get("logado"):
        st.error("É necessário entrar no sistema.")
        return

    titulo_pagina(
        "Meu Perfil",
        "Informações do usuário e permissões de acesso.",
    )

    perfil = st.session_state.get("perfil", "professor")
    administrador = perfil == "administrador"

    nome = (
        "Administrador"
        if administrador
        else st.session_state.get("professor_atual")
        or "Professor"
    )

    with st.container(key="perfil_informacoes"):
        st.subheader("Informações do usuário")

        col_nome, col_acesso = st.columns(2)

        with col_nome:
            st.text_input(
                "Nome",
                value=nome,
                disabled=True,
            )

        with col_acesso:
            st.text_input(
                "Tipo de acesso",
                value=(
                    "Administrador"
                    if administrador
                    else "Professor"
                ),
                disabled=True,
            )

    st.divider()

    st.subheader("Permissões de acesso")

    if administrador:
        st.success(
            "Seu perfil possui acesso às páginas "
            "administrativas do Vértice."
        )

        st.write(
            "Você pode visualizar os indicadores, "
            "importar dados e gerenciar atribuições."
        )
    else:
        st.info(
            "Seu perfil possui acesso somente "
            "às turmas atribuídas."
        )

        atribuicoes = [
            item
            for item in listar_atribuicoes()
            if item["Professor"] == nome
        ]

        st.subheader("Minhas turmas")

        if atribuicoes:
            tabela = pd.DataFrame(atribuicoes)

            st.dataframe(
                tabela[["Disciplina", "Turma"]],
                hide_index=True,
                width="stretch",
            )
        else:
            st.warning(
                "Você ainda não possui turmas atribuídas."
            )

    st.caption("Informações de acesso aguardam integração com o serviço de autenticação.")
