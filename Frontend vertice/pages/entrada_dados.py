
"""Tela: Entrada de Dados — Importação em duas etapas, prévia, confirmação, descarte e histórico real."""

import base64
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina
from data.api_client import (
    RespostaAPI,
    baixar_modelo_importacao_api,
    confirmar_importacao_api,
    descartar_importacao_api,
    listar_importacoes_api,
    obter_previa_importacao_api,
    possui_sessao_api_ativa,
    validar_importacao_api,
)
from utils.formatacao import numero_br


PASTA_ICONS = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "icons"
)

COLUNAS_DADOS_ESCOLARES = [
    "codigo_anonimo",
    "turma",
    "disciplina",
    "ano_letivo",
    "periodo_letivo",
    "frequencia_percentual",
    "faltas",
    "media_geral",
    "nota",
    "nota_prova",
    "nota_trabalho",
    "historico_reprovacoes",
    "participacao_recuperacao",
    "situacao_final",
]

COLUNAS_OBRIGATORIAS_DADOS_ESCOLARES = (
    "codigo_anonimo",
    "turma",
    "ano_letivo",
    "periodo_letivo",
)

COLUNAS_AVALIACOES = [
    "id_avaliacao",
    "titulo_avaliacao",
    "disciplina",
    "turma",
    "periodo_letivo",
    "data_avaliacao",
    "id_questao",
    "tipo_questao",
    "valor_questao",
    "alternativa_correta",
    "codigo_anonimo",
    "alternativa_marcada",
    "em_branco",
    "nota_obtida",
    "faixa_dificuldade",
    "topico",
]

COLUNAS_ATIVIDADES = [
    "id_atividade",
    "titulo_atividade",
    "disciplina",
    "turma",
    "periodo_letivo",
    "ano_letivo",
    "data_limite",
    "nota_maxima",
    "codigo_anonimo",
    "status_entrega",
    "data_entrega",
    "nota",
]

COLUNAS_OBRIGATORIAS_ATIVIDADES = (
    "id_atividade",
    "turma",
    "codigo_anonimo",
)

# Mantido por compatibilidade com referências anteriores
COLUNAS_ESTUDANTES = COLUNAS_DADOS_ESCOLARES

COLUNAS_LEGADAS_AVALIACOES = {
    "Avaliação",
    "avaliacao",
    "Acertou",
    "acertou",
}

TIPOS_IMPORTACAO = {
    "Dados escolares": COLUNAS_DADOS_ESCOLARES,
    "Resultados de avaliações": COLUNAS_AVALIACOES,
    "Atividades": COLUNAS_ATIVIDADES,
}

MAPA_TIPO_API = {
    "Dados escolares": "dados_escolares",
    "Resultados de avaliações": "avaliacoes",
    "Atividades": "atividades",
}

MAPA_TIPO_ROTULO = {
    "dados_escolares": "Dados escolares",
    "avaliacoes": "Resultados de avaliações",
    "atividades": "Atividades",
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

    if tipo == "Resultados de avaliações" and (
        "Acertou" in dados.columns
        or "acertou" in dados.columns
    ) and "alternativa_marcada" not in dados.columns:
        problemas.append({
            "Linha": "Cabeçalho",
            "Problema": (
                "O formato da planilha de avaliações foi atualizado. "
                "O campo binário 'Acertou' não é mais aceito isoladamente; "
                "utilize o novo modelo com 'alternativa_marcada' e 'alternativa_correta'."
            ),
        })

    if tipo in ("Dados escolares", "Estudantes"):
        col_obrig = COLUNAS_OBRIGATORIAS_DADOS_ESCOLARES
        faltantes_dados = [c for c in col_obrig if c not in dados.columns]
        if faltantes_dados:
            problemas.append({
                "Linha": "Cabeçalho",
                "Problema": "Colunas obrigatórias ausentes: " + ", ".join(faltantes_dados),
            })
            return None, pd.DataFrame(problemas)

        dados = dados.copy()
        for col in dados.columns:
            dados[col] = dados[col].astype("string").str.strip()

        for indice, linha in dados.iterrows():
            vazias = [
                col for col in col_obrig
                if pd.isna(linha[col]) or linha[col] == ""
            ]
            if vazias:
                problemas.append({
                    "Linha": indice + 2,
                    "Problema": "Campos obrigatórios vazios: " + ", ".join(vazias),
                })

        anos = _numero(dados["ano_letivo"])
        for indice in dados.index[anos.isna() | ~anos.between(2000, 2100)]:
            problemas.append({
                "Linha": indice + 2,
                "Problema": "ano_letivo deve estar entre 2000 e 2100",
            })

        if "frequencia_percentual" in dados.columns:
            freqs = _numero(dados["frequencia_percentual"])
            preenchida = dados["frequencia_percentual"].notna() & (dados["frequencia_percentual"] != "")
            for indice in dados.index[preenchida & (freqs.isna() | ~freqs.between(0, 100))]:
                problemas.append({
                    "Linha": indice + 2,
                    "Problema": "frequencia_percentual deve estar entre 0 e 100",
                })

        for col_nota in ("media_geral", "nota", "nota_prova", "nota_trabalho"):
            if col_nota in dados.columns:
                notas = _numero(dados[col_nota])
                preenchida = dados[col_nota].notna() & (dados[col_nota] != "")
                for indice in dados.index[preenchida & (notas.isna() | ~notas.between(0, 10))]:
                    problemas.append({
                        "Linha": indice + 2,
                        "Problema": f"{col_nota} deve estar entre 0 e 10",
                    })

        erros = pd.DataFrame(problemas) if problemas else pd.DataFrame(columns=["Linha", "Problema"])
        return (dados if erros.empty else None), erros

    if tipo == "Atividades":
        faltantes_at = [c for c in COLUNAS_OBRIGATORIAS_ATIVIDADES if c not in dados.columns]
        if faltantes_at:
            problemas.append({
                "Linha": "Cabeçalho",
                "Problema": "Colunas obrigatórias ausentes: " + ", ".join(faltantes_at),
            })
            return None, pd.DataFrame(problemas)

        dados = dados.copy()
        for col in dados.columns:
            dados[col] = dados[col].astype("string").str.strip()

        for indice, linha in dados.iterrows():
            vazias = [
                col for col in COLUNAS_OBRIGATORIAS_ATIVIDADES
                if pd.isna(linha[col]) or linha[col] == ""
            ]
            if vazias:
                problemas.append({
                    "Linha": indice + 2,
                    "Problema": "Campos obrigatórios vazios: " + ", ".join(vazias),
                })

        if "nota_maxima" in dados.columns:
            nmax = _numero(dados["nota_maxima"])
            preenchida = dados["nota_maxima"].notna() & (dados["nota_maxima"] != "")
            for indice in dados.index[preenchida & (nmax.isna() | (nmax <= 0))]:
                problemas.append({
                    "Linha": indice + 2,
                    "Problema": "nota_maxima deve ser maior que zero",
                })

        if "nota" in dados.columns:
            nota_at = _numero(dados["nota"])
            preenchida = dados["nota"].notna() & (dados["nota"] != "")
            for indice in dados.index[preenchida & (nota_at.isna() | (nota_at < 0))]:
                problemas.append({
                    "Linha": indice + 2,
                    "Problema": "nota não pode ser negativa",
                })

        erros = pd.DataFrame(problemas) if problemas else pd.DataFrame(columns=["Linha", "Problema"])
        return (dados if erros.empty else None), erros

    # Resultados de avaliações: mantém pré-validação completa das 16 colunas e consistência de em_branco
    faltantes_av = [
        coluna
        for coluna in esperado
        if coluna not in dados.columns
    ]
    extras_av = [
        coluna
        for coluna in dados.columns
        if coluna not in esperado
    ]
    if faltantes_av:
        problemas.append({
            "Linha": "Cabeçalho",
            "Problema": "Colunas ausentes: " + ", ".join(faltantes_av),
        })
    if extras_av:
        problemas.append({
            "Linha": "Cabeçalho",
            "Problema": "Colunas não previstas: " + ", ".join(extras_av),
        })
    if problemas:
        return None, pd.DataFrame(problemas)

    dados = dados[esperado].copy()
    for coluna in esperado:
        dados[coluna] = dados[coluna].astype("string").str.strip()

    if True:
        obrigatorias_avaliacao = [
            "id_avaliacao",
            "titulo_avaliacao",
            "disciplina",
            "turma",
            "periodo_letivo",
            "data_avaliacao",
            "id_questao",
            "tipo_questao",
            "valor_questao",
            "codigo_anonimo",
        ]

        for indice, linha in dados.iterrows():
            num_linha = indice + 2
            vazias = [
                coluna
                for coluna in obrigatorias_avaliacao
                if pd.isna(linha[coluna])
                or linha[coluna] == ""
            ]
            if vazias:
                problemas.append({
                    "Linha": num_linha,
                    "Problema": (
                        "Campos obrigatórios vazios: "
                        + ", ".join(vazias)
                    ),
                })

            tipo_q = (
                str(linha["tipo_questao"] or "").strip().upper()
            )
            if tipo_q not in ("FECHADA", "ABERTA"):
                problemas.append({
                    "Linha": num_linha,
                    "Problema": (
                        "tipo_questao deve ser FECHADA ou ABERTA"
                    ),
                })

            peso_series = _numero(
                pd.Series([linha["valor_questao"]])
            )
            peso_val = peso_series.iloc[0]
            if pd.isna(peso_val) or peso_val <= 0:
                problemas.append({
                    "Linha": num_linha,
                    "Problema": (
                        "valor_questao deve ser maior que zero"
                    ),
                })

            alt_correta = (
                ""
                if pd.isna(linha["alternativa_correta"])
                else str(linha["alternativa_correta"]).strip().upper()
            )
            if alt_correta in ("NULL", "NONE", "NAN", "-"):
                alt_correta = ""

            alt_marcada = (
                ""
                if pd.isna(linha["alternativa_marcada"])
                else str(linha["alternativa_marcada"]).strip().upper()
            )
            if alt_marcada in ("NULL", "NONE", "NAN", "-"):
                alt_marcada = ""

            em_branco_txt = (
                ""
                if pd.isna(linha["em_branco"])
                else str(linha["em_branco"]).strip().lower()
            )
            if em_branco_txt in ("", "null", "none", "nan", "-"):
                em_branco_bool = None
            elif em_branco_txt in (
                "true",
                "1",
                "sim",
                "s",
                "yes",
                "y",
                "verdadeiro",
            ):
                em_branco_bool = True
            elif em_branco_txt in (
                "false",
                "0",
                "nao",
                "não",
                "n",
                "no",
                "falso",
            ):
                em_branco_bool = False
            else:
                em_branco_bool = None
                problemas.append({
                    "Linha": num_linha,
                    "Problema": (
                        "Valor booleano inválido em 'em_branco'. "
                        "Use Sim/Não, True/False ou 1/0"
                    ),
                })

            nota_series = _numero(
                pd.Series([linha["nota_obtida"]])
            )
            nota_val = nota_series.iloc[0]

            if tipo_q == "FECHADA":
                if alt_correta not in ("A", "B", "C", "D", "E"):
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            "Questão FECHADA exige alternativa_correta "
                            "entre A, B, C, D ou E"
                        ),
                    })

                if em_branco_bool is True and alt_marcada in (
                    "A",
                    "B",
                    "C",
                    "D",
                    "E",
                ):
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            "Inconsistência na questão fechada: 'em_branco' foi "
                            "marcado como verdadeiro, mas 'alternativa_marcada' "
                            f"foi preenchida com '{alt_marcada}'"
                        ),
                    })
                elif em_branco_bool is False and (
                    not alt_marcada or alt_marcada == "BRANCO"
                ):
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            "Inconsistência na questão fechada: 'em_branco' foi "
                            "indicado como falso, mas nenhuma alternativa válida (A-E) "
                            "foi informada em 'alternativa_marcada'"
                        ),
                    })
                elif em_branco_bool is True or alt_marcada == "BRANCO":
                    if not pd.isna(nota_val) and nota_val > 0:
                        problemas.append({
                            "Linha": num_linha,
                            "Problema": (
                                "Questão fechada deixada em branco não pode "
                                "ter nota_obtida positiva"
                            ),
                        })
                elif not alt_marcada:
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            "Questão FECHADA exige alternativa_marcada "
                            "(A, B, C, D, E ou BRANCO)"
                        ),
                    })
                elif alt_marcada not in ("A", "B", "C", "D", "E"):
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            f"Alternativa marcada inválida ('{alt_marcada}'). "
                            "Use A, B, C, D, E ou BRANCO"
                        ),
                    })
                else:
                    if (
                        alt_correta in ("A", "B", "C", "D", "E")
                        and alt_marcada != alt_correta
                        and not pd.isna(nota_val)
                        and nota_val > 0
                    ):
                        problemas.append({
                            "Linha": num_linha,
                            "Problema": (
                                f"A resposta marcada ('{alt_marcada}') diverge "
                                f"do gabarito ('{alt_correta}') e não pode ter "
                                "nota_obtida positiva"
                            ),
                        })
            elif tipo_q == "ABERTA":
                if alt_correta:
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            "Questão ABERTA não deve possuir "
                            "alternativa_correta"
                        ),
                    })
                if alt_marcada and alt_marcada != "BRANCO":
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            "Questão ABERTA não aceita alternativa A-E"
                        ),
                    })
                elif em_branco_bool is False and alt_marcada == "BRANCO":
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            "Inconsistência na questão aberta: 'em_branco' foi "
                            "indicado como falso, mas 'alternativa_marcada' está "
                            "como 'BRANCO'"
                        ),
                    })
                elif em_branco_bool is True or alt_marcada == "BRANCO":
                    if not pd.isna(nota_val) and nota_val > 0:
                        problemas.append({
                            "Linha": num_linha,
                            "Problema": (
                                "Questão aberta deixada em branco não pode "
                                "ter nota_obtida positiva"
                            ),
                        })
                elif pd.isna(nota_val):
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            "Questão ABERTA exige nota_obtida "
                            "quando não estiver em branco"
                        ),
                    })

            if not pd.isna(nota_val) and not pd.isna(peso_val):
                if nota_val < 0 or nota_val > peso_val:
                    problemas.append({
                        "Linha": num_linha,
                        "Problema": (
                            "nota_obtida deve estar entre 0 e valor_questao"
                        ),
                    })

        chaves = [
            "id_avaliacao",
            "disciplina",
            "turma",
            "codigo_anonimo",
            "id_questao",
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


def _papel_usuario_entrada() -> str:
    usuario = st.session_state.get("usuario_api") or {}
    return str(
        usuario.get("papel")
        or st.session_state.get("papel_api")
        or st.session_state.get("perfil")
        or "professor"
    ).strip().lower()


def enviar_validacao_importacao_api(
    nome_arquivo: str,
    conteudo_bytes: bytes,
    tipo_selecionado: Optional[str] = None,
) -> RespostaAPI:
    """Etapa 1: envia o arquivo para validação e geração de prévia sem persistência acadêmica."""
    mapa_validacao = {
        "Dados escolares": "DADOS_ESCOLARES",
        "Resultados de avaliações": "AVALIACOES",
        "Atividades": "ATIVIDADES",
    }
    tipo_api = mapa_validacao.get(tipo_selecionado or "", tipo_selecionado)
    return validar_importacao_api(
        nome_arquivo=nome_arquivo,
        conteudo_bytes=conteudo_bytes,
        tipo_importacao=tipo_api,
    )


def confirmar_lote_importacao_api(lote_id: str) -> RespostaAPI:
    """Etapa 2: confirma explicitamente um lote validado em transação atômica."""
    return confirmar_importacao_api(lote_id)


def descartar_lote_importacao_api(lote_id: str) -> RespostaAPI:
    """Descarta explicitamente um lote validado ou com erros."""
    return descartar_importacao_api(lote_id)


def carregar_historico_importacoes_api(limit: int = 30) -> RespostaAPI:
    """Carrega o histórico real de lotes visíveis no escopo do usuário autenticado."""
    return listar_importacoes_api(skip=0, limit=limit)


def _obter_conteudo_modelo_oficial(tipo: str, formato: str) -> bytes:
    """Solicita o modelo oficial do endpoint do backend ou gera localmente pelo mesmo contrato."""
    tipo_api = MAPA_TIPO_API.get(tipo, "dados_escolares")
    if possui_sessao_api_ativa():
        resp = baixar_modelo_importacao_api(tipo_api, formato=formato.lower())
        if resp.ok and isinstance(resp.dados, (bytes, bytearray)) and resp.dados:
            return bytes(resp.dados)
    return _arquivo_modelo(tipo, "CSV" if formato.upper() == "CSV" else "Excel")


def _extrair_problemas_relatorio(relatorio: dict[str, Any]) -> list[dict[str, Any]]:
    linhas_prob: list[dict[str, Any]] = []
    for col_aus in relatorio.get("colunas_ausentes") or []:
        linhas_prob.append(
            {
                "Linha": "Cabeçalho",
                "Categoria": "coluna_ausente",
                "Campo": str(col_aus),
                "Mensagem": f"Coluna obrigatória ausente: '{col_aus}'.",
            }
        )
    for col_pii in relatorio.get("colunas_proibidas_pii") or []:
        linhas_prob.append(
            {
                "Linha": "Cabeçalho",
                "Categoria": "pii_proibido",
                "Campo": str(col_pii),
                "Mensagem": f"Coluna com dado pessoal proibido (LGPD): '{col_pii}'.",
            }
        )
    for item in relatorio.get("erros") or []:
        if not isinstance(item, dict):
            continue
        linhas_prob.append(
            {
                "Linha": item.get("linha") or "Cabeçalho",
                "Categoria": item.get("categoria") or "erro",
                "Campo": item.get("campo") or "—",
                "Mensagem": item.get("mensagem") or "Erro de validação.",
            }
        )
    return linhas_prob


def _tela_lote_validado() -> None:
    """Apresenta o resultado da Etapa 1 (prévia/erros) e botões explícitos da Etapa 2."""
    lote = st.session_state.get("entrada_lote_atual")
    confirmacao = st.session_state.get("entrada_confirmacao_atual")

    if not isinstance(lote, dict):
        st.session_state["entrada_tela"] = "importacao"
        st.rerun()
        return

    titulo_pagina(
        "Prévia e Confirmação do Lote",
        "Etapa 1 concluída. Nenhum dado acadêmico é gravado até a confirmação explícita abaixo.",
    )

    lote_id = str(lote.get("id") or "")
    tipo_raw = str(lote.get("tipo_importacao") or "")
    tipo_rotulo = MAPA_TIPO_ROTULO.get(tipo_raw, tipo_raw)
    status_lote = str(lote.get("status") or "").lower()
    pode_confirmar = bool(lote.get("pode_confirmar"))
    relatorio = lote.get("relatorio_validacao") or {}

    st.caption(
        f"Lote `{lote_id}`  •  Arquivo: `{lote.get('nome_arquivo')}`  •  "
        f"Tipo: **{tipo_rotulo}**  •  Status atual: **{status_lote.upper()}**"
    )

    with st.container(key="entrada_metricas"):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total de linhas", numero_br(lote.get("total_linhas") or 0))
        c2.metric("Registros válidos", numero_br(lote.get("registros_validos") or 0))
        c3.metric("Novos", numero_br(lote.get("registros_novos") or 0))
        c4.metric("Atualizações", numero_br(lote.get("registros_existentes") or 0))
        c5.metric("Erros", numero_br(lote.get("quantidade_erros") or 0))

    if isinstance(confirmacao, dict):
        st.success(
            confirmacao.get("mensagem")
            or (
                f"Importação confirmada em transação atômica: "
                f"{confirmacao.get('registros_inseridos', 0)} inserido(s), "
                f"{confirmacao.get('registros_atualizados', 0)} atualizado(s)."
            )
        )

    turmas_id = relatorio.get("turmas_identificadas") or []
    discs_id = relatorio.get("disciplinas_identificadas") or []
    if turmas_id or discs_id:
        st.info(
            f"Turmas identificadas: {', '.join(turmas_id) or '—'}  •  "
            f"Disciplinas identificadas: {', '.join(discs_id) or '—'}"
        )

    avisos = relatorio.get("avisos") or []
    if avisos:
        with st.expander(f"Avisos da validação ({len(avisos)})", expanded=False):
            st.dataframe(pd.DataFrame(avisos), hide_index=True, width="stretch")

    problemas = _extrair_problemas_relatorio(relatorio)
    if problemas:
        st.error(
            f"Foram encontrados {len(problemas)} problema(s) impeditivo(s). "
            "Corrija o arquivo e reenvie para validação; a confirmação está bloqueada."
        )
        with st.container(key="entrada_resultado_tabela"):
            st.dataframe(pd.DataFrame(problemas), hide_index=True, width="stretch")

    previa = lote.get("previa_registros") or []
    if previa:
        st.markdown("#### Prévia dos registros validados")
        with st.container(key="entrada_preview"):
            st.dataframe(pd.DataFrame(previa).head(50), hide_index=True, width="stretch")

    st.divider()
    col_confirmar, col_descartar, col_voltar = st.columns(3)

    with col_confirmar:
        if pode_confirmar and status_lote == "validado" and not isinstance(confirmacao, dict):
            if st.button(
                "Etapa 2 — Confirmar importação",
                type="primary",
                key="entrada_btn_confirmar_lote",
                use_container_width=True,
            ):
                resp_conf = confirmar_lote_importacao_api(lote_id)
                if resp_conf.ok and isinstance(resp_conf.dados, dict):
                    st.session_state["entrada_confirmacao_atual"] = resp_conf.dados
                    lote["status"] = str(resp_conf.dados.get("status") or "confirmado")
                    lote["pode_confirmar"] = False
                    st.session_state["entrada_lote_atual"] = lote
                    st.rerun()
                else:
                    st.error(resp_conf.erro or "Não foi possível confirmar o lote no backend.")

    with col_descartar:
        if status_lote in ("validado", "com_erros") and not isinstance(confirmacao, dict):
            if st.button(
                "Descartar lote",
                key="entrada_btn_descartar_lote",
                use_container_width=True,
            ):
                resp_desc = descartar_lote_importacao_api(lote_id)
                if resp_desc.ok:
                    st.session_state.pop("entrada_lote_atual", None)
                    st.session_state.pop("entrada_confirmacao_atual", None)
                    st.session_state.pop("entrada_arquivo_selecionado", None)
                    st.session_state["entrada_tela"] = "importacao"
                    st.session_state["entrada_aviso"] = "Lote descartado com sucesso sem alterar dados acadêmicos."
                    st.rerun()
                else:
                    st.error(resp_desc.erro or "Não foi possível descartar o lote.")

    with col_voltar:
        if st.button(
            "← Voltar para Entrada de Dados",
            key="entrada_voltar",
            use_container_width=True,
        ):
            st.session_state.pop("entrada_confirmacao_atual", None)
            st.session_state["entrada_tela"] = "importacao"
            st.rerun()


def _render_historico_importacoes() -> None:
    """Aba de histórico real persistido no backend (`GET /api/v1/importacoes`)."""
    st.subheader("Histórico real de importações")
    resp_hist = carregar_historico_importacoes_api(limit=50)
    if resp_hist.sessao_expirada:
        st.warning(resp_hist.erro or "Sua sessão expirou. Faça login novamente.")
        return
    if resp_hist.sem_permissao:
        st.error(resp_hist.erro or "Permissão insuficiente para consultar lotes de importação.")
        return
    if not resp_hist.ok:
        st.error(resp_hist.erro or "Não foi possível consultar o histórico de lotes.")
        return

    lotes = resp_hist.dados if isinstance(resp_hist.dados, list) else []
    if not lotes:
        st.info("Nenhum lote de importação registrado neste escopo até o momento.")
        return

    linhas = [
        {
            "ID": str(item.get("id") or ""),
            "Arquivo": item.get("nome_arquivo") or "—",
            "Tipo": MAPA_TIPO_ROTULO.get(str(item.get("tipo_importacao") or ""), item.get("tipo_importacao")),
            "Status": str(item.get("status") or "").upper(),
            "Linhas": item.get("total_linhas") or 0,
            "Válidos": item.get("registros_validos") or 0,
            "Erros": item.get("quantidade_erros") or 0,
            "Inseridos": item.get("registros_inseridos") or 0,
            "Atualizados": item.get("registros_atualizados") or 0,
            "Enviado em": str(item.get("enviado_em") or "")[:19].replace("T", " "),
        }
        for item in lotes
        if isinstance(item, dict)
    ]
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")

    pendentes = [
        lote for lote in lotes
        if isinstance(lote, dict) and str(lote.get("status") or "").lower() in ("validado", "com_erros")
    ]
    if pendentes:
        mapa_lotes = {
            f"{lote.get('nome_arquivo')} ({str(lote.get('status')).upper()}) — {str(lote.get('id'))[:8]}": str(lote.get("id"))
            for lote in pendentes
        }
        escolha = st.selectbox(
            "Abrir lote pendente para revisão/confirmação/descarte",
            list(mapa_lotes.keys()),
            index=None,
            placeholder="Selecione um lote pendente...",
            key="entrada_hist_abrir_lote",
        )
        if escolha and st.button("Carregar prévia do lote selecionado", key="btn_hist_carregar_previa"):
            resp_prev = obter_previa_importacao_api(mapa_lotes[escolha])
            if resp_prev.ok and isinstance(resp_prev.dados, dict):
                st.session_state["entrada_lote_atual"] = resp_prev.dados
                st.session_state.pop("entrada_confirmacao_atual", None)
                st.session_state["entrada_tela"] = "resultado"
                st.rerun()
            else:
                st.error(resp_prev.erro or "Não foi possível carregar a prévia do lote.")


def render():
    """Renderiza a importação oficial em duas etapas integrada ao backend."""
    aplicar_responsividade()

    if not st.session_state.get("logado"):
        st.error("É necessário entrar no sistema.")
        return

    papel = _papel_usuario_entrada()
    if papel not in ("gestor", "professor"):
        st.error(
            "Perfis administrativos globais não importam datasets pedagógicos diretamente. "
            "Utilize uma conta de Gestor Escolar ou Professor."
        )
        return

    if not possui_sessao_api_ativa():
        st.warning("Sessão da API inativa ou expirada. Faça login novamente para importar datasets.")
        return

    st.session_state.setdefault("entrada_tela", "importacao")

    if st.session_state["entrada_tela"] == "resultado":
        _tela_lote_validado()
        return

    titulo_pagina(
        "Entrada de Dados",
        "Importação padronizada em duas etapas: validação/prévia no servidor e confirmação explícita.",
    )

    aviso = st.session_state.pop("entrada_aviso", None)
    if aviso:
        st.success(aviso)

    tab_nova, tab_historico = st.tabs(["Nova importação", "Histórico de lotes"])

    with tab_historico:
        _render_historico_importacoes()

    with tab_nova:
        st.markdown("**1. Escolha o tipo de dados e baixe o modelo oficial**")

        tipo = st.selectbox(
            "Tipo de importação",
            list(TIPOS_IMPORTACAO),
            key="entrada_tipo",
        )

        if st.session_state.get("entrada_tipo_anterior") != tipo:
            st.session_state["entrada_tipo_anterior"] = tipo
            st.session_state.pop("entrada_arquivo_selecionado", None)
            st.session_state.pop("entrada_lote_atual", None)
            st.session_state.pop("entrada_confirmacao_atual", None)

        mapa_nomes_modelo = {
            "Dados escolares": "modelo_dados_escolares",
            "Resultados de avaliações": "modelo_resultados_avaliacoes",
            "Atividades": "modelo_atividades_entregas",
        }
        nome_base = mapa_nomes_modelo.get(tipo, "modelo_vertice")

        with st.container(key="entrada_modelos"):
            col_csv, col_excel, _ = st.columns([1, 1, 3])
            with col_csv:
                st.download_button(
                    "↓ Modelo CSV",
                    data=_obter_conteudo_modelo_oficial(tipo, "CSV"),
                    file_name=f"{nome_base}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_excel:
                st.download_button(
                    "↓ Modelo Excel",
                    data=_obter_conteudo_modelo_oficial(tipo, "Excel"),
                    file_name=f"{nome_base}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        st.caption(
            "Colunas oficiais esperadas pelo validador (`"
            + "`, `".join(TIPOS_IMPORTACAO[tipo])
            + "`). Utilize sempre identificadores anônimos."
        )

        icone_upload = _arquivo_base64("download.svg")
        icone_arquivo = _arquivo_base64("arquivo.png")
        icone_info = _arquivo_base64("info.svg")

        st.markdown("**2. Envie o arquivo preenchido**")

        with st.container(key="entrada_upload"):
            if icone_upload:
                st.html(
                    '<div class="entrada-upload-icone">'
                    f'<img src="data:image/svg+xml;base64,{icone_upload}" alt="">'
                    '</div>'
                )

            st.html(
                '<div class="entrada-upload-titulo">'
                'Importação em massa (CSV/XLSX)'
                '</div>'
                '<div class="entrada-upload-instrucao">'
                'Selecione um arquivo CSV ou Excel para validar na Etapa 1'
                '</div>'
            )

            if st.button(
                "Selecionar arquivo",
                key="entrada_abrir_selecao",
                use_container_width=True,
            ):
                _dialogo_selecionar_arquivo(tipo)

        selecionado = st.session_state.get("entrada_arquivo_selecionado")
        if not selecionado or selecionado.get("tipo") != tipo:
            return

        conteudo = selecionado["conteudo"]
        nome = selecionado["nome"]

        if len(conteudo) > 10 * 1024 * 1024:
            st.error("O arquivo ultrapassa o limite de 10 MB.")
            return

        try:
            dados = _ler_arquivo(conteudo, nome)
        except Exception:
            st.error("Não foi possível ler o arquivo. Confira se o CSV ou XLSX é válido.")
            return

        if dados.empty:
            st.error("O arquivo não possui registros.")
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
            st.subheader("Amostra do arquivo enviado")
            st.dataframe(dados.head(5), hide_index=True, width="stretch")

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
                'LGPD: use apenas códigos anônimos (`codigo_anonimo`). '
                'Não inclua nomes, CPF, RG ou e-mail. A Etapa 1 apenas valida '
                'e gera a prévia no servidor sem gravar dados acadêmicos.'
                '</div></div>'
            )

        st.markdown("**3. Etapa 1 — Validar e gerar prévia no servidor**")

        with st.container(key="entrada_processar"):
            if st.button(
                "Etapa 1 — Validar no servidor",
                type="primary",
                key="entrada_validar",
            ):
                with st.spinner("Validando arquivo no servidor do Vértice..."):
                    resp_val = enviar_validacao_importacao_api(nome, conteudo, tipo)

                if resp_val.sessao_expirada:
                    st.warning(resp_val.erro or "Sua sessão expirou. Faça login novamente.")
                    return
                if resp_val.sem_permissao:
                    st.error(resp_val.erro or "Permissão insuficiente para importar este dataset.")
                    return
                if resp_val.ok and isinstance(resp_val.dados, dict):
                    st.session_state["entrada_lote_atual"] = resp_val.dados
                    st.session_state.pop("entrada_confirmacao_atual", None)
                    st.session_state["entrada_tela"] = "resultado"
                    st.rerun()
                else:
                    st.error(resp_val.erro or "Falha ao validar arquivo no servidor.")
