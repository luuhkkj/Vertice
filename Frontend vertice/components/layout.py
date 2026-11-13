
"""Cabeçalho, navegação e títulos das páginas do Vértice."""

import base64
import unicodedata
from pathlib import Path

import streamlit as st

from config import NOME_APP, NOME_ESCOLA


RAIZ = Path(__file__).resolve().parent.parent
PASTA_ICONS = RAIZ / "assets" / "icons"


def _icone_base64(nome):
    """Lê um ícone da pasta de recursos."""

    caminho = PASTA_ICONS / nome

    if not caminho.is_file():
        return None

    return base64.b64encode(
        caminho.read_bytes()
    ).decode("utf-8")


def carregar_icone(caminho):
    """Lê uma imagem pelo caminho informado."""

    arquivo = Path(caminho)

    if not arquivo.is_absolute():
        arquivo = RAIZ / arquivo

    if not arquivo.is_file():
        return None

    return base64.b64encode(
        arquivo.read_bytes()
    ).decode("utf-8")


def normalizar_texto(texto):
    """Padroniza o identificador de uma página."""

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        str(texto),
    )

    texto = (
        texto.encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
        .strip()
    )

    for caractere in (" / ", "/", " ", "_"):
        texto = texto.replace(caractere, "-")

    while "--" in texto:
        texto = texto.replace("--", "-")

    return texto.strip("-")


def identificar_pagina(pagina):
    """Identifica a página utilizada na navegação."""

    url = getattr(pagina, "url_path", "") or ""
    titulo = getattr(pagina, "title", "") or ""

    identificador = (
        normalizar_texto(url)
        or normalizar_texto(titulo)
    )

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
        "perfil": "meu-perfil",
        "meu-perfil": "meu-perfil",
    }

    return aliases.get(
        identificador,
        identificador or "visao-geral",
    )


ICONES_MENU = {
    "visao-geral": ("visao.svg", "image/svg+xml"),
    "estudantes": ("estudantes.png", "image/png"),
    "entrada-de-dados": ("dados.svg", "image/svg+xml"),
    "assistente-ia": ("IA.svg", "image/svg+xml"),
    "mapa-de-acertos": ("acertos.svg", "image/svg+xml"),
    "participacao": ("participacao.svg", "image/svg+xml"),
    "atribuir-turmas": ("atribuicao.svg", "image/svg+xml"),
}


def _icone_perfil_base64():
    """Cria um ícone de perfil para o menu lateral."""

    svg = """
    <svg xmlns="http://www.w3.org/2000/svg"
         width="24" height="24"
         viewBox="0 0 24 24"
         fill="none"
         stroke="black"
         stroke-width="1.8"
         stroke-linecap="round"
         stroke-linejoin="round">
        <circle cx="12" cy="8" r="4"/>
        <path d="M4 21v-2a8 8 0 0 1 16 0v2"/>
    </svg>
    """

    return base64.b64encode(
        svg.encode("utf-8")
    ).decode("utf-8")


def _estilos_icones():
    """Mantém todos os ícones do menu lateral brancos."""

    regras = []

    icones = dict(ICONES_MENU)

    icones["meu-perfil"] = (
        None,
        "image/svg+xml",
    )

    for identificador, (arquivo, mime) in icones.items():

        if identificador == "meu-perfil":
            conteudo = _icone_perfil_base64()
        else:
            conteudo = _icone_base64(arquivo)

        if not conteudo:
            continue

        nome = identificador.replace("-", "_")

        regras.append(
            f"""
            .st-key-menu_{nome}
            [data-testid="stPageLink-NavLink"]::before,
            .st-key-menu_ativo_{nome}
            [data-testid="stPageLink-NavLink"]::before {{
                content: "";
                display: inline-block;
                width: 25px;
                height: 25px;
                min-width: 25px;
                flex: 0 0 25px;
                margin-right: 10px;
                background-color: #ffffff;

                -webkit-mask:
                    url("data:{mime};base64,{conteudo}")
                    center / contain no-repeat;

                mask:
                    url("data:{mime};base64,{conteudo}")
                    center / contain no-repeat;
            }}
            """
        )

    st.html(
        "<style>"
        + "\n".join(regras)
        + """
        /* Esconde o ícone original preto do Meu Perfil.
           O ícone branco é desenhado acima com ::before. */

        .st-key-menu_meu_perfil
        [data-testid="stPageLink-NavLink"] svg,
        .st-key-menu_ativo_meu_perfil
        [data-testid="stPageLink-NavLink"] svg {
            display: none !important;
        }
        </style>
        """
    )


def _sair():
    """Encerra o acesso e retorna à tela de Login."""

    st.session_state["logado"] = False
    st.session_state["perfil"] = "professor"
    st.session_state["professor_atual"] = None
    st.session_state["tela_auth"] = "login"
    st.session_state["menu_mobile_aberto"] = False

    for chave in (
        "login_email",
        "login_senha",
        "login_perfil",
        "login_professor",
        "email_atual",
        "entrada_resultado",
        "access_token",
        "usuario_api",
        "papel_api",
        "sessao_api_expirada",
        "mensagem_sessao_expirada",
    ):
        st.session_state.pop(chave, None)


def _estilos_cabecalho():
    """Centraliza a escola e posiciona os botões superiores."""

    st.html(
        """
        <style>
            /* Centralização real na janela inteira. */

            .st-key-cabecalho .vertice-escola-central {
                position: fixed !important;
                top: 0.96rem !important;
                left: 50vw !important;
                transform: translateX(-50%) !important;

                width: max-content !important;
                max-width: 35vw !important;
                margin: 0 !important;
                padding: 0 !important;

                color: #ffffff !important;
                font-size: 13px !important;
                font-weight: 600 !important;
                text-align: center !important;
                white-space: nowrap;

                z-index: 1002 !important;
                pointer-events: none !important;
            }

            /* Botão Sair: mantém a posição funcional. */

            .st-key-logout_flutuante {
                position: fixed !important;
                top: 0.35rem !important;
                right: 0.55rem !important;

                width: 42px !important;
                min-width: 42px !important;
                max-width: 42px !important;

                margin: 0 !important;
                padding: 0 !important;

                z-index: 2000000 !important;
                pointer-events: auto !important;
            }

            /* Botão de perfil ao lado de Sair. */

            .st-key-perfil_flutuante {
                position: fixed !important;
                top: 0.35rem !important;
                right: 3.65rem !important;

                width: 42px !important;
                min-width: 42px !important;
                max-width: 42px !important;

                margin: 0 !important;
                padding: 0 !important;

                z-index: 2000000 !important;
                pointer-events: auto !important;
            }

            /* Aparência igual para os dois botões. */

            .st-key-logout_flutuante
            [data-testid="stButton"],
            .st-key-perfil_flutuante
            [data-testid="stButton"] {
                width: 42px !important;
                margin: 0 !important;
                padding: 0 !important;
            }

            .st-key-logout_flutuante button,
            .st-key-perfil_flutuante button {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;

                width: 42px !important;
                min-width: 42px !important;
                max-width: 42px !important;

                height: 36px !important;
                min-height: 36px !important;

                padding: 0 !important;
                margin: 0 !important;

                border: 1px solid white !important;
                border-radius: 7px !important;

                color: white !important;
                background: transparent !important;
                cursor: pointer !important;
                pointer-events: auto !important;
            }

            .st-key-logout_flutuante button:hover,
            .st-key-perfil_flutuante button:hover {
                background: rgba(
                    255, 255, 255, .15
                ) !important;
            }

            .st-key-logout_flutuante button svg,
            .st-key-perfil_flutuante button svg {
                width: 19px !important;
                height: 19px !important;
                color: white !important;
                stroke: white !important;
            }

            /* Navegação mobile continua independente. */

            .st-key-nav_mobile {
                display: none !important;
            }

            @media (max-width: 800px) {

                /* O nome da escola não aperta o cabeçalho. */

                .st-key-cabecalho
                .vertice-escola-central {
                    display: none !important;
                }

                /* Distribui os três botões no celular:
                   Perfil, Menu e Sair. */

                .st-key-perfil_flutuante {
                    right: 6.75rem !important;
                }

                .st-key-nav_mobile {
                    display: block !important;
                    position: fixed !important;

                    top: 0.35rem !important;
                    right: 3.65rem !important;

                    width: 42px !important;
                    min-width: 42px !important;
                    max-width: 42px !important;

                    margin: 0 !important;
                    padding: 0 !important;

                    z-index: 2000001 !important;
                    pointer-events: auto !important;
                }

                .st-key-nav_mobile
                [data-testid="stButton"] {
                    width: 42px !important;
                    pointer-events: auto !important;
                }

                .st-key-nav_mobile button {
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;

                    width: 42px !important;
                    height: 36px !important;
                    min-height: 36px !important;

                    margin: 0 !important;
                    padding: 0 !important;

                    border: 1px solid white !important;
                    border-radius: 7px !important;

                    color: white !important;
                    background: transparent !important;
                    cursor: pointer !important;
                    pointer-events: auto !important;
                }

                .st-key-nav_mobile button p {
                    margin: 0 !important;
                    color: white !important;
                    font-size: 20px !important;
                }

                .st-key-logout_flutuante {
                    right: 0.45rem !important;
                }
            }
        </style>
        """
    )


@st.dialog("Navegação", width="small")
def abrir_menu_mobile(paginas):
    """Mostra as páginas disponíveis no celular."""

    for pagina in paginas:
        st.page_link(
            pagina,
            use_container_width=True,
        )


def _pagina_perfil(paginas):
    """Encontra a página Meu Perfil já registrada no app."""

    for pagina in paginas or []:
        if identificar_pagina(pagina) == "meu-perfil":
            return pagina

    return None


def render_header(paginas=None):
    """Exibe o cabeçalho e os controles do sistema."""

    capelo = _icone_base64("capelo.svg")

    _estilos_cabecalho()

    with st.container(key="cabecalho"):

        col_logo, col_escola = st.columns(
            [1, 2],
            vertical_alignment="center",
            gap="small",
        )

        with col_logo:
            if capelo:
                st.html(
                    f"""
                    <div class="vertice-logo">
                        <img
                            src="data:image/svg+xml;base64,{capelo}"
                            alt="Vértice"
                        >
                        <span>{NOME_APP}</span>
                    </div>
                    """
                )
            else:
                st.markdown(f"**{NOME_APP}**")

        with col_escola:
            st.html(
                f"""
                <div class="vertice-escola-central">
                    {NOME_ESCOLA}
                </div>
                """
            )

    with st.container(key="nav_mobile"):
        if st.button(
            "☰",
            key="btn_menu_mobile",
            help="Abrir navegação",
        ):
            abrir_menu_mobile(paginas or [])

    pagina_perfil = _pagina_perfil(paginas)

    if pagina_perfil is not None:
        with st.container(key="perfil_flutuante"):
            if st.button(
                "",
                icon=":material/person_outline:",
                key="botao_perfil_cabecalho",
                help="Meu Perfil",
            ):
                st.switch_page(pagina_perfil)

    with st.container(key="logout_flutuante"):
        st.button(
            "",
            icon=":material/logout:",
            key="botao_logout",
            help="Sair do sistema",
            on_click=_sair,
        )


def render_sidebar(paginas, pagina_atual):
    """Mantém a navegação azul fixa no desktop."""

    _estilos_icones()

    atual = identificar_pagina(pagina_atual)

    with st.container(key="vertice_menu_lateral"):

        for pagina in paginas:
            identificador = identificar_pagina(pagina)

            prefixo = (
                "menu_ativo"
                if identificador == atual
                else "menu"
            )

            chave = (
                f"{prefixo}_"
                f"{identificador.replace('-', '_')}"
            )

            with st.container(key=chave):
                st.page_link(pagina)


def _titulo_e_subtitulo(titulo, subtitulo):
    """Renderiza o título e o subtítulo."""

    st.title(titulo, anchor=False)

    if subtitulo:
        st.caption(subtitulo)


def titulo_pagina(
    titulo,
    subtitulo=None,
    destaque=None,
):
    """Exibe o título padrão da página."""

    if destaque is None:
        _titulo_e_subtitulo(titulo, subtitulo)
        return

    col_titulo, col_destaque = st.columns(
        [3, 2],
        vertical_alignment="center",
    )

    with col_titulo:
        _titulo_e_subtitulo(titulo, subtitulo)

    with col_destaque:
        with st.container(key="pilula"):
            st.markdown(destaque)
