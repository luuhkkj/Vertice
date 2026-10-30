
"""Tela do Assistente IA."""

import base64
from pathlib import Path

import streamlit as st

from components.chat import balao
from components.layout import titulo_pagina
from data import mock_data


PASTA_ICONS = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "icons"
)


def _icone_base64(nome):
    """Converte um ícone local para base64."""

    caminho = PASTA_ICONS / nome

    if not caminho.is_file():
        return None

    return base64.b64encode(
        caminho.read_bytes()
    ).decode("utf-8")


def _aplicar_estilos():
    """Mantém o layout do desktop e adapta o chat ao celular."""

    st.html(
        """
        <style>
            /* Card principal */

            .st-key-assistente_card {
                width: 90% !important;
                max-width: 1375px !important;
                margin: 30px auto 0 !important;
                min-width: 0 !important;
                box-sizing: border-box;
            }

            /* Cabeçalho */

            .st-key-assistente_cabecalho {
                width: 100%;
            }

            .st-key-assistente_cabecalho
            .assistente-header-linha {
                display: flex;
                align-items: center;
                gap: 14px;
                min-height: 44px;
            }

            .st-key-assistente_cabecalho
            .assistente-header-icone {
                width: 30px;
                height: 30px;
                flex: 0 0 30px;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .st-key-assistente_cabecalho
            .assistente-header-icone img {
                display: block;
                width: 30px;
                height: 30px;
                object-fit: contain;
            }

            .st-key-assistente_cabecalho
            .assistente-header-titulo {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }

            /* Histórico da conversa */

            .st-key-assistente_mensagens {
                width: 100%;
                min-width: 0;
            }

            /* Rodapé */

            .st-key-assistente_rodape {
                width: 100%;
                min-width: 0;
            }

            .st-key-assistente_rodape
            [data-testid="stForm"] {
                width: 100%;
                min-width: 0;
                border: none !important;
                background: transparent !important;
                padding: 0 !important;
                box-shadow: none !important;
            }

            /* Mantém as colunas alinhadas no desktop */

            .st-key-assistente_rodape
            [data-testid="stHorizontalBlock"] {
                align-items: center !important;
            }

            .st-key-assistente_rodape
            [data-testid="column"],
            .st-key-assistente_rodape
            [data-testid="stColumn"] {
                min-width: 0 !important;
            }

            /* Ícone decorativo do desktop */

            .st-key-assistente_rodape
            .assistente-envio {
                width: 100%;
                height: 48px;
                display: flex;
                justify-content: center;
                align-items: center;
            }

            .st-key-assistente_rodape
            .assistente-envio img {
                display: block;
                width: 27px;
                height: 27px;
                object-fit: contain;
            }

            /* Campo de mensagem */

            .st-key-assistente_rodape
            [data-testid="stTextInput"] {
                width: 100%;
                min-width: 0;
            }

            .st-key-assistente_rodape
            [data-testid="stTextInput"]
            [data-baseweb="input"] {
                min-height: 46px;
                border-radius: 100px !important;
                overflow: hidden !important;
                background: #ffffff !important;
                border: 1px solid #e2e8f0 !important;
                box-shadow: 0 2px 5px rgba(0,0,0,0.08);
            }

            .st-key-assistente_rodape
            [data-testid="stTextInput"] input {
                min-height: 46px !important;
                width: 100%;
                min-width: 0;
                border-radius: 100px !important;
                background: transparent !important;
                padding-left: 18px !important;
                font-size: 14px;
                outline: none !important;
            }

            .st-key-assistente_rodape
            [data-testid="stTextInput"]
            [data-baseweb="input"]:focus-within {
                border: 1px solid #4E67CA !important;
                border-radius: 100px !important;
                box-shadow:
                    0 0 0 2px rgba(78,103,202,0.12)
                    !important;
            }

            /* Botão Enviar */

            .st-key-assistente_rodape
            [data-testid="stFormSubmitButton"] {
                display: flex !important;
                width: 100% !important;
                align-items: center !important;
                justify-content: center !important;
            }

            .st-key-assistente_rodape
            [data-testid="stFormSubmitButton"] button {
                display: flex !important;
                width: 100% !important;
                min-height: 46px !important;
                align-items: center !important;
                justify-content: center !important;
                padding: 0 12px !important;
                background: #334D8D !important;
                color: #ffffff !important;
                border: none !important;
                border-radius: 15px !important;
                font-weight: 600 !important;
                text-align: center !important;
            }

            .st-key-assistente_rodape
            [data-testid="stFormSubmitButton"] button:hover {
                background: #4E67CA !important;
            }

            .st-key-assistente_rodape
            [data-testid="stFormSubmitButton"] button p,
            .st-key-assistente_rodape
            [data-testid="stFormSubmitButton"] button span,
            .st-key-assistente_rodape
            [data-testid="stFormSubmitButton"]
            [data-testid="stMarkdownContainer"] {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                width: 100%;
                margin: 0 !important;
                padding: 0 !important;
                line-height: 1.2 !important;
                text-align: center !important;
                color: #ffffff !important;
            }

            /* Tablet */

            @media (max-width: 900px) {
                .st-key-assistente_card {
                    width: 98% !important;
                    margin-top: 15px !important;
                }

                .st-key-assistente_cabecalho
                .assistente-header-titulo {
                    font-size: 16px;
                }
            }

            /* Celular */

            @media (max-width: 600px) {

                /* O chat aproveita a largura disponível */

                .st-key-assistente_card {
                    width: 100% !important;
                    max-width: 100% !important;
                    margin: 12px auto 0 !important;
                    min-width: 0 !important;
                }

                /* Cabeçalho mais compacto */

                .st-key-assistente_cabecalho
                .assistente-header-linha {
                    min-height: 40px;
                    gap: 10px;
                }

                .st-key-assistente_cabecalho
                .assistente-header-icone,
                .st-key-assistente_cabecalho
                .assistente-header-icone img {
                    width: 25px;
                    height: 25px;
                    flex-basis: 25px;
                }

                .st-key-assistente_cabecalho
                .assistente-header-titulo {
                    font-size: 15px;
                }

                /* Diminui o espaço vazio das mensagens */

                .st-key-assistente_mensagens {
                    height: 245px !important;
                    min-height: 180px !important;
                    max-height: 245px !important;
                    overflow-y: auto !important;
                    overflow-x: hidden !important;
                }

                .st-key-assistente_mensagens
                [data-testid="stVerticalBlockBorderWrapper"] {
                    height: 245px !important;
                    min-height: 180px !important;
                    max-height: 245px !important;
                    overflow-y: auto !important;
                }

                /* Mantém o formulário em uma única linha */

                .st-key-assistente_rodape
                [data-testid="stForm"]
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) 88px !important;
                    align-items: center !important;
                    gap: 8px !important;
                    width: 100% !important;
                    min-width: 0 !important;
                    flex-wrap: nowrap !important;
                }

                /* O aviãozinho isolado não aparece no celular */

                .st-key-assistente_rodape
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"]:first-child,
                .st-key-assistente_rodape
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"]:first-child {
                    display: none !important;
                }

                /* Campo e botão ocupam suas células */

                .st-key-assistente_rodape
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"],
                .st-key-assistente_rodape
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                .st-key-assistente_rodape
                [data-testid="stTextInput"]
                [data-baseweb="input"] {
                    min-height: 42px !important;
                }

                .st-key-assistente_rodape
                [data-testid="stTextInput"] input {
                    min-height: 42px !important;
                    font-size: 13px !important;
                    padding-left: 12px !important;
                }

                .st-key-assistente_rodape
                [data-testid="stFormSubmitButton"] button {
                    min-height: 42px !important;
                    height: 42px !important;
                    padding: 0 8px !important;
                    border-radius: 12px !important;
                    font-size: 13px !important;
                }
            }
        </style>
        """
    )


def _renderizar_cabecalho(icone_ia):
    """Exibe o ícone e o título do assistente."""

    with st.container(key="assistente_cabecalho"):
        if icone_ia:
            st.html(
                f"""
                <div class="assistente-header-linha">
                    <div class="assistente-header-icone">
                        <img
                            src="data:image/svg+xml;base64,{icone_ia}"
                            alt="Assistente IA"
                        >
                    </div>
                    <div class="assistente-header-titulo">
                        Assistente virtual
                    </div>
                </div>
                """
            )
        else:
            st.html(
                """
                <div class="assistente-header-linha">
                    <div class="assistente-header-titulo">
                        Assistente virtual
                    </div>
                </div>
                """
            )


def _renderizar_mensagens(mensagens):
    """Exibe o histórico da conversa."""

    with st.container(
        key="assistente_mensagens",
        height=390,
    ):
        for indice, mensagem in enumerate(mensagens):
            balao(
                mensagem["texto"],
                mensagem["autor"],
                indice,
            )


def _renderizar_rodape(icone_envio):
    """Exibe o campo de mensagem e o botão Enviar."""

    with st.container(key="assistente_rodape"):
        with st.form(
            "form_chat",
            clear_on_submit=True,
            border=False,
        ):
            col_icone, col_texto, col_botao = st.columns(
                [0.6, 8, 1.4],
                gap="small",
                vertical_alignment="center",
            )

            with col_icone:
                if icone_envio:
                    st.html(
                        f"""
                        <div class="assistente-envio">
                            <img
                                src="data:image/svg+xml;base64,{icone_envio}"
                                alt=""
                            >
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

    return enviado, texto


def render():
    """Renderiza a tela do Assistente IA."""

    titulo_pagina("Assistente IA")
    _aplicar_estilos()

    icone_ia = _icone_base64("IA.svg")
    icone_envio = _icone_base64("envio.svg")

    st.session_state.setdefault("chat_mensagens", [])

    mensagens = st.session_state["chat_mensagens"]

    with st.container(key="assistente_card"):
        _renderizar_cabecalho(icone_ia)

        _renderizar_mensagens(mensagens)

        enviado, texto = _renderizar_rodape(
            icone_envio
        )

    if st.session_state.get("chat_pendente_backend"):
        st.info("Mensagem registrada. O assistente aguarda conexão com o backend.")

    if enviado and texto.strip():
        mensagens.append(
            {
                "autor": "usuario",
                "texto": texto.strip(),
            }
        )

        st.session_state["chat_pendente_backend"] = True

        st.rerun()
