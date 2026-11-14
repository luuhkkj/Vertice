"""Tela: Participação, Entregas e Acompanhamento de Estudantes (Fase 6)."""

from datetime import date, datetime
from typing import Any, Optional

import pandas as pd
import streamlit as st

from components.cards import card, card_kpi
from components.graficos import (
    grafico_barras_horizontais,
    grafico_linha,
)
from components.layout import titulo_pagina
from components.tabelas import tabela_paginada
from data.api_client import (
    atualizar_atividade_api,
    atualizar_entrega_por_id_api,
    consultar_indicadores_participacao,
    criar_atividade_api,
    gerar_entregas_esperadas_api,
    listar_acompanhamentos_api,
    listar_atividades_api,
    listar_atribuicoes_api,
    listar_disciplinas_api,
    listar_entregas_atividade_api,
    listar_turmas_api,
    possui_sessao_api_ativa,
    registrar_acompanhamento_pedagogico_api,
    registrar_entrega_atividade_api,
)
from utils.formatacao import (
    decimal_br,
    numero_br,
    percentual_br,
)


ROTULOS_STATUS_ENTREGA: dict[str, str] = {
    "ENTREGUE": "Entregue no prazo",
    "ATRASADO": "Entregue com atraso",
    "PENDENTE": "Pendente (no prazo)",
    "NAO_ENTREGUE": "Não entregue",
}

ROTULOS_STATUS_ATIVIDADE: dict[str, str] = {
    "ABERTA": "Aberta",
    "ENCERRADA": "Encerrada",
    "ARQUIVADA": "Arquivada",
}


def aplicar_responsividade() -> None:
    """Organiza a tela de Participação em diferentes larguras de viewport."""
    st.html(
        """
        <style>
            .st-key-participacao_cabecalho,
            .st-key-participacao_filtros,
            .st-key-participacao_indicadores,
            .st-key-participacao_graficos,
            .st-key-participacao_detalhes,
            .st-key-participacao_acoes {
                width: 100%;
                max-width: 100%;
                min-width: 0;
                box-sizing: border-box;
            }

            .st-key-participacao_cabecalho [data-testid="column"],
            .st-key-participacao_filtros [data-testid="column"],
            .st-key-participacao_indicadores [data-testid="column"],
            .st-key-participacao_graficos [data-testid="column"],
            .st-key-participacao_acoes [data-testid="column"] {
                min-width: 0 !important;
            }

            .st-key-participacao_detalhes [data-testid="stDataFrame"] {
                width: 100% !important;
                max-width: 100% !important;
                min-width: 0 !important;
            }

            @media (min-width: 601px) and (max-width: 1100px) {
                .st-key-participacao_filtros [data-testid="stHorizontalBlock"],
                .st-key-participacao_indicadores [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
                    gap: 12px !important;
                }

                .st-key-participacao_graficos [data-testid="stHorizontalBlock"] {
                    display: flex !important;
                    flex-direction: column !important;
                    gap: 12px !important;
                }

                .st-key-participacao_graficos [data-testid="column"] {
                    width: 100% !important;
                    flex: none !important;
                }
            }

            @media (max-width: 600px) {
                .st-key-participacao_cabecalho [data-testid="stHorizontalBlock"] {
                    gap: 12px !important;
                }

                .st-key-participacao_cabecalho [data-testid="column"]:first-child {
                    flex: 1 1 0 !important;
                    width: auto !important;
                }

                .st-key-participacao_cabecalho [data-testid="column"]:last-child {
                    flex: 0 0 auto !important;
                    width: fit-content !important;
                    max-width: 100% !important;
                }

                .st-key-participacao_cabecalho .stButton,
                .st-key-participacao_cabecalho .stButton button {
                    width: auto !important;
                }
            }
        </style>
        """
    )


def _formatar_data_br(valor: Any) -> str:
    """Converte data ISO (`YYYY-MM-DD`) ou `date` para `DD/MM/YYYY`."""
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    texto = str(valor).strip()
    if not texto:
        return "—"
    try:
        return datetime.fromisoformat(texto[:10]).date().strftime("%d/%m/%Y")
    except ValueError:
        return texto


def _parse_date(valor: Any) -> Optional[date]:
    if valor is None or valor == "":
        return None
    if isinstance(valor, date):
        return valor
    try:
        return datetime.fromisoformat(str(valor).strip()[:10]).date()
    except ValueError:
        return None


def validar_coerencia_entrega_frontend(
    *,
    data_limite: date,
    data_entrega: Optional[date],
    status_informado: Optional[str],
    nota: Optional[float] = None,
    nota_maxima: Optional[float] = None,
    hoje: Optional[date] = None,
) -> Optional[str]:
    """
    Valida no frontend a coerência entre `data_entrega`, `data_limite`, `status_entrega`
    e `nota`, espelhando as regras estritas do backend (Bloco E).
    Retorna `None` se válido ou mensagem de erro amigável.
    """
    ref_hoje = hoje or date.today()

    if nota is not None:
        if nota < 0:
            return "A nota informada não pode ser negativa."
        if nota_maxima is not None and nota > nota_maxima:
            return (
                f"A nota ({decimal_br(nota, 1)}) excede a nota máxima da atividade "
                f"({decimal_br(nota_maxima, 1)})."
            )

    if not status_informado:
        return None

    st_limpo = str(status_informado).strip().upper()
    if data_entrega is not None:
        if st_limpo in ("PENDENTE", "NAO_ENTREGUE"):
            return (
                f"Com data de entrega preenchida, não é permitido selecionar o status '{st_limpo}'."
            )
        esperado = "ENTREGUE" if data_entrega <= data_limite else "ATRASADO"
        if st_limpo != esperado:
            return (
                f"Para entrega em {_formatar_data_br(data_entrega)} (limite {_formatar_data_br(data_limite)}), "
                f"o status compatível é '{esperado}'."
            )
        return None

    # Sem data_entrega
    if st_limpo in ("ENTREGUE", "ATRASADO"):
        return f"O status '{st_limpo}' exige o preenchimento da data de entrega."

    esperado_sem_entrega = "PENDENTE" if ref_hoje <= data_limite else "NAO_ENTREGUE"
    if st_limpo != esperado_sem_entrega:
        if st_limpo == "PENDENTE":
            return (
                f"Não é permitido marcar 'PENDENTE' após o vencimento da data limite "
                f"({_formatar_data_br(data_limite)}) sem data de entrega."
            )
        return (
            f"Não é permitido marcar 'NAO_ENTREGUE' antes do vencimento da data limite "
            f"({_formatar_data_br(data_limite)})."
        )

    return None


def carregar_contexto_participacao_api() -> dict[str, Any]:
    """Carrega turmas, disciplinas, atribuições e atividades reais da API."""
    contexto: dict[str, Any] = {
        "conectado": False,
        "sessao_expirada": False,
        "sem_permissao": False,
        "erro_comunicacao": None,
        "turmas": [],
        "disciplinas": [],
        "atribuicoes": [],
        "atividades": [],
    }

    if st.session_state.get("sessao_api_expirada"):
        contexto["sessao_expirada"] = True
        contexto["erro_comunicacao"] = st.session_state.get(
            "mensagem_sessao_expirada",
            "Sua sessão expirou. Faça login novamente.",
        )
        return contexto

    if not possui_sessao_api_ativa():
        return contexto

    resp_turmas = listar_turmas_api()
    resp_disc = listar_disciplinas_api()
    resp_atrib = listar_atribuicoes_api()
    resp_ativ = listar_atividades_api()

    for r in (resp_turmas, resp_disc, resp_atrib, resp_ativ):
        if r.sessao_expirada:
            contexto["sessao_expirada"] = True
            contexto["erro_comunicacao"] = r.erro
            return contexto
        if r.sem_permissao:
            contexto["sem_permissao"] = True
            contexto["erro_comunicacao"] = r.erro
            return contexto
        if not r.ok:
            contexto["erro_comunicacao"] = r.erro
            return contexto

    contexto["conectado"] = True
    contexto["turmas"] = resp_turmas.dados if isinstance(resp_turmas.dados, list) else []
    contexto["disciplinas"] = resp_disc.dados if isinstance(resp_disc.dados, list) else []
    contexto["atribuicoes"] = resp_atrib.dados if isinstance(resp_atrib.dados, list) else []
    contexto["atividades"] = resp_ativ.dados if isinstance(resp_ativ.dados, list) else []
    return contexto


def montar_resumo_indicadores_participacao(
    indicadores: Optional[dict[str, Any]],
) -> dict[str, str]:
    """
    Formata os KPIs vindos exclusivamente do backend (`/indicadores/participacao`),
    preservando `—` quando o denominador for zero ou não houver notas disponíveis.
    """
    if not isinstance(indicadores, dict):
        return {
            "taxa_entrega": "—",
            "realizadas_vs_esperadas": "0 / 0",
            "no_prazo": "0",
            "atrasadas": "0",
            "nao_entregues": "0",
            "pendentes": "0",
            "media_notas": "—",
        }

    esperadas = int(indicadores.get("total_entregas_esperadas") or 0)
    realizadas = int(indicadores.get("entregas_realizadas") or 0)
    no_prazo = int(indicadores.get("entregas_no_prazo") or 0)
    atrasadas = int(indicadores.get("entregas_atrasadas") or 0)
    nao_entregues = int(indicadores.get("nao_entregas_apos_prazo") or 0)
    pendentes = int(indicadores.get("atividades_pendentes_antes_prazo") or 0)

    taxa_raw = indicadores.get("taxa_entrega_geral_percentual")
    media_raw = indicadores.get("media_notas_disponiveis")

    return {
        "taxa_entrega": (
            percentual_br(float(taxa_raw), casas=1) if taxa_raw is not None else "—"
        ),
        "realizadas_vs_esperadas": (
            f"{numero_br(realizadas)} / {numero_br(esperadas)}"
        ),
        "no_prazo": numero_br(no_prazo),
        "atrasadas": numero_br(atrasadas),
        "nao_entregues": numero_br(nao_entregues),
        "pendentes": numero_br(pendentes),
        "media_notas": (
            decimal_br(float(media_raw), casas=1) if media_raw is not None else "—"
        ),
    }


def formatar_tabela_entregas_atividade(
    entregas: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    Constrói a tabela de acompanhamento das entregas esperadas e realizadas
    mantendo anonimização estrita e preservando notas ausentes como `—`.
    """
    linhas: list[dict[str, Any]] = []
    for ent in entregas:
        status_raw = str(ent.get("status_entrega") or "")
        atraso_flag = bool(ent.get("em_atraso"))
        dias_atraso = int(ent.get("dias_atraso") or 0)
        if atraso_flag and dias_atraso > 0:
            sit_atraso = f"Sim ({dias_atraso}d)"
        elif atraso_flag:
            sit_atraso = "Sim"
        else:
            sit_atraso = "Não"

        nota_val = ent.get("nota")
        nota_max_val = ent.get("nota_maxima")

        linhas.append(
            {
                "Código": ent.get("codigo_anonimo") or "—",
                "Status": ROTULOS_STATUS_ENTREGA.get(status_raw, status_raw or "—"),
                "Data limite": _formatar_data_br(ent.get("data_limite")),
                "Data de entrega": _formatar_data_br(ent.get("data_entrega")),
                "Nota obtida": (
                    decimal_br(float(nota_val), casas=1)
                    if nota_val is not None
                    else "—"
                ),
                "Nota máxima": (
                    decimal_br(float(nota_max_val), casas=1)
                    if nota_max_val is not None
                    else "—"
                ),
                "Em atraso": sit_atraso,
            }
        )
    return pd.DataFrame(linhas)


def montar_historico_turma_df(
    indicadores: Optional[dict[str, Any]],
) -> pd.DataFrame:
    """Extrai a tabela de histórico de atividades e taxas de participação da turma."""
    if not isinstance(indicadores, dict):
        return pd.DataFrame()
    itens = indicadores.get("taxa_por_atividade") or []
    linhas: list[dict[str, Any]] = []
    for item in itens:
        taxa = item.get("taxa_entrega_percentual")
        media = item.get("media_notas_disponiveis")
        linhas.append(
            {
                "Código": item.get("codigo") or "—",
                "Atividade": item.get("titulo") or "—",
                "Turma": item.get("turma_nome") or "—",
                "Disciplina": item.get("disciplina_codigo") or "—",
                "Período": item.get("periodo_letivo") or "—",
                "Data limite": _formatar_data_br(item.get("data_limite")),
                "Esperadas": int(item.get("total_entregas_esperadas") or 0),
                "Entregues": int(item.get("entregas_realizadas") or 0),
                "No prazo": int(item.get("entregas_no_prazo") or 0),
                "Atrasadas": int(item.get("entregas_atrasadas") or 0),
                "Pendentes": int(item.get("pendentes_antes_prazo") or 0),
                "Não entregues": int(item.get("nao_entregas_apos_prazo") or 0),
                "Taxa entrega": (
                    percentual_br(float(taxa), casas=1) if taxa is not None else "—"
                ),
                "Média notas": (
                    decimal_br(float(media), casas=1) if media is not None else "—"
                ),
            }
        )
    return pd.DataFrame(linhas)


def _opcoes_turmas_disciplinas_autorizadas(
    contexto_api: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Filtra turmas e disciplinas respeitando as atribuições do usuário autenticado."""
    turmas = list(contexto_api.get("turmas") or [])
    disciplinas = list(contexto_api.get("disciplinas") or [])
    atribuicoes = list(contexto_api.get("atribuicoes") or [])

    usuario_api = st.session_state.get("usuario_api") or {}
    papel_api = str(
        usuario_api.get("papel")
        or st.session_state.get("papel_api")
        or "professor"
    ).lower()

    if papel_api == "professor" and atribuicoes:
        ids_turmas_atrib = {str(a.get("turma_id")) for a in atribuicoes if a.get("turma_id")}
        ids_disc_atrib = {
            str(a.get("disciplina_id"))
            for a in atribuicoes
            if a.get("disciplina_id")
        }
        if ids_turmas_atrib:
            turmas = [t for t in turmas if str(t.get("id")) in ids_turmas_atrib]
        if ids_disc_atrib:
            disciplinas = [d for d in disciplinas if str(d.get("id")) in ids_disc_atrib]

    return turmas, disciplinas


@st.dialog("Nova atividade")
def _abrir_dialog_nova_atividade(
    turmas: list[dict[str, Any]],
    disciplinas: list[dict[str, Any]],
) -> None:
    """Modal para criação de nova atividade com geração transacional de entregas esperadas."""
    if not turmas or not disciplinas:
        st.warning(
            "É necessário possuir pelo menos uma turma e uma disciplina autorizadas para cadastrar atividades."
        )
        return

    mapa_turmas = {
        f"{t.get('nome')} ({t.get('ano_letivo', '')})": str(t.get("id"))
        for t in turmas
        if t.get("id")
    }
    mapa_discs = {
        f"{d.get('nome')} ({d.get('codigo')})": str(d.get("id"))
        for d in disciplinas
        if d.get("id")
    }

    with st.form("form_nova_atividade_fase6"):
        codigo = st.text_input(
            "Código da atividade",
            placeholder="Ex.: ATIV-MAT-01",
            help="Identificador único da atividade na turma e disciplina.",
        )
        titulo = st.text_input(
            "Título da atividade",
            placeholder="Ex.: Lista de Exercícios 01",
        )
        col1, col2 = st.columns(2)
        with col1:
            turma_rotulo = st.selectbox("Turma", list(mapa_turmas.keys()))
            periodo_letivo = st.text_input(
                "Período letivo",
                value="1º Bimestre",
            )
            data_limite = st.date_input("Data limite", value=date.today())
        with col2:
            disc_rotulo = st.selectbox("Disciplina", list(mapa_discs.keys()))
            usar_nota_maxima = st.checkbox("Definir nota máxima", value=True)
            nota_maxima = st.number_input(
                "Nota máxima",
                min_value=0.1,
                max_value=100.0,
                value=10.0,
                step=0.5,
                disabled=not usar_nota_maxima,
            )
            status_inicial = st.selectbox(
                "Status inicial",
                ["ABERTA", "ENCERRADA", "ARQUIVADA"],
                format_func=lambda s: ROTULOS_STATUS_ATIVIDADE.get(s, s),
            )

        gerar_esperadas = st.checkbox(
            "Gerar automaticamente entregas esperadas para os estudantes elegíveis da turma",
            value=True,
        )

        enviado = st.form_submit_button("Cadastrar atividade", type="primary")
        if enviado:
            if not codigo.strip() or not titulo.strip() or not periodo_letivo.strip():
                st.error("Preencha código, título e período letivo da atividade.")
                return

            resp = criar_atividade_api(
                codigo=codigo.strip(),
                titulo=titulo.strip(),
                turma_id=mapa_turmas[turma_rotulo],
                disciplina_id=mapa_discs[disc_rotulo],
                periodo_letivo=periodo_letivo.strip(),
                data_limite=data_limite.isoformat(),
                nota_maxima=float(nota_maxima) if usar_nota_maxima else None,
                status=status_inicial,
                gerar_entregas_esperadas=gerar_esperadas,
            )
            if resp.ok:
                st.success("Atividade cadastrada com sucesso no backend.")
                st.rerun()
            else:
                st.error(resp.erro or "Falha ao cadastrar atividade.")


def _renderizar_aba_entregas_atividade(
    atividade_sel: Optional[dict[str, Any]],
) -> None:
    """Bloco B & C: Gestão da atividade selecionada e registro/consulta de entregas esperadas."""
    if atividade_sel is None:
        st.info(
            "Nenhuma atividade encontrada para os filtros selecionados. "
            "Clique em '+ Inserir atividade' para cadastrar a primeira."
        )
        return

    atividade_id = str(atividade_sel.get("id"))
    prazo_at = _parse_date(atividade_sel.get("data_limite")) or date.today()
    nota_max_at = atividade_sel.get("nota_maxima")

    col_info, col_gerir = st.columns([1.4, 1], gap="medium")
    with col_info:
        with card(
            f"{atividade_sel.get('codigo')} • {atividade_sel.get('titulo')}",
            subtitulo=(
                f"Turma: {atividade_sel.get('turma_nome') or '—'} | "
                f"Disciplina: {atividade_sel.get('disciplina_codigo') or '—'} | "
                f"Período: {atividade_sel.get('periodo_letivo') or '—'}"
            ),
        ):
            st.write(
                f"**Data limite:** {_formatar_data_br(prazo_at)}  •  "
                f"**Nota máxima:** {decimal_br(float(nota_max_at), 1) if nota_max_at is not None else 'Sem nota atribuída'}  •  "
                f"**Status:** {ROTULOS_STATUS_ATIVIDADE.get(str(atividade_sel.get('status')), str(atividade_sel.get('status')))}"
            )
            if st.button(
                "Atualizar / Gerar entregas esperadas da turma",
                key=f"btn_gerar_entregas_{atividade_id}",
                help="Gera de forma idempotente as entregas esperadas para estudantes elegíveis sem duplicar registros existentes.",
            ):
                resp_gen = gerar_entregas_esperadas_api(atividade_id)
                if resp_gen.ok and isinstance(resp_gen.dados, dict):
                    st.success(resp_gen.dados.get("mensagem") or "Entregas sincronizadas.")
                    st.rerun()
                else:
                    st.error(resp_gen.erro or "Erro ao gerar entregas esperadas.")

    with col_gerir:
        with st.expander("Editar atividade / alterar data limite", expanded=False):
            periodo_atual = str(atividade_sel.get("periodo_letivo") or "")
            with st.form(f"form_editar_ativ_{atividade_id}"):
                novo_titulo = st.text_input(
                    "Título",
                    value=str(atividade_sel.get("titulo") or ""),
                )
                novo_periodo = st.text_input(
                    "Período letivo",
                    value=periodo_atual,
                    help="O período letivo somente pode ser alterado enquanto não houver entregas esperadas/registradas.",
                )
                novo_prazo = st.date_input("Nova data limite", value=prazo_at)
                novo_status = st.selectbox(
                    "Status da atividade",
                    ["ABERTA", "ENCERRADA", "ARQUIVADA"],
                    index=(
                        ["ABERTA", "ENCERRADA", "ARQUIVADA"].index(
                            str(atividade_sel.get("status") or "ABERTA").upper()
                        )
                        if str(atividade_sel.get("status") or "ABERTA").upper()
                        in ("ABERTA", "ENCERRADA", "ARQUIVADA")
                        else 0
                    ),
                    format_func=lambda s: ROTULOS_STATUS_ATIVIDADE.get(s, s),
                )
                if st.form_submit_button("Salvar alterações da atividade"):
                    periodo_envio = (
                        novo_periodo.strip()
                        if novo_periodo.strip() != periodo_atual.strip()
                        else None
                    )
                    resp_upd = atualizar_atividade_api(
                        atividade_id=atividade_id,
                        titulo=novo_titulo,
                        periodo_letivo=periodo_envio,
                        data_limite=novo_prazo.isoformat(),
                        status=novo_status,
                    )
                    if resp_upd.ok:
                        st.success(
                            "Atividade atualizada. Registros pendentes sem entrega foram reconciliados com o novo prazo."
                        )
                        st.rerun()
                    else:
                        st.error(resp_upd.erro or "Não foi possível atualizar a atividade.")

    resp_entregas = listar_entregas_atividade_api(atividade_id)
    if not resp_entregas.ok:
        st.error(resp_entregas.erro or "Erro ao consultar entregas da atividade.")
        return

    entregas = resp_entregas.dados if isinstance(resp_entregas.dados, list) else []

    with st.container(key="participacao_detalhes"):
        if not entregas:
            st.warning(
                "Esta atividade ainda não possui entregas esperadas registradas. "
                "Clique em 'Atualizar / Gerar entregas esperadas da turma' acima."
            )
        else:
            df_entregas = formatar_tabela_entregas_atividade(entregas)
            tabela_paginada(
                df_entregas,
                chave=f"part_entregas_{atividade_id}",
                titulo="Lista de entregas esperadas e realizadas (estudantes anonimizados)",
                itens_por_pagina=12,
            )

    if entregas:
        with st.expander("Registrar ou atualizar entrega de estudante", expanded=True):
            opcoes_est = {
                f"{e.get('codigo_anonimo')} ({ROTULOS_STATUS_ENTREGA.get(str(e.get('status_entrega')), str(e.get('status_entrega')))})": e
                for e in entregas
            }
            rotulo_sel = st.selectbox(
                "Estudante (código anonimizado)",
                list(opcoes_est.keys()),
                key=f"sel_est_entrega_{atividade_id}",
            )
            entrega_atual = opcoes_est[rotulo_sel]
            data_ent_atual = _parse_date(entrega_atual.get("data_entrega"))
            nota_atual = entrega_atual.get("nota")

            with st.form(f"form_reg_entrega_{atividade_id}"):
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    possui_data = st.checkbox(
                        "Registrar entrega efetivada (informar data)",
                        value=data_ent_atual is not None,
                    )
                    data_informada = st.date_input(
                        "Data efetiva da entrega",
                        value=data_ent_atual or date.today(),
                    )
                with col_f2:
                    possui_nota = st.checkbox(
                        "Informar nota",
                        value=nota_atual is not None,
                    )
                    max_permitida = float(nota_max_at) if nota_max_at is not None else 100.0
                    nota_informada = st.number_input(
                        "Nota obtida",
                        min_value=0.0,
                        max_value=max_permitida,
                        value=float(nota_atual) if nota_atual is not None else 0.0,
                        step=0.5,
                    )
                with col_f3:
                    opcoes_status = [
                        "AUTOMATICO",
                        "ENTREGUE",
                        "ATRASADO",
                        "PENDENTE",
                        "NAO_ENTREGUE",
                    ]
                    status_escolha = st.selectbox(
                        "Status da entrega",
                        opcoes_status,
                        format_func=lambda s: (
                            "Calcular automaticamente pela data"
                            if s == "AUTOMATICO"
                            else ROTULOS_STATUS_ENTREGA.get(s, s)
                        ),
                    )

                if st.form_submit_button("Salvar entrega", type="primary"):
                    data_enviar = data_informada if possui_data else None
                    nota_enviar = float(nota_informada) if possui_nota else None
                    status_enviar = (
                        None if status_escolha == "AUTOMATICO" else status_escolha
                    )

                    erro_val = validar_coerencia_entrega_frontend(
                        data_limite=prazo_at,
                        data_entrega=data_enviar,
                        status_informado=status_enviar,
                        nota=nota_enviar,
                        nota_maxima=(
                            float(nota_max_at) if nota_max_at is not None else None
                        ),
                    )
                    if erro_val:
                        st.error(erro_val)
                    else:
                        entrega_id = entrega_atual.get("id")
                        if entrega_id:
                            resp_save = atualizar_entrega_por_id_api(
                                entrega_id=str(entrega_id),
                                data_entrega=(
                                    data_enviar.isoformat() if data_enviar else None
                                ),
                                nota=nota_enviar,
                                status_entrega=status_enviar,
                                incluir_data_entrega=True,
                                incluir_nota=True,
                            )
                        else:
                            resp_save = registrar_entrega_atividade_api(
                                atividade_id=atividade_id,
                                estudante_id=str(entrega_atual.get("estudante_id")),
                                data_entrega=(
                                    data_enviar.isoformat() if data_enviar else None
                                ),
                                nota=nota_enviar,
                                status_entrega=status_enviar,
                                incluir_nota=True,
                            )
                        if resp_save.ok:
                            st.success("Registro de entrega salvo com sucesso.")
                            st.rerun()
                        else:
                            st.error(resp_save.erro or "Falha ao salvar entrega.")


def _renderizar_aba_historico_turma(
    indicadores: Optional[dict[str, Any]],
) -> None:
    """Blocos F e G: Visão consolidada por atividade, por turma e evolução temporal."""
    if not isinstance(indicadores, dict) or not indicadores.get("taxa_por_atividade"):
        st.info("Ainda não há histórico de atividades para os filtros selecionados.")
        return

    df_atividades = montar_historico_turma_df(indicadores)

    with st.container(key="participacao_graficos"):
        col_g1, col_g2 = st.columns(2, gap="medium")
        with col_g1:
            df_taxa = pd.DataFrame(
                [
                    {
                        "Atividade": f"{item.get('codigo')} — {item.get('titulo')}",
                        "Taxa de entrega (%)": float(item["taxa_entrega_percentual"]),
                    }
                    for item in (indicadores.get("taxa_por_atividade") or [])
                    if item.get("taxa_entrega_percentual") is not None
                ]
            )
            with card("Taxa de entrega por atividade (%)"):
                if df_taxa.empty:
                    st.info("Sem atividades com entregas esperadas calculadas.")
                else:
                    st.plotly_chart(
                        grafico_barras_horizontais(
                            df_taxa,
                            x="Taxa de entrega (%)",
                            y="Atividade",
                        ),
                        use_container_width=True,
                    )

        with col_g2:
            ev_itens = indicadores.get("evolucao_participacao") or []
            df_ev = pd.DataFrame(
                [
                    {
                        "Data / Período": (
                            f"{_formatar_data_br(ev.get('data_referencia'))} ({ev.get('periodo_letivo')})"
                        ),
                        "Taxa de entrega (%)": float(ev["taxa_entrega_percentual"]),
                    }
                    for ev in ev_itens
                    if ev.get("taxa_entrega_percentual") is not None
                ]
            )
            with card("Evolução da participação ao longo dos prazos"):
                if df_ev.empty:
                    st.info("Sem pontos suficientes para série temporal de evolução.")
                else:
                    st.plotly_chart(
                        grafico_linha(df_ev, x="Data / Período", y="Taxa de entrega (%)"),
                        use_container_width=True,
                    )

    tabela_paginada(
        df_atividades,
        chave="part_historico_turma",
        titulo="Histórico de participação por atividade e turma",
        itens_por_pagina=10,
    )

    turma_itens = indicadores.get("taxa_por_turma") or []
    if turma_itens:
        df_turmas = pd.DataFrame(
            [
                {
                    "Turma": t.get("turma_nome") or "—",
                    "Atividades": int(t.get("total_atividades") or 0),
                    "Esperadas": int(t.get("total_entregas_esperadas") or 0),
                    "Entregues": int(t.get("entregas_realizadas") or 0),
                    "Atrasadas": int(t.get("entregas_atrasadas") or 0),
                    "Pendentes": int(t.get("pendentes_antes_prazo") or 0),
                    "Não entregues": int(t.get("nao_entregas_apos_prazo") or 0),
                    "Taxa turma": (
                        percentual_br(float(t["taxa_entrega_percentual"]), 1)
                        if t.get("taxa_entrega_percentual") is not None
                        else "—"
                    ),
                    "Média notas": (
                        decimal_br(float(t["media_notas_disponiveis"]), 1)
                        if t.get("media_notas_disponiveis") is not None
                        else "—"
                    ),
                }
                for t in turma_itens
            ]
        )
        tabela_paginada(
            df_turmas,
            chave="part_resumo_turmas",
            titulo="Consolidação por turma",
            itens_por_pagina=10,
        )


def _renderizar_aba_historico_individual(
    indicadores: Optional[dict[str, Any]],
    atividades_filtradas: list[dict[str, Any]],
    turma_id_filtro: Optional[str],
    disciplina_id_filtro: Optional[str],
    periodo_filtro: Optional[str],
) -> None:
    """Bloco G: Histórico individual anonimizado do estudante com evolução por período."""
    estudantes = (
        (indicadores.get("percentual_por_estudante") or [])
        if isinstance(indicadores, dict)
        else []
    )
    if not estudantes:
        st.info(
            "Nenhum estudante esperado encontrado para o recorte atual de participação."
        )
        return

    mapa_est = {
        str(e.get("codigo_anonimo")): e
        for e in estudantes
        if e.get("estudante_id") and e.get("codigo_anonimo")
    }
    if not mapa_est:
        st.info("Sem estudantes anonimizados disponíveis.")
        return

    codigo_sel = st.selectbox(
        "Selecionar estudante (código anonimizado)",
        sorted(mapa_est.keys()),
        key="part_est_individual_codigo",
    )
    est_resumo = mapa_est[codigo_sel]
    estudante_id = str(est_resumo["estudante_id"])

    resp_ind_est = consultar_indicadores_participacao(
        turma_id=turma_id_filtro,
        disciplina_id=disciplina_id_filtro,
        periodo_letivo=periodo_filtro,
        estudante_id=estudante_id,
    )
    if not resp_ind_est.ok or not isinstance(resp_ind_est.dados, dict):
        st.error(
            resp_ind_est.erro or "Erro ao consultar histórico individual do estudante."
        )
        return

    ind_est = resp_ind_est.dados
    kpis_est = montar_resumo_indicadores_participacao(ind_est)

    c1, c2, c3, c4, c5 = st.columns(5, gap="small")
    with c1:
        card_kpi("Taxa individual", kpis_est["taxa_entrega"])
    with c2:
        card_kpi("Entregues / Esperadas", kpis_est["realizadas_vs_esperadas"])
    with c3:
        card_kpi("Com atraso", kpis_est["atrasadas"])
    with c4:
        card_kpi(
            "Não entregues / Pendentes",
            f"{kpis_est['nao_entregues']} / {kpis_est['pendentes']}",
        )
    with c5:
        card_kpi("Média das notas", kpis_est["media_notas"])

    ev_est = ind_est.get("evolucao_participacao") or []
    if ev_est:
        df_ev_est = pd.DataFrame(
            [
                {
                    "Período / Data": (
                        f"{ev.get('periodo_letivo')} ({_formatar_data_br(ev.get('data_referencia'))})"
                    ),
                    "Taxa individual (%)": float(ev["taxa_entrega_percentual"]),
                }
                for ev in ev_est
                if ev.get("taxa_entrega_percentual") is not None
            ]
        )
        if not df_ev_est.empty:
            with card(f"Evolução da participação — {codigo_sel}"):
                st.plotly_chart(
                    grafico_linha(df_ev_est, x="Período / Data", y="Taxa individual (%)"),
                    use_container_width=True,
                )

    # Detalhamento das atividades desse estudante
    linhas_detalhe: list[dict[str, Any]] = []
    for at in atividades_filtradas:
        resp_ent_est = listar_entregas_atividade_api(
            str(at.get("id")),
            estudante_id=estudante_id,
        )
        if not resp_ent_est.ok or not isinstance(resp_ent_est.dados, list):
            continue
        if not resp_ent_est.dados:
            continue
        ent = resp_ent_est.dados[0]
        nota_val = ent.get("nota")
        nota_max = ent.get("nota_maxima") or at.get("nota_maxima")
        linhas_detalhe.append(
            {
                "Código": at.get("codigo") or "—",
                "Atividade": at.get("titulo") or "—",
                "Período": at.get("periodo_letivo") or "—",
                "Data limite": _formatar_data_br(at.get("data_limite")),
                "Status": ROTULOS_STATUS_ENTREGA.get(
                    str(ent.get("status_entrega")), str(ent.get("status_entrega"))
                ),
                "Data entrega": _formatar_data_br(ent.get("data_entrega")),
                "Nota": (
                    decimal_br(float(nota_val), 1) if nota_val is not None else "—"
                ),
                "Nota máxima": (
                    decimal_br(float(nota_max), 1) if nota_max is not None else "—"
                ),
            }
        )

    if linhas_detalhe:
        tabela_paginada(
            pd.DataFrame(linhas_detalhe),
            chave=f"part_ind_det_{estudante_id}",
            titulo=f"Atividades esperadas e entregas de {codigo_sel}",
            itens_por_pagina=10,
        )
    else:
        st.info("Não há entregas detalhadas registradas para este estudante no recorte.")


def _renderizar_aba_acompanhamento(
    turma_id_filtro: Optional[str],
    disciplina_id_filtro: Optional[str],
    indicadores: Optional[dict[str, Any]],
) -> None:
    """Bloco C/G: Registro e consulta de ações pedagógicas vinculadas à participação."""
    if not turma_id_filtro:
        st.info(
            "Selecione uma turma específica nos filtros acima para registrar acompanhamentos pedagógicos."
        )
        return

    estudantes = (
        (indicadores.get("percentual_por_estudante") or [])
        if isinstance(indicadores, dict)
        else []
    )
    mapa_est = {
        "Coletivo (toda a turma)": None,
        **{
            str(e.get("codigo_anonimo")): str(e.get("estudante_id"))
            for e in estudantes
            if e.get("estudante_id") and e.get("codigo_anonimo")
        },
    }

    with st.form("form_acomp_participacao"):
        alvo_rotulo = st.selectbox("Alvo do acompanhamento", list(mapa_est.keys()))
        tipo_acao = st.text_input(
            "Tipo de ação pedagógica",
            placeholder="Ex.: Busca ativa / devolutiva de atividade",
        )
        descricao = st.text_area(
            "Descrição do acompanhamento",
            placeholder="Descreva a intervenção pedagógica realizada sem inserir dados pessoais identificáveis (LGPD).",
        )
        if st.form_submit_button("Registrar acompanhamento", type="primary"):
            if len(tipo_acao.strip()) < 2 or len(descricao.strip()) < 3:
                st.error("Informe um tipo de ação e uma descrição válidos.")
            else:
                resp_acomp = registrar_acompanhamento_pedagogico_api(
                    turma_id=turma_id_filtro,
                    disciplina_id=disciplina_id_filtro,
                    estudante_id=mapa_est[alvo_rotulo],
                    tipo_acao=tipo_acao,
                    descricao=descricao,
                    origem="PARTICIPACAO",
                )
                if resp_acomp.ok:
                    st.success("Acompanhamento pedagógico registrado com sucesso.")
                    st.rerun()
                else:
                    st.error(resp_acomp.erro or "Falha ao registrar acompanhamento.")

    resp_lista = listar_acompanhamentos_api(
        turma_id=turma_id_filtro,
        disciplina_id=disciplina_id_filtro,
        origem="PARTICIPACAO",
    )
    if resp_lista.ok and isinstance(resp_lista.dados, list) and resp_lista.dados:
        df_ac = pd.DataFrame(
            [
                {
                    "Data": _formatar_data_br(item.get("criado_em")),
                    "Estudante": item.get("codigo_anonimo") or "Coletivo (Turma)",
                    "Tipo de ação": item.get("tipo_acao") or "—",
                    "Descrição": item.get("descricao") or "—",
                }
                for item in resp_lista.dados
            ]
        )
        tabela_paginada(
            df_ac,
            chave="part_hist_acomp",
            titulo="Acompanhamentos pedagógicos registrados na participação",
            itens_por_pagina=8,
        )


def render() -> None:
    """Ponto de entrada da página Participação."""
    aplicar_responsividade()

    contexto_api = carregar_contexto_participacao_api()

    with st.container(key="participacao_cabecalho"):
        col_titulo, col_botao = st.columns([4, 1], gap="medium")
        with col_titulo:
            titulo_pagina(
                "Participação",
                "Acompanhamento de atividades, entregas esperadas e participação discente.",
            )
        with col_botao:
            st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
            turmas_aut, discs_aut = _opcoes_turmas_disciplinas_autorizadas(contexto_api)
            if st.button(
                "+ Inserir atividade",
                type="primary",
                use_container_width=True,
                disabled=not contexto_api.get("conectado"),
            ):
                _abrir_dialog_nova_atividade(turmas_aut, discs_aut)

    if contexto_api.get("sessao_expirada"):
        st.warning(
            contexto_api.get("erro_comunicacao")
            or "Sua sessão expirou. Faça login novamente."
        )
        return

    if contexto_api.get("sem_permissao"):
        st.error(
            contexto_api.get("erro_comunicacao")
            or "Permissão insuficiente para acessar os dados de participação."
        )
        return

    if contexto_api.get("erro_comunicacao"):
        st.error(contexto_api["erro_comunicacao"])
        return

    if not contexto_api.get("conectado"):
        st.warning(
            "Sessão autenticada no backend não encontrada. "
            "Faça login com uma conta válida conectada à API para acompanhar atividades e entregas reais."
        )
        return

    atividades_todas = list(contexto_api.get("atividades") or [])

    with st.container(key="participacao_filtros"):
        col_disc, col_turma, col_per, col_ativ = st.columns(
            [1.1, 1.1, 1.0, 1.4],
            gap="small",
        )

        opcoes_disc = {"Todas": None}
        for d in discs_aut:
            if d.get("id"):
                opcoes_disc[f"{d.get('nome')} ({d.get('codigo')})"] = str(d["id"])
        with col_disc:
            disc_sel = st.selectbox(
                "Disciplina",
                list(opcoes_disc.keys()),
                key="part_filtro_disc",
            )
            disciplina_id_filtro = opcoes_disc[disc_sel]

        opcoes_turma = {"Todas": None}
        for t in turmas_aut:
            if t.get("id"):
                opcoes_turma[f"{t.get('nome')} ({t.get('ano_letivo', '')})"] = str(t["id"])
        with col_turma:
            turma_sel = st.selectbox(
                "Turma",
                list(opcoes_turma.keys()),
                key="part_filtro_turma",
            )
            turma_id_filtro = opcoes_turma[turma_sel]

        periodos_unicos = sorted(
            {
                str(a.get("periodo_letivo")).strip()
                for a in atividades_todas
                if a.get("periodo_letivo")
            }
        )
        with col_per:
            per_sel = st.selectbox(
                "Período letivo",
                ["Todos", *periodos_unicos],
                key="part_filtro_periodo",
            )
            periodo_filtro = None if per_sel == "Todos" else per_sel

        atividades_filtradas = [
            a
            for a in atividades_todas
            if (disciplina_id_filtro is None or str(a.get("disciplina_id")) == disciplina_id_filtro)
            and (turma_id_filtro is None or str(a.get("turma_id")) == turma_id_filtro)
            and (periodo_filtro is None or str(a.get("periodo_letivo")) == periodo_filtro)
        ]

        opcoes_ativ = {"Todas as atividades": None}
        for a in atividades_filtradas:
            opcoes_ativ[f"{a.get('codigo')} — {a.get('titulo')}"] = a
        with col_ativ:
            ativ_rotulo_sel = st.selectbox(
                "Atividade",
                list(opcoes_ativ.keys()),
                key="part_filtro_atividade",
            )
            atividade_obj_sel = opcoes_ativ[ativ_rotulo_sel]
            atividade_id_filtro = (
                str(atividade_obj_sel["id"]) if atividade_obj_sel else None
            )

    resp_ind = consultar_indicadores_participacao(
        turma_id=turma_id_filtro,
        disciplina_id=disciplina_id_filtro,
        periodo_letivo=periodo_filtro,
        atividade_id=atividade_id_filtro,
    )
    if resp_ind.sessao_expirada:
        st.warning(resp_ind.erro or "Sessão expirada.")
        return
    if not resp_ind.ok:
        st.error(resp_ind.erro or "Não foi possível carregar os indicadores de participação.")
        return

    indicadores = resp_ind.dados if isinstance(resp_ind.dados, dict) else {}
    kpis = montar_resumo_indicadores_participacao(indicadores)

    with st.container(key="participacao_indicadores"):
        k1, k2, k3, k4, k5 = st.columns(5, gap="small")
        with k1:
            card_kpi("Taxa de entrega", kpis["taxa_entrega"])
        with k2:
            card_kpi("Entregues / Esperadas", kpis["realizadas_vs_esperadas"])
        with k3:
            card_kpi("No prazo / Atrasadas", f"{kpis['no_prazo']} / {kpis['atrasadas']}")
        with k4:
            card_kpi(
                "Não entregues / Pendentes",
                f"{kpis['nao_entregues']} / {kpis['pendentes']}",
            )
        with k5:
            card_kpi("Média notas disponíveis", kpis["media_notas"])

    atividade_para_entregas = (
        atividade_obj_sel
        if atividade_obj_sel is not None
        else (atividades_filtradas[0] if atividades_filtradas else None)
    )

    aba_entregas, aba_turma, aba_individual, aba_acomp = st.tabs(
        [
            "Entregas da atividade",
            "Indicadores & Histórico da Turma",
            "Histórico Individual (Anonimizado)",
            "Acompanhamento Pedagógico",
        ]
    )

    with aba_entregas:
        _renderizar_aba_entregas_atividade(atividade_para_entregas)

    with aba_turma:
        _renderizar_aba_historico_turma(indicadores)

    with aba_individual:
        _renderizar_aba_historico_individual(
            indicadores=indicadores,
            atividades_filtradas=atividades_filtradas,
            turma_id_filtro=turma_id_filtro,
            disciplina_id_filtro=disciplina_id_filtro,
            periodo_filtro=periodo_filtro,
        )

    with aba_acomp:
        _renderizar_aba_acompanhamento(
            turma_id_filtro=turma_id_filtro,
            disciplina_id_filtro=disciplina_id_filtro,
            indicadores=indicadores,
        )
