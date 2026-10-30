
"""Tela: Entrada de Dados."""

import base64
from hashlib import sha256
from html import escape
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina
from data import mock_data
from utils.formatacao import numero_br


PASTA_ICONS = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "icons"
)

COLUNAS_ESTUDANTES = [
    "Identificador",
    "Série",
    "Turma",
    "Turno",
    "Frequência",
    "Média geral",
    "Risco",
]

COLUNAS_AVALIACOES = [
    "Avaliação",
    "Disciplina",
    "Turma",
    "Identificador",
    "Questão",
    "Acertou",
]

TIPOS_IMPORTACAO = {
    "Estudantes": COLUNAS_ESTUDANTES,
    "Resultados de avaliações": COLUNAS_AVALIACOES,
}


def aplicar_responsividade():
    """Organiza a importação e seus resultados em telas menores."""

    st.html(
        """
        <style>
            /* Os componentes devem respeitar a largura da página. */

            .st-key-entrada_modelos,
            .st-key-entrada_upload,
            .st-key-entrada_arquivo_carregado,
            .st-key-entrada_preview,
            .st-key-entrada_info,
            .st-key-entrada_processar,
            .st-key-entrada_metricas,
            .st-key-entrada_resultado_tabela {
                width: 100%;
                max-width: 100%;
                min-width: 0;
                box-sizing: border-box;
            }

            /* Os botões de download mantêm a largura da coluna. */

            .st-key-entrada_modelos
            [data-testid="stDownloadButton"],
            .st-key-entrada_modelos
            [data-testid="stDownloadButton"] button {
                width: 100% !important;
            }

            /* Evita cortes em nomes longos de arquivos. */

            .st-key-entrada_arquivo_carregado
            .entrada-arquivo-linha,
            .st-key-entrada_info
            .entrada-info-linha {
                max-width: 100%;
                min-width: 0;
            }

            .st-key-entrada_arquivo_carregado
            .entrada-arquivo-conteudo,
            .st-key-entrada_info
            .entrada-info-texto {
                min-width: 0;
                overflow-wrap: anywhere;
                word-break: normal;
            }

            /* O componente de tabela não deve alargar a página. */

            .st-key-entrada_preview
            [data-testid="stDataFrame"],
            .st-key-entrada_resultado_tabela
            [data-testid="stDataFrame"] {
                width: 100% !important;
                max-width: 100% !important;
                min-width: 0 !important;
            }

            /* Tablet */

            @media (min-width: 601px) and (max-width: 1100px) {

                .st-key-entrada_modelos
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        repeat(2, minmax(0, 1fr)) !important;
                    gap: 12px !important;
                    width: 100% !important;
                }

                .st-key-entrada_modelos
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                }

                /* A terceira coluna é apenas um espaçador. */

                .st-key-entrada_modelos
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"]:nth-child(3) {
                    display: none !important;
                }
            }

            /* Celular */

            @media (max-width: 600px) {

                .st-key-entrada_modelos
                [data-testid="stHorizontalBlock"],
                .st-key-entrada_metricas
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                    gap: 10px !important;
                    width: 100% !important;
                }

                .st-key-entrada_modelos
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"],
                .st-key-entrada_metricas
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                    flex: none !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                .st-key-entrada_modelos
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"]:nth-child(3) {
                    display: none !important;
                }

                /* Upload e validação com botões largos. */

                .st-key-entrada_upload
                [data-testid="stButton"],
                .st-key-entrada_upload
                [data-testid="stButton"] button,
                .st-key-entrada_processar
                [data-testid="stButton"],
                .st-key-entrada_processar
                [data-testid="stButton"] button {
                    width: 100% !important;
                }

                /* Adapta o cartão do arquivo importado. */

                .st-key-entrada_arquivo_carregado
                .entrada-arquivo-linha {
                    gap: 10px;
                }

                .st-key-entrada_arquivo_carregado
                .entrada-arquivo-nome {
                    overflow-wrap: anywhere;
                }

                /* Mantém os avisos dentro do celular. */

                .st-key-entrada_info
                .entrada-info-texto {
                    line-height: 1.5;
                    overflow-wrap: anywhere;
                }

                /* Evita que as tabelas cortem a página. */

                .st-key-entrada_preview,
                .st-key-entrada_resultado_tabela {
                    overflow-x: auto;
                }
            }
        </style>
        """
    )


def _arquivo_base64(nome):
    """Converte um ícone local para base64."""

    caminho = PASTA_ICONS / nome

    if not caminho.exists():
        return None

    return base64.b64encode(
        caminho.read_bytes()
    ).decode("utf-8")


def _modelo(tipo):
    """Entrega somente os cabeçalhos esperados na importação."""
    return pd.DataFrame(columns=TIPOS_IMPORTACAO[tipo])


def _arquivo_modelo(tipo, formato):
    """Gera o arquivo de modelo para download."""

    dados = _modelo(tipo)

    if formato == "CSV":
        return dados.to_csv(
            index=False,
            sep=";",
        ).encode("utf-8-sig")

    saida = BytesIO()

    with pd.ExcelWriter(
        saida,
        engine="openpyxl",
    ) as escritor:
        dados.to_excel(
            escritor,
            index=False,
            sheet_name="Modelo",
        )

    return saida.getvalue()


def _ler_arquivo(conteudo_bytes, nome_arquivo):
    """Lê CSV ou Excel preservando os identificadores."""

    conteudo = BytesIO(conteudo_bytes)

    if nome_arquivo.lower().endswith(".csv"):
        try:
            return pd.read_csv(
                conteudo,
                sep=None,
                engine="python",
                encoding="utf-8-sig",
                dtype=str,
            )

        except UnicodeDecodeError:
            conteudo.seek(0)

            return pd.read_csv(
                conteudo,
                sep=None,
                engine="python",
                encoding="latin-1",
                dtype=str,
            )

    return pd.read_excel(
        conteudo,
        dtype=str,
        engine="openpyxl",
    )


def _numero(serie):
    """Aceita números escritos com ponto ou vírgula."""

    return pd.to_numeric(
        serie.astype("string")
        .str.strip()
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _validar(dados, tipo):
    """Verifica a estrutura, o preenchimento e os valores."""

    problemas = []
    esperado = TIPOS_IMPORTACAO[tipo]

    faltantes = [
        coluna
        for coluna in esperado
        if coluna not in dados.columns
    ]

    extras = [
        coluna
        for coluna in dados.columns
        if coluna not in esperado
    ]

    if faltantes:
        problemas.append({
            "Linha": "Cabeçalho",
            "Problema": (
                "Colunas ausentes: "
                + ", ".join(faltantes)
            ),
        })

    if extras:
        problemas.append({
            "Linha": "Cabeçalho",
            "Problema": (
                "Colunas não previstas: "
                + ", ".join(extras)
            ),
        })

    if problemas:
        return None, pd.DataFrame(problemas)

    dados = dados[esperado].copy()

    for coluna in esperado:
        dados[coluna] = (
            dados[coluna].astype("string").str.strip()
        )

    for indice, linha in dados.iterrows():
        vazias = [
            coluna
            for coluna in esperado
            if pd.isna(linha[coluna])
            or linha[coluna] == ""
        ]

        if vazias:
            problemas.append({
                "Linha": indice + 2,
                "Problema": (
                    "Campos vazios: "
                    + ", ".join(vazias)
                ),
            })

    if tipo == "Estudantes":
        regras = {
            "Série": mock_data.SERIES,
            "Turma": mock_data.TURMAS,
            "Turno": mock_data.TURNOS,
            "Risco": mock_data.NIVEIS_RISCO,
        }

        for coluna, permitidos in regras.items():
            if not permitidos:
                continue
            invalidos = (
                ~dados[coluna].isin(permitidos)
                & dados[coluna].notna()
            )

            for indice in dados.index[invalidos]:
                problemas.append({
                    "Linha": indice + 2,
                    "Problema": (
                        f"{coluna} fora das opções permitidas"
                    ),
                })

        for coluna, minimo, maximo in [
            ("Frequência", 0, 100),
            ("Média geral", 0, 10),
        ]:
            numeros = _numero(dados[coluna])

            invalidos = (
                numeros.isna()
                | ~numeros.between(minimo, maximo)
            )

            for indice in dados.index[invalidos]:
                problemas.append({
                    "Linha": indice + 2,
                    "Problema": (
                        f"{coluna} deve estar entre "
                        f"{minimo} e {maximo}"
                    ),
                })

            dados[coluna] = numeros

        duplicados = dados[
            "Identificador"
        ].duplicated(keep=False)

        for indice in dados.index[duplicados]:
            problemas.append({
                "Linha": indice + 2,
                "Problema": "Identificador duplicado",
            })

        if not problemas:
            dados["Status"] = dados["Risco"].map(
                mock_data.STATUS_POR_RISCO
            )

    else:
        regras = {
            "Disciplina": mock_data.DISCIPLINAS,
            "Turma": mock_data.TURMAS_ATRIBUICAO,
        }

        for coluna, permitidos in regras.items():
            if not permitidos:
                continue
            invalidos = (
                ~dados[coluna].isin(permitidos)
                & dados[coluna].notna()
            )

            for indice in dados.index[invalidos]:
                problemas.append({
                    "Linha": indice + 2,
                    "Problema": (
                        f"{coluna} fora das opções permitidas"
                    ),
                })

        for coluna in ["Questão", "Acertou"]:
            numeros = _numero(dados[coluna])

            validos = (
                numeros.notna()
                & (numeros % 1 == 0)
            )

            if coluna == "Questão":
                validos &= numeros >= 1

                mensagem = (
                    "Questão deve ser um inteiro positivo"
                )
            else:
                validos &= numeros.isin([0, 1])

                mensagem = (
                    "Acertou deve ser 0 (não) ou 1 (sim)"
                )

            for indice in dados.index[~validos]:
                problemas.append({
                    "Linha": indice + 2,
                    "Problema": mensagem,
                })

            dados[coluna] = numeros

        chaves = [
            "Avaliação",
            "Disciplina",
            "Turma",
            "Identificador",
            "Questão",
        ]

        duplicados = dados.duplicated(
            subset=chaves,
            keep=False,
        )

        for indice in dados.index[duplicados]:
            problemas.append({
                "Linha": indice + 2,
                "Problema": (
                    "Resposta duplicada para a mesma questão"
                ),
            })

        if not problemas:
            dados[["Questão", "Acertou"]] = (
                dados[["Questão", "Acertou"]].astype(int)
            )

    erros = pd.DataFrame(
        problemas,
        columns=["Linha", "Problema"],
    )

    return (
        dados if erros.empty else None,
        erros,
    )


@st.dialog("Selecionar arquivo de dados")
def _dialogo_selecionar_arquivo(tipo):
    """Abre a janela para selecionar e confirmar o arquivo."""

    st.markdown("**Envie seu arquivo CSV ou Excel**")

    st.caption(
        f"Tipo de importação: {tipo}. "
        "Tamanho máximo: 10 MB."
    )

    arquivo = st.file_uploader(
        "Escolher arquivo",
        type=["csv", "xlsx"],
        key="entrada_arquivo_modal",
    )

    if arquivo is not None:
        st.caption(
            f"Arquivo selecionado: {arquivo.name}"
        )

    if st.button(
        "Usar este arquivo",
        type="primary",
        disabled=arquivo is None,
        use_container_width=True,
        key="entrada_confirmar_arquivo",
    ):
        if arquivo.size > 10 * 1024 * 1024:
            st.error(
                "O arquivo ultrapassa o limite de 10 MB."
            )
            return

        st.session_state["entrada_arquivo_selecionado"] = {
            "nome": arquivo.name,
            "conteudo": arquivo.getvalue(),
            "tipo": tipo,
        }

        st.session_state.pop(
            "entrada_resultado",
            None,
        )

        st.session_state["entrada_tela"] = "importacao"
        st.rerun()


def _tela_resultado():
    """Apresenta o resultado da validação em tela própria."""

    resultado = st.session_state.get(
        "entrada_resultado"
    )

    if not resultado:
        st.session_state["entrada_tela"] = "importacao"
        st.rerun()
        return

    titulo_pagina("Resultado da validação")

    st.caption(
        f"Arquivo: {resultado['arquivo']}  •  "
        f"Tipo: {resultado['tipo']}"
    )

    erros = resultado["erros"]

    if erros.empty:
        st.success(
            "Arquivo validado e processado com sucesso!"
        )

        with st.container(key="entrada_metricas"):
            col_registros, col_problemas = st.columns(2)

            with col_registros:
                st.metric(
                    "Registros importados",
                    numero_br(resultado["quantidade"]),
                )

            with col_problemas:
                st.metric(
                    "Problemas encontrados",
                    "0",
                )

        st.markdown(
            "#### Prévia dos dados importados"
        )

        with st.container(key="entrada_resultado_tabela"):
            st.dataframe(
                resultado["amostra"],
                hide_index=True,
                width="stretch",
            )

        st.info(
            "Os dados foram salvos temporariamente nesta sessão. "
            "Os estudantes importados já alimentam a Visão Geral. "
            "A persistência definitiva dependerá do backend."
        )

        if resultado["tipo"] == "Resultados de avaliações":
            st.caption(
                "As respostas foram validadas e armazenadas, "
                "mas o Mapa de Acertos ainda precisa ser "
                "conectado a elas."
            )

    else:
        st.error(
            f"A validação encontrou "
            f"{numero_br(len(erros))} problema(s). "
            "Nenhum registro deste arquivo foi importado."
        )

        st.metric(
            "Registros analisados",
            numero_br(resultado["quantidade"]),
        )

        st.markdown("#### Problemas encontrados")

        with st.container(key="entrada_resultado_tabela"):
            st.dataframe(
                erros,
                hide_index=True,
                width="stretch",
            )

        st.warning(
            "Corrija as linhas indicadas no arquivo e faça "
            "uma nova importação. Dados de importações "
            "anteriores não foram apagados."
        )

    st.divider()

    if st.button(
        "← Voltar para Entrada de Dados",
        key="entrada_voltar",
        use_container_width=True,
    ):
        st.session_state["entrada_tela"] = "importacao"
        st.rerun()


def render():
    """Renderiza a importação e a tela de validação."""

    aplicar_responsividade()

    if st.session_state.get("perfil") != "administrador":
        st.error(
            "Apenas administradores podem importar dados."
        )
        return

    st.session_state.setdefault(
        "entrada_tela",
        "importacao",
    )

    if st.session_state["entrada_tela"] == "resultado":
        _tela_resultado()
        return

    titulo_pagina("Entrada de Dados")

    st.markdown(
        "**1. Escolha o tipo de dados e baixe um modelo**"
    )

    tipo = st.selectbox(
        "Tipo de importação",
        list(TIPOS_IMPORTACAO),
        key="entrada_tipo",
    )

    if st.session_state.get("entrada_tipo_anterior") != tipo:
        st.session_state["entrada_tipo_anterior"] = tipo
        st.session_state.pop(
            "entrada_arquivo_selecionado",
            None,
        )
        st.session_state.pop(
            "entrada_resultado",
            None,
        )

    nome_base = (
        "modelo_estudantes"
        if tipo == "Estudantes"
        else "modelo_resultados_avaliacoes"
    )

    with st.container(key="entrada_modelos"):
        col_csv, col_excel, _ = st.columns(
            [1, 1, 3]
        )

        with col_csv:
            st.download_button(
                "↓ Modelo CSV",
                data=_arquivo_modelo(tipo, "CSV"),
                file_name=f"{nome_base}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with col_excel:
            st.download_button(
                "↓ Modelo Excel",
                data=_arquivo_modelo(tipo, "Excel"),
                file_name=f"{nome_base}.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

    st.caption(
        "Os modelos contêm apenas os nomes das colunas. "
        "Substitua-os por dados anonimizados."
    )

    icone_upload = _arquivo_base64("download.svg")
    icone_arquivo = _arquivo_base64("arquivo.png")
    icone_info = _arquivo_base64("info.svg")

    st.markdown(
        "**2. Envie o arquivo preenchido**"
    )

    with st.container(key="entrada_upload"):
        if icone_upload:
            st.html(
                '<div class="entrada-upload-icone">'
                f'<img src="data:image/svg+xml;base64,{icone_upload}" alt="">'
                '</div>'
            )

        st.html(
            '<div class="entrada-upload-titulo">'
            'Importação em massa (CSV/EXCEL)'
            '</div>'
            '<div class="entrada-upload-instrucao">'
            'Selecione um arquivo CSV ou Excel para importar'
            '</div>'
        )

        if st.button(
            "Selecionar arquivo",
            key="entrada_abrir_selecao",
            use_container_width=True,
        ):
            _dialogo_selecionar_arquivo(tipo)

    selecionado = st.session_state.get(
        "entrada_arquivo_selecionado"
    )

    if not selecionado or selecionado.get("tipo") != tipo:
        return

    conteudo = selecionado["conteudo"]
    nome = selecionado["nome"]

    if len(conteudo) > 10 * 1024 * 1024:
        st.error(
            "O arquivo ultrapassa o limite de 10 MB."
        )
        return

    assinatura = sha256(
        conteudo + tipo.encode("utf-8")
    ).hexdigest()

    try:
        dados = _ler_arquivo(
            conteudo,
            nome,
        )
    except Exception:
        st.error(
            "Não foi possível ler o arquivo. "
            "Confira se o CSV ou XLSX é válido."
        )
        return

    if dados.empty:
        st.error(
            "O arquivo não possui registros."
        )
        return

    nome_seguro = escape(nome)

    icone_html = (
        f'<img src="data:image/png;base64,{icone_arquivo}" alt="">'
        if icone_arquivo
        else ""
    )

    with st.container(key="entrada_arquivo_carregado"):
        st.html(
            '<div class="entrada-arquivo-linha">'
            f'<div class="entrada-arquivo-icone">{icone_html}</div>'
            '<div class="entrada-arquivo-conteudo">'
            f'<div class="entrada-arquivo-nome">{nome_seguro}</div>'
            '<div class="entrada-arquivo-registros">'
            f'{numero_br(len(dados))} registros'
            '</div></div></div>'
        )

    with st.container(key="entrada_preview"):
        st.subheader(
            "Pré-visualização dos Dados"
        )

        st.dataframe(
            dados.head(5),
            hide_index=True,
            width="stretch",
        )

    icone_info_html = (
        f'<img src="data:image/svg+xml;base64,{icone_info}" alt="">'
        if icone_info
        else ""
    )

    with st.container(key="entrada_info"):
        st.html(
            '<div class="entrada-info-linha">'
            f'<div class="entrada-info-icone">{icone_info_html}</div>'
            '<div class="entrada-info-texto">'
            'Use apenas identificadores anônimos. '
            'Não inclua nomes, CPF ou outros dados pessoais. '
            'Os arquivos aprovados serão mantidos somente '
            'na sessão atual.'
            '</div></div>'
        )

    st.markdown(
        "**3. Valide os dados**"
    )

    with st.container(key="entrada_processar"):
        if st.button(
            "Validar e processar dados",
            type="primary",
            key="entrada_validar",
        ):
            validados, erros = _validar(
                dados,
                tipo,
            )

            st.session_state["entrada_resultado"] = {
                "assinatura": assinatura,
                "arquivo": nome,
                "tipo": tipo,
                "erros": erros,
                "quantidade": len(dados),
                "amostra": (
                    validados.head(5).copy()
                    if validados is not None
                    else dados.head(5).copy()
                ),
            }

            if validados is not None:
                st.session_state.setdefault(
                    "entrada_importacoes",
                    {},
                )[tipo] = validados

            st.session_state["entrada_tela"] = "resultado"
            st.rerun()
