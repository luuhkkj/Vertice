"""Página utilitária de modelos oficiais de planilhas do Vértice."""

import streamlit as st

from components.layout import titulo_pagina
from data.api_client import baixar_modelo_importacao_api, possui_sessao_api_ativa
from pages.entrada_dados import (
    COLUNAS_ATIVIDADES,
    COLUNAS_AVALIACOES,
    COLUNAS_DADOS_ESCOLARES,
    _arquivo_modelo,
)


MODELOS_OFICIAIS = [
    {
        "titulo": "Resultados de Avaliações e Gabarito por Questão",
        "tipo_entrada": "Resultados de avaliações",
        "tipo_api": "avaliacoes",
        "nome_base": "modelo_resultados_avaliacoes",
        "colunas": COLUNAS_AVALIACOES,
        "descricao": (
            "Planilha oficial com 16 colunas para importação de avaliações, questões abertas/fechadas, "
            "gabarito (`alternativa_correta`) e respostas individuais (`alternativa_marcada`, `em_branco`, `nota_obtida`)."
        ),
    },
    {
        "titulo": "Dados Escolares, Frequência e Desempenho",
        "tipo_entrada": "Dados escolares",
        "tipo_api": "dados_escolares",
        "nome_base": "modelo_dados_escolares",
        "colunas": COLUNAS_DADOS_ESCOLARES,
        "descricao": (
            "Contrato oficial para cadastro/atualização de estudantes anonimizados (`codigo_anonimo`), "
            "boletins por período letivo, frequência, faltas, médias e notas por disciplina."
        ),
    },
    {
        "titulo": "Atividades e Registro de Entregas",
        "tipo_entrada": "Atividades",
        "tipo_api": "atividades",
        "nome_base": "modelo_atividades_entregas",
        "colunas": COLUNAS_ATIVIDADES,
        "descricao": (
            "Contrato oficial para criação/atualização de atividades e entregas (`id_atividade`, "
            "`data_limite`, `status_entrega`, `data_entrega`, `nota`)."
        ),
    },
]


def _obter_bytes_modelo(modelo: dict, formato: str) -> bytes:
    """Obtém o arquivo oficial via endpoint do backend quando conectado, ou pelo contrato local idêntico."""
    if possui_sessao_api_ativa():
        resp = baixar_modelo_importacao_api(modelo["tipo_api"], formato=formato.lower())
        if resp.ok and isinstance(resp.dados, (bytes, bytearray)) and resp.dados:
            return bytes(resp.dados)
    return _arquivo_modelo(modelo["tipo_entrada"], "CSV" if formato.upper() == "CSV" else "Excel")


def render():
    """Exibe e disponibiliza para download os 3 modelos oficiais alinhados ao validador do backend."""
    if st.button(
        "Voltar para Mapa de Acertos",
        icon=":material/arrow_back:",
        key="modelos_voltar",
    ):
        pagina = st.session_state.get("pagina_mapa_acertos")
        if pagina is not None:
            st.switch_page(pagina)

    titulo_pagina(
        "Modelos Oficiais de Planilhas",
        "Baixe os templates compatíveis com o validador de importação do backend (CSV UTF-8 ou XLSX).",
    )

    st.info(
        "Todos os modelos abaixo refletem exatamente o contrato do validador no backend (`validator.py`) "
        "e utilizam exclusivamente identificadores anônimos (`codigo_anonimo`), sem dados pessoais (LGPD)."
    )

    for idx, modelo in enumerate(MODELOS_OFICIAIS):
        with st.container(border=True):
            st.subheader(modelo["titulo"])
            st.write(modelo["descricao"])
            st.caption("Colunas oficiais: `" + "`, `".join(modelo["colunas"]) + "`")

            col_csv, col_xlsx, _ = st.columns([1, 1, 2])
            with col_csv:
                st.download_button(
                    "↓ Baixar modelo CSV",
                    data=_obter_bytes_modelo(modelo, "CSV"),
                    file_name=f"{modelo['nome_base']}.csv",
                    mime="text/csv",
                    key=f"modelo_oficial_csv_{idx}",
                    use_container_width=True,
                )
            with col_xlsx:
                st.download_button(
                    "↓ Baixar modelo XLSX",
                    data=_obter_bytes_modelo(modelo, "XLSX"),
                    file_name=f"{modelo['nome_base']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"modelo_oficial_xlsx_{idx}",
                    use_container_width=True,
                )
