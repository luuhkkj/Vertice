"""Tela do Assistente IA."""

import base64
from pathlib import Path

import streamlit as st

from components.chat import balao
from components.layout import titulo_pagina
from data import mock_data

PASTA_ICONS = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _icone_base64(nome):
    """Converte um ícone local para base64."""
    caminho = PASTA_ICONS / nome
    if not caminho.exists():
        return None
    return base64.b64encode(caminho.read_bytes()).decode("utf-8")


def render():
    """Renderiza o chat do assistente."""
    titulo_pagina("Assistente IA")

    icone_ia = _icone_base64("IA.svg")
    icone_envio = _icone_base64("envio.svg")

    st.session_state.setdefault(
        "chat_mensagens",
        [{"autor": "assistente", "texto": mock_data.MENSAGEM_BOAS_VINDAS}],
    )
    mensagens = st.session_state["chat_mensagens"]

    with st.container(key="assistente_card"):
        with st.container(key="assistente_cabecalho"):
            if icone_ia:
                st.html(
                    f"""
<div class="assistente-header-linha">
    <div class="assistente-header-icone">
        <img src="data:image/svg+xml;base64,{icone_ia}" alt="">
    </div>
    <div class="assistente-header-titulo">Assistente virtual</div>
</div>
"""
                )
            else:
                st.html(
                    '<div class="assistente-header-linha">'
                    '<div class="assistente-header-titulo">Assistente virtual</div>'
                    "</div>"
                )

        with st.container(key="assistente_mensagens", height=390):
            for indice, mensagem in enumerate(mensagens):
                balao(mensagem["texto"], mensagem["autor"], indice)

        with st.container(key="assistente_rodape"):
            with st.form("form_chat", clear_on_submit=True, border=False):
                col_envio, col_texto, col_botao = st.columns(
                    [0.45, 8.2, 1.35],
                    gap="small",
                    vertical_alignment="center",
                )

                with col_envio:
                    if icone_envio:
                        st.html(
                            f"""
<div class="assistente-envio">
    <img src="data:image/svg+xml;base64,{icone_envio}" alt="">
</div>
"""
                        )

                with col_texto:
                    texto = st.text_input(
                        "Mensagem",
                        placeholder="Peça ao assistente",
                        label_visibility="collapsed",
                        key="assistente_input",
                    )

                with col_botao:
                    enviado = st.form_submit_button(
                        "Enviar",
                        use_container_width=True,
                    )

        if enviado and texto.strip():
            mensagens.append({"autor": "usuario", "texto": texto.strip()})
            #  resposta simulada.
            mensagens.append(
                {"autor": "assistente", "texto": mock_data.RESPOSTA_SIMULADA}
            )
            st.rerun()
