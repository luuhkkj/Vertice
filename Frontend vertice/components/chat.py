"""Componentes visuais do chat."""

import streamlit as st


def balao(texto, autor, indice):
    """Renderiza uma mensagem à esquerda ou à direita, conforme o autor."""
    if autor == "usuario":
        _, col_mensagem = st.columns([1.15, 2.85], gap="small")
        chave = f"chat_usuario_{indice}"
    else:
        col_mensagem, _ = st.columns([1.65, 2.35], gap="small")
        chave = f"chat_assistente_{indice}"

    with col_mensagem:
        with st.container(key=chave):
            st.markdown(texto)
