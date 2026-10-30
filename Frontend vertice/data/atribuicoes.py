
"""Gerenciamento temporário das atribuições de turmas."""

import streamlit as st

from data import mock_data


def listar_atribuicoes():
    """Retorna os vínculos atuais da sessão."""

    if "at_atribuicoes" not in st.session_state:
        st.session_state["at_atribuicoes"] = [
            dict(item)
            for item in mock_data.ATRIBUICOES_INICIAIS
        ]

    return st.session_state["at_atribuicoes"]
