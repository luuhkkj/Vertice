
"""Página de modelos de prova do Vértice."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina


TAMANHO_MAXIMO = 10 * 1024 * 1024

MIME_EXCEL = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


def aplicar_estilos():
    """Adapta a página ao desktop, tablet e celular."""

    st.html(
        """
        <style>
            .st-key-modelos_apresentacao,
            .st-key-modelos_cadastro,
            .st-key-modelos_lista {
                width: 100%;
                max-width: 100%;
                min-width: 0;
                box-sizing: border-box;
            }

            .st-key-modelos_cadastro
            [data-testid="stFileUploader"] {
                width: 100%;
                max-width: 100%;
            }

            .st-key-modelos_lista
            [data-testid="stHorizontalBlock"] {
                align-items: center;
            }

            .st-key-modelos_lista
            [data-testid="stColumn"] {
                min-width: 0 !important;
            }

            @media (max-width: 800px) {
                .st-key-modelos_lista
                [data-testid="stHorizontalBlock"] {
                    flex-wrap: wrap !important;
                }

                .st-key-modelos_lista
                [data-testid="stColumn"] {
                    min-width: 0 !important;
                }
            }

            @media (max-width: 600px) {
                .st-key-modelos_lista
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                    gap: 8px !important;
                    width: 100% !important;
                }

                .st-key-modelos_lista
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                    flex: none !important;
                }

                .st-key-modelos_lista button,
                .st-key-modelos_cadastro button {
                    width: 100% !important;
                }
            }
        </style>
        """
    )


@st.cache_data(show_spinner=False)
def criar_modelo_padrao():
    """Gera uma planilha padrão de avaliações, questões e respostas individuais."""

    instrucoes = pd.DataFrame(
        [
            {
                "Campo": "id_avaliacao",
                "Orientação": "Código único da avaliação (ex.: AV-MAT-2026-01).",
            },
            {
                "Campo": "titulo_avaliacao",
                "Orientação": "Nome ou título da avaliação.",
            },
            {
                "Campo": "disciplina",
                "Orientação": "Código ou nome da disciplina.",
            },
            {
                "Campo": "turma",
                "Orientação": "Turma que realizou a avaliação.",
            },
            {
                "Campo": "periodo_letivo",
                "Orientação": "Período letivo (ex.: 1º Bimestre).",
            },
            {
                "Campo": "data_avaliacao",
                "Orientação": "Data da avaliação no formato YYYY-MM-DD ou DD/MM/YYYY.",
            },
            {
                "Campo": "id_questao",
                "Orientação": "Identificador da questão (ex.: Q01, Q02).",
            },
            {
                "Campo": "tipo_questao",
                "Orientação": "FECHADA ou ABERTA.",
            },
            {
                "Campo": "valor_questao",
                "Orientação": "Peso numérico da questão (maior que zero).",
            },
            {
                "Campo": "alternativa_correta",
                "Orientação": "Gabarito da questão (A, B, C, D ou E para questões FECHADAS; vazio para ABERTAS).",
            },
            {
                "Campo": "codigo_anonimo",
                "Orientação": "Identificador anônimo do estudante (ex.: EST-001).",
            },
            {
                "Campo": "alternativa_marcada",
                "Orientação": "Alternativa escolhida pelo estudante (A, B, C, D, E ou BRANCO).",
            },
            {
                "Campo": "em_branco",
                "Orientação": "Indica se a questão foi deixada em branco (Sim/Não ou True/False).",
            },
            {
                "Campo": "nota_obtida",
                "Orientação": "Nota obtida (obrigatória para questões ABERTAS não deixadas em branco).",
            },
            {
                "Campo": "faixa_dificuldade",
                "Orientação": "Classificação da questão (Fácil, Adequada, Atenção ou Difícil).",
            },
            {
                "Campo": "topico",
                "Orientação": "Assunto ou habilidade avaliada.",
            },
        ]
    )

    questoes = pd.DataFrame(columns=[
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
    ])

    saida = BytesIO()

    with pd.ExcelWriter(
        saida,
        engine="openpyxl",
    ) as escritor:
        instrucoes.to_excel(
            escritor,
            sheet_name="Instruções",
            index=False,
        )

        questoes.to_excel(
            escritor,
            sheet_name="Questões",
            index=False,
        )

        for planilha in escritor.sheets.values():
            planilha.freeze_panes = "A2"
            planilha.auto_filter.ref = planilha.dimensions

            for coluna in planilha.columns:
                largura = max(
                    len(str(celula.value or ""))
                    for celula in coluna
                )

                letra = coluna[0].column_letter

                planilha.column_dimensions[letra].width = min(
                    max(largura + 3, 14),
                    55,
                )

    return saida.getvalue()


def obter_modelos():
    """Consulta os modelos guardados nesta sessão."""

    return st.session_state.setdefault(
        "modelos_prova_cadastrados",
        {},
    )


def validar_arquivo(arquivo):
    """Confere extensão, tamanho e leitura do arquivo."""

    if arquivo is None:
        return "Selecione um arquivo."

    if arquivo.size == 0:
        return "O arquivo está vazio."

    if arquivo.size > TAMANHO_MAXIMO:
        return "O arquivo deve ter no máximo 10 MB."

    extensao = Path(arquivo.name).suffix.lower()

    if extensao not in (".xlsx", ".csv"):
        return "Envie um arquivo Excel (.xlsx) ou CSV."

    conteudo = arquivo.getvalue()

    try:
        if extensao == ".xlsx":
            with pd.ExcelFile(
                BytesIO(conteudo),
                engine="openpyxl",
            ) as planilha:
                if not planilha.sheet_names:
                    return "O Excel não possui planilhas."
        else:
            try:
                pd.read_csv(
                    BytesIO(conteudo),
                    sep=None,
                    engine="python",
                    encoding="utf-8-sig",
                    nrows=3,
                )
            except UnicodeDecodeError:
                pd.read_csv(
                    BytesIO(conteudo),
                    sep=None,
                    engine="python",
                    encoding="latin-1",
                    nrows=3,
                )

    except Exception:
        return (
            "Não foi possível ler o arquivo. "
            "Confira se ele está válido."
        )

    return None


def cadastrar_modelo(nome, descricao, arquivo):
    """Guarda um modelo temporariamente na sessão."""

    nome = nome.strip()
    descricao = descricao.strip()

    if not nome:
        return "Informe o nome do modelo."

    erro = validar_arquivo(arquivo)

    if erro:
        return erro

    modelos = obter_modelos()
    conteudo = arquivo.getvalue()

    identificador = sha256(
        conteudo
    ).hexdigest()

    if identificador in modelos:
        return "Este arquivo já foi cadastrado."

    modelos[identificador] = {
        "nome": nome,
        "descricao": descricao,
        "arquivo": arquivo.name,
        "conteudo": conteudo,
        "tipo": Path(arquivo.name).suffix.lower(),
    }

    return None


def _modelo_padrao():
    """Mostra o modelo padrão para download."""

    with st.container(key="modelos_apresentacao"):
        with st.container(border=True):
            st.markdown("### Modelo padrão do Vértice")

            st.write(
                "Planilha de referência para organizar "
                "as questões, alternativas e o gabarito "
                "de uma avaliação."
            )

            st.caption(
                "Formato: Excel (.xlsx) • "
                "Abas: Instruções e Questões"
            )

            st.download_button(
                "↓ Baixar modelo padrão",
                data=criar_modelo_padrao(),
                file_name="modelo_prova_vertice.xlsx",
                mime=MIME_EXCEL,
                key="modelo_prova_padrao",
                use_container_width=True,
            )


def _cadastrar():
    """Permite ao administrador cadastrar modelos."""

    with st.container(key="modelos_cadastro"):
        with st.container(border=True):
            st.markdown("### Cadastrar modelo de prova")

            st.caption(
                "Adicione um modelo elaborado pela escola "
                "para disponibilizá-lo aos professores."
            )

            with st.form(
                "form_cadastro_modelo",
                clear_on_submit=True,
            ):
                nome = st.text_input(
                    "Nome do modelo",
                    placeholder="Ex.: Modelo de prova bimestral",
                )

                descricao = st.text_area(
                    "Descrição",
                    placeholder=(
                        "Informe quando o modelo deve ser usado."
                    ),
                    height=90,
                )

                arquivo = st.file_uploader(
                    "Arquivo do modelo",
                    type=["xlsx", "csv"],
                    help="Tamanho máximo: 10 MB.",
                )

                salvar = st.form_submit_button(
                    "Cadastrar modelo",
                    type="primary",
                    use_container_width=True,
                )

            if salvar:
                erro = cadastrar_modelo(
                    nome,
                    descricao,
                    arquivo,
                )

                if erro:
                    st.error(erro)
                else:
                    st.session_state["modelos_aviso"] = (
                        "Modelo cadastrado nesta sessão."
                    )
                    st.rerun()


def _listar_modelos(administrador):
    """Lista os modelos e suas ações permitidas."""

    modelos = obter_modelos()

    with st.container(key="modelos_lista"):
        st.markdown("### Modelos disponibilizados")

        if not modelos:
            st.info(
                "Ainda não há modelos adicionais cadastrados. "
                "O modelo padrão continua disponível acima."
            )
            return

        for identificador, modelo in list(modelos.items()):
            with st.container(border=True):
                col_dados, col_baixar, col_remover = st.columns(
                    [3, 1.2, 1.1],
                    gap="small",
                    vertical_alignment="center",
                )

                with col_dados:
                    st.markdown(
                        f"**{modelo['nome']}**"
                    )

                    st.caption(
                        modelo["descricao"]
                        or "Sem descrição adicional."
                    )

                    st.caption(
                        f"Arquivo: {modelo['arquivo']}"
                    )

                with col_baixar:
                    mime = (
                        MIME_EXCEL
                        if modelo["tipo"] == ".xlsx"
                        else "text/csv"
                    )

                    st.download_button(
                        "↓ Baixar",
                        data=modelo["conteudo"],
                        file_name=modelo["arquivo"],
                        mime=mime,
                        key=f"modelo_baixar_{identificador}",
                        use_container_width=True,
                    )

                with col_remover:
                    if administrador:
                        if st.button(
                            "Excluir",
                            key=f"modelo_excluir_{identificador}",
                            use_container_width=True,
                        ):
                            del modelos[identificador]

                            st.session_state["modelos_aviso"] = (
                                "Modelo excluído da sessão."
                            )

                            st.rerun()



def render():
    """Exibe os modelos conforme o perfil conectado."""

    aplicar_estilos()

    administrador = (
        st.session_state.get("perfil")
        == "administrador"
    )

    if st.button(
        "Voltar para Mapa de Acertos",
        icon=":material/arrow_back:",
        key="modelos_voltar",
    ):
        pagina = st.session_state.get(
            "pagina_mapa_acertos"
        )

        if pagina is not None:
            st.switch_page(pagina)

    st.write("")

    titulo_pagina(
        "Modelos de Prova",
        "Consulte e organize os modelos de avaliação "
        "utilizados pela escola.",
    )

    aviso = st.session_state.pop(
        "modelos_aviso",
        None,
    )

    if aviso:
        st.success(aviso)

    if administrador:
        st.caption(
            "Área do Administrador • "
            "Gerenciamento de modelos"
        )

        _modelo_padrao()
        _cadastrar()
        _listar_modelos(administrador=True)

    else:
        st.caption(
            "Área do Professor • "
            "Consulta e download de modelos"
        )

        _modelo_padrao()
        _listar_modelos(administrador=False)

    st.caption(
        "Versão demonstrativa: os modelos adicionais "
        "ficam disponíveis somente nesta sessão. "
        "O compartilhamento definitivo dependerá "
        "da integração com o backend."
    )
