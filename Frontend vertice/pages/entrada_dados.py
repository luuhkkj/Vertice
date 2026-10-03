"""Tela: Entrada de Dados."""

import base64
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina
from utils.formatacao import numero_br


PASTA_ICONS = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "icons"
)


def _arquivo_base64(nome_arquivo):
    """Converte um arquivo de ícone em base64."""

    caminho = PASTA_ICONS / nome_arquivo

    if not caminho.exists():
        return None

    return base64.b64encode(
        caminho.read_bytes()
    ).decode("utf-8")


def _ler_arquivo(arquivo):
    """Lê CSV ou XLSX enviado pelo usuário."""

    if arquivo.name.lower().endswith(".csv"):

        try:
            return pd.read_csv(
                arquivo,
                sep=None,
                engine="python",
                encoding="utf-8-sig",
            )

        except UnicodeDecodeError:

            arquivo.seek(0)

            return pd.read_csv(
                arquivo,
                sep=None,
                engine="python",
                encoding="latin-1",
            )

    return pd.read_excel(arquivo)


def render():
    """Renderiza a tela Entrada de Dados."""

    titulo_pagina(
        "Entrada de Dados"
    )

    # Ícones
    icone_upload = _arquivo_base64(
        "download.svg"
    )

    icone_arquivo = _arquivo_base64(
        "arquivo.png"
    )

    icone_info = _arquivo_base64(
        "info.svg"
    )

    # Área de upload
    with st.container(
        key="entrada_upload"
    ):

        if icone_upload:

            st.html(
                f"""
<div class="entrada-upload-icone">
    <img
        src="data:image/svg+xml;base64,{icone_upload}"
        alt=""
    >
</div>
"""
            )

        st.html(
            """
<div class="entrada-upload-titulo">
    Importação em massa (CSV/EXCEL)
</div>

<div class="entrada-upload-instrucao">
    Arraste até aqui ou clique para selecionar
</div>
"""
        )

        arquivo = st.file_uploader(
            "Selecionar Arquivo",
            type=[
                "csv",
                "xlsx",
            ],
            label_visibility="collapsed",
            key="entrada_arquivo",
        )

    # Sem arquivo
    if arquivo is None:
        return

    # Leitura
    try:
        dados = _ler_arquivo(
            arquivo
        )

    except Exception:

        st.error(
            "Não foi possível ler o arquivo. "
            "Confira se ele é um CSV ou XLSX válido."
        )

        return

    if dados.empty:

        st.error(
            "O arquivo não possui registros."
        )

        return

    # Arquivo carregado
    nome_arquivo = escape(
        arquivo.name
    )

    quantidade_registros = numero_br(
        len(dados)
    )

    if icone_arquivo:

        html_icone_arquivo = (
            f"""
<img
    src="data:image/png;base64,{icone_arquivo}"
    alt=""
>
"""
        )

    else:

        html_icone_arquivo = ""

    with st.container(
        key="entrada_arquivo_carregado"
    ):

        st.html(
            f"""
<div class="entrada-arquivo-linha">

    <div class="entrada-arquivo-icone">
        {html_icone_arquivo}
    </div>

    <div class="entrada-arquivo-conteudo">

        <div class="entrada-arquivo-nome">
            {nome_arquivo}
        </div>

        <div class="entrada-arquivo-registros">
            {quantidade_registros} registros
        </div>

    </div>

</div>
"""
        )

    # Pré-visualização
    with st.container(
        key="entrada_preview"
    ):

        st.subheader(
            "Pré-visualização dos Dados"
        )

        st.dataframe(
            dados.head(5),
            hide_index=True,
            width="stretch",
        )

    # Informação
    if icone_info:

        html_icone_info = (
            f"""
<img
    src="data:image/svg+xml;base64,{icone_info}"
    alt=""
>
"""
        )

    else:

        html_icone_info = ""

    with st.container(
        key="entrada_info"
    ):

        st.html(
            f"""
<div class="entrada-info-linha">

    <div class="entrada-info-icone">
        {html_icone_info}
    </div>

    <div class="entrada-info-texto">
        Os dados serão utilizados para calcular indicadores
        e gerar alertas de acompanhamento.
        Não inclua nomes, CPF ou outras informações pessoais.
    </div>

</div>
"""
        )

    # Processamento
    with st.container(
        key="entrada_processar"
    ):

        if st.button(
            "Validar e processar dados",
            type="primary",
        ):

            st.success(
                "Arquivo enviado para validação e processamento."
            )