
"""Componentes visuais do chat."""

import streamlit as st


def _estilos_baloes():
    """Corrige o alinhamento e o tamanho dos balões."""

    st.html(
        """
        <style>
            /* Balões do assistente e do usuário */
            [class*="st-key-chat_assistente_"],
            [class*="st-key-chat_usuario_"] {
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;

                height: auto !important;
                min-height: 44px !important;
                max-height: none !important;

                padding: 10px 14px !important;
                box-sizing: border-box !important;
            }

            /* Bloco que contém o texto */
            [class*="st-key-chat_assistente_"]
            [data-testid="stMarkdownContainer"],
            [class*="st-key-chat_usuario_"]
            [data-testid="stMarkdownContainer"] {
                width: 100% !important;
                height: auto !important;
                min-height: 0 !important;

                margin: 0 !important;
                padding: 0 !important;

                display: block !important;
                text-align: left !important;
            }

            /* Texto das mensagens */
            [class*="st-key-chat_assistente_"]
            [data-testid="stMarkdownContainer"] p,
            [class*="st-key-chat_usuario_"]
            [data-testid="stMarkdownContainer"] p {
                margin: 0 !important;
                padding: 0 !important;

                font-size: 14px !important;
                line-height: 1.5 !important;
                text-align: left !important;

                white-space: pre-wrap !important;
                overflow-wrap: anywhere !important;
                word-break: normal !important;
            }

            /* Evita espaçamento extra entre blocos */
            [class*="st-key-chat_assistente_"]
            [data-testid="stMarkdownContainer"] > :last-child,
            [class*="st-key-chat_usuario_"]
            [data-testid="stMarkdownContainer"] > :last-child {
                margin-bottom: 0 !important;
            }

            /* Evita cortes em mensagens maiores */
            [class*="st-key-chat_assistente_"]
            [data-testid="stMarkdown"],
            [class*="st-key-chat_usuario_"]
            [data-testid="stMarkdown"] {
                height: auto !important;
                min-height: 0 !important;
                overflow: visible !important;
            }
        </style>
        """
    )


def balao(texto, autor, indice):
    """Renderiza uma mensagem à esquerda ou à direita."""

    if indice == 0:
        _estilos_baloes()

    if autor == "usuario":
        _, col_mensagem = st.columns(
            [1.15, 2.85],
            gap="small",
        )
        chave = f"chat_usuario_{indice}"

    else:
        col_mensagem, _ = st.columns(
            [1.65, 2.35],
            gap="small",
        )
        chave = f"chat_assistente_{indice}"

    with col_mensagem:
        with st.container(key=chave):
            st.markdown(texto)
