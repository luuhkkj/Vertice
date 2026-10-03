"""Estrutura comum a todas as telas: cabeçalho, menu lateral e título."""

import base64
import unicodedata
from pathlib import Path

import streamlit as st

from config import NOME_APP, NOME_ESCOLA


PASTA_ICONS = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "icons"
)


def _icone_base64(nome):
    """Converte um ícone local em base64."""

    caminho = PASTA_ICONS / nome

    if not caminho.exists():
        return None

    return base64.b64encode(
        caminho.read_bytes()
    ).decode("utf-8")


def render_header():
    """Faixa superior com logo, nome da escola e botão de sair."""

    capelo = _icone_base64("capelo.svg")

    with st.container(key="cabecalho"):

        col_logo, col_escola, col_sair = st.columns(
            [1, 2, 1],
            vertical_alignment="center",
        )

        with col_logo:

            if capelo:
                st.markdown(
                    f"""
                    <div class="vertice-logo">
                        <img
                            src="data:image/svg+xml;base64,{capelo}"
                            alt=""
                        >
                        <span>{NOME_APP}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            else:
                st.markdown(f"**{NOME_APP}**")

        with col_escola:
            st.markdown(NOME_ESCOLA)

        with col_sair:

            if st.button(
                "Sair",
                key="btn_sair",
            ):
                st.session_state["logado"] = False
                st.rerun()


def carregar_icone(caminho):
    """Converte um arquivo de ícone em base64."""

    arquivo = Path(caminho)

    if not arquivo.exists():
        return None

    return base64.b64encode(
        arquivo.read_bytes()
    ).decode("utf-8")


def normalizar_texto(texto):
    """Remove acentos e padroniza texto para uso nas chaves."""

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        str(texto),
    )

    texto = (
        texto
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
        .strip()
    )

    texto = texto.replace(" / ", "-")
    texto = texto.replace("/", "-")
    texto = texto.replace(" ", "-")
    texto = texto.replace("_", "-")

    while "--" in texto:
        texto = texto.replace("--", "-")

    return texto.strip("-")


def identificar_pagina(pagina):
    """Cria um identificador estável para cada página."""

    url_path = (
        getattr(pagina, "url_path", "")
        or ""
    )

    title = (
        getattr(pagina, "title", "")
        or ""
    )

    url_norm = normalizar_texto(url_path)
    title_norm = normalizar_texto(title)

    if (
        not url_norm
        or url_norm in {
            "",
            "/",
            "home",
            "inicio",
            "index",
        }
    ):
        if (
            "visao" in title_norm
            and "geral" in title_norm
        ):
            return "visao-geral"

        if not title_norm:
            return "visao-geral"

    identificador = url_norm or title_norm

    aliases = {
        "visao-geral": "visao-geral",
        "estudantes": "estudantes",
        "entrada-de-dados": "entrada-de-dados",
        "assistente-ia": "assistente-ia",
        "mapa-de-acertos": "mapa-de-acertos",
        "participacao": "participacao",
        "participacao-dos-estudantes": "participacao",
        "atribuir-turmas": "atribuir-turmas",
        "atribuicao-de-turmas": "atribuir-turmas",
        "atribuicao-turmas": "atribuir-turmas",
    }

    return aliases.get(
        identificador,
        identificador,
    )


def render_sidebar(
    paginas,
    pagina_atual,
):
    """Renderiza o menu lateral com ícones personalizados."""

    icones = {
        "visao-geral": (
            "assets/icons/visao.svg",
            "image/svg+xml",
        ),
        "estudantes": (
            "assets/icons/estudantes.png",
            "image/png",
        ),
        "entrada-de-dados": (
            "assets/icons/dados.svg",
            "image/svg+xml",
        ),
        "assistente-ia": (
            "assets/icons/IA.svg",
            "image/svg+xml",
        ),
        "mapa-de-acertos": (
            "assets/icons/acertos.svg",
            "image/svg+xml",
        ),
        "participacao": (
            "assets/icons/participacao.svg",
            "image/svg+xml",
        ),
        "atribuir-turmas": (
            "assets/icons/atribuicao.svg",
            "image/svg+xml",
        ),
    }

    estilos_icones = []

    for identificador, (
        caminho,
        mime,
    ) in icones.items():

        icone_base64 = carregar_icone(
            caminho
        )

        if not icone_base64:
            continue

        nome_css = identificador.replace(
            "-",
            "_",
        )

        estilos_icones.append(
            f"""
            .st-key-menu_{nome_css}
            [data-testid="stPageLink-NavLink"]::before,

            .st-key-menu_ativo_{nome_css}
            [data-testid="stPageLink-NavLink"]::before {{

                content: "";

                display: inline-block;

                width: 25px;
                height: 25px;

                min-width: 25px;
                flex: 0 0 25px;

                background-color: #ffffff;

                -webkit-mask-image:
                    url("data:{mime};base64,{icone_base64}");

                mask-image:
                    url("data:{mime};base64,{icone_base64}");

                -webkit-mask-repeat: no-repeat;
                mask-repeat: no-repeat;

                -webkit-mask-position: center;
                mask-position: center;

                -webkit-mask-size: contain;
                mask-size: contain;

                margin-right: 10px;
            }}
            """
        )

    with st.sidebar:

        if estilos_icones:

            st.markdown(
                f"""
                <style>
                    {''.join(estilos_icones)}

                    [class*="st-key-menu_"]
                    [data-testid="stPageLink-NavLink"] {{
                        display: flex !important;
                        align-items: center !important;
                    }}

                    [class*="st-key-menu_"]
                    [data-testid="stPageLink-NavLink"] p {{
                        margin: 0 !important;
                    }}
                </style>
                """,
                unsafe_allow_html=True,
            )

        pagina_atual_id = identificar_pagina(
            pagina_atual
        )

        for pagina in paginas:

            pagina_id = identificar_pagina(
                pagina
            )

            prefixo = (
                "menu_ativo"
                if pagina_id == pagina_atual_id
                else "menu"
            )

            chave = (
                f"{prefixo}_"
                f"{pagina_id.replace('-', '_')}"
            )

            with st.container(
                key=chave
            ):
                st.page_link(pagina)


def _titulo_e_subtitulo(
    titulo,
    subtitulo,
):
    """Renderiza título e subtítulo."""

    st.title(
        titulo,
        anchor=False,
    )

    if subtitulo:
        st.caption(subtitulo)


def titulo_pagina(
    titulo,
    subtitulo=None,
    destaque=None,
):
    """Título padrão das páginas."""

    if destaque is None:

        _titulo_e_subtitulo(
            titulo,
            subtitulo,
        )

        return

    col_titulo, col_destaque = (
        st.columns(
            [3, 2],
            vertical_alignment="center",
        )
    )

    with col_titulo:

        _titulo_e_subtitulo(
            titulo,
            subtitulo,
        )

    with col_destaque:

        with st.container(
            key="pilula"
        ):
            st.markdown(destaque)