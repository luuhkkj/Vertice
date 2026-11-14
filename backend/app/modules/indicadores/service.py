"""
Serviços especializados de cálculo de Indicadores Educacionais (Fase 4):
1. `IndicadoresGeraisService`: métricas gerais, distribuições por série/turma/turno e evolução longitudinal.
2. `IndicadoresAvaliacoesService`: Mapa de Acertos, taxas de acerto, distribuição de alternativas,
   faixa de desempenho da turma na questão e média ponderada.
3. `IndicadoresParticipacaoService`: entregas esperadas, realizadas, atrasadas, não entregas após
   o prazo, pendentes antes do prazo, taxas por atividade/turma e percentual individual.
"""

from collections import defaultdict
from datetime import date
from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.avaliacoes.models import (
    ALTERNATIVAS_VALIDAS_GABARITO,
    Avaliacao,
    FaixaDificuldadeQuestao,
    TipoQuestao,
)
from app.modules.estudantes.models import BoletimPeriodo, Estudante
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.indicadores.repository import IndicadoresRepository
from app.modules.indicadores.schemas import (
    ComparacaoPeriodoAnteriorSchema,
    DesempenhoTurmaDisciplinaAvaliacaoSchema,
    DistribuicaoAcertosAvaliacaoSchema,
    DistribuicaoItemSchema,
    EvolucaoParticipacaoItemSchema,
    EvolucaoPeriodoGeralSchema,
    IndicadorQuestaoSchema,
    IndicadorTopicoAvaliacaoSchema,
    IndicadoresAvaliacoesResponse,
    IndicadoresGeraisResponse,
    IndicadoresParticipacaoResponse,
    PercentualIndividualEntregaSchema,
    TaxaEntregaAtividadeSchema,
    TaxaEntregaTurmaSchema,
)
from app.modules.participacao.models import (
    StatusAtividade,
    StatusEntregaAtividade,
)
from app.modules.participacao.repository import ParticipacaoRepository
from app.modules.usuarios.models import PapelUsuario, Usuario

# Limites configuráveis e documentados para classificação da "faixa de desempenho da turma na questão"
# a partir da taxa de acerto observada (%):
LIMIAR_TAXA_ACERTO_FACIL = 75.0
LIMIAR_TAXA_ACERTO_ADEQUADA = 50.0
LIMIAR_TAXA_ACERTO_ATENCAO = 30.0


def classificar_faixa_desempenho_questao(
    taxa_acerto_percentual: Optional[float],
) -> Optional[str]:
    """
    Classifica o desempenho observado da turma em uma questão com base na taxa de acerto (%):
    - Fácil: taxa >= 75.0%
    - Adequada: 50.0% <= taxa < 75.0%
    - Atenção: 30.0% <= taxa < 50.0%
    - Difícil: taxa < 30.0%
    Retorna `None` caso não haja respostas válidas/esperadas.
    """
    if taxa_acerto_percentual is None:
        return None
    if taxa_acerto_percentual >= LIMIAR_TAXA_ACERTO_FACIL:
        return FaixaDificuldadeQuestao.FACIL.value
    if taxa_acerto_percentual >= LIMIAR_TAXA_ACERTO_ADEQUADA:
        return FaixaDificuldadeQuestao.ADEQUADA.value
    if taxa_acerto_percentual >= LIMIAR_TAXA_ACERTO_ATENCAO:
        return FaixaDificuldadeQuestao.ATENCAO.value
    return FaixaDificuldadeQuestao.DIFICIL.value


def _media_arredondada(valores: list[float]) -> Optional[float]:
    if not valores:
        return None
    return round(sum(valores) / len(valores), 2)


class IndicadoresGeraisService:
    """Cálculos de indicadores gerais (Bloco A / Visão Geral)."""

    @staticmethod
    def _extrair_freq_e_nota_boletim(
        bol: BoletimPeriodo,
        usuario: Usuario,
        mapa_vinculos_prof: dict[uuid.UUID, set[Optional[uuid.UUID]]],
        disciplina_id_filtro: Optional[uuid.UUID] = None,
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Extrai a frequência e a nota representativa de um boletim respeitando o escopo:
        - Se um filtro `disciplina_id` foi informado, ou se o usuário é professor vinculado a
          disciplina(s) específica(s), utiliza a média das `NotaDisciplina` autorizadas;
        - Caso contrário (gestor sem filtro de disciplina ou professor com vínculo geral `None`),
          utiliza `boletim.frequencia_percentual` e `boletim.media_geral` (com fallback para as
          notas de disciplina quando `media_geral` for `None`).
        Valores ausentes (`None`) nunca são convertidos em zero.
        """
        usar_escopo_disciplina = disciplina_id_filtro is not None or (
            usuario.papel == PapelUsuario.PROFESSOR
            and None not in mapa_vinculos_prof.get(bol.turma_id, set())
        )

        if usar_escopo_disciplina:
            discs_aut = mapa_vinculos_prof.get(bol.turma_id, set())
            notas_elegiveis = [
                nd
                for nd in bol.notas_disciplina
                if (nd.disciplina is None or nd.disciplina.ativo)
                and (
                    usuario.papel != PapelUsuario.PROFESSOR
                    or None in discs_aut
                    or nd.disciplina_id in discs_aut
                )
                and (
                    disciplina_id_filtro is None
                    or nd.disciplina_id == disciplina_id_filtro
                )
            ]
            freqs = [
                float(nd.frequencia_percentual)
                for nd in notas_elegiveis
                if nd.frequencia_percentual is not None
            ]
            notas = [
                float(nd.nota)
                for nd in notas_elegiveis
                if nd.nota is not None
            ]
            freq_val = (
                _media_arredondada(freqs)
                if freqs
                else (
                    float(bol.frequencia_percentual)
                    if bol.frequencia_percentual is not None
                    else None
                )
            )
            nota_val = (
                _media_arredondada(notas)
                if notas
                else (
                    float(bol.media_geral)
                    if bol.media_geral is not None
                    else None
                )
            )
            return freq_val, nota_val

        freq_geral = (
            float(bol.frequencia_percentual)
            if bol.frequencia_percentual is not None
            else None
        )
        if freq_geral is None:
            freqs_nd = [
                float(nd.frequencia_percentual)
                for nd in bol.notas_disciplina
                if nd.frequencia_percentual is not None
            ]
            freq_geral = _media_arredondada(freqs_nd)

        media_g = (
            float(bol.media_geral) if bol.media_geral is not None else None
        )
        if media_g is None:
            notas_nd = [
                float(nd.nota)
                for nd in bol.notas_disciplina
                if nd.nota is not None
            ]
            media_g = _media_arredondada(notas_nd)

        return freq_geral, media_g

    @staticmethod
    def calcular_indicadores_gerais(
        db: Session,
        usuario: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
    ) -> IndicadoresGeraisResponse:
        escolas_aut = IndicadoresRepository.validar_filtros_escopo(
            db=db,
            usuario=usuario,
            escola_id=escola_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
        )

        boletins, mapa_vinculos_prof = (
            IndicadoresRepository.listar_boletins_escopo(
                db=db,
                usuario=usuario,
                escolas_autorizadas=escolas_aut,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                ano_letivo=ano_letivo,
                periodo_letivo=periodo_letivo,
            )
        )

        if not boletins:
            return IndicadoresGeraisResponse()

        estudantes_distintos_ids: set[uuid.UUID] = set()
        todas_freqs: list[float] = []
        todas_medias: list[float] = []

        # Estruturas para distribuições sem duplicar estudantes na contagem
        agrup_serie_est: dict[str, set[uuid.UUID]] = defaultdict(set)
        agrup_serie_freqs: dict[str, list[float]] = defaultdict(list)
        agrup_serie_medias: dict[str, list[float]] = defaultdict(list)

        agrup_turma_est: dict[str, set[uuid.UUID]] = defaultdict(set)
        agrup_turma_freqs: dict[str, list[float]] = defaultdict(list)
        agrup_turma_medias: dict[str, list[float]] = defaultdict(list)

        agrup_turno_est: dict[str, set[uuid.UUID]] = defaultdict(set)
        agrup_turno_freqs: dict[str, list[float]] = defaultdict(list)
        agrup_turno_medias: dict[str, list[float]] = defaultdict(list)

        agrup_periodo_est: dict[tuple[int, str], set[uuid.UUID]] = defaultdict(
            set
        )
        agrup_periodo_freqs: dict[tuple[int, str], list[float]] = defaultdict(
            list
        )
        agrup_periodo_medias: dict[tuple[int, str], list[float]] = defaultdict(
            list
        )

        for bol in boletins:
            estudantes_distintos_ids.add(bol.estudante_id)
            freq_v, nota_v = (
                IndicadoresGeraisService._extrair_freq_e_nota_boletim(
                    bol=bol,
                    usuario=usuario,
                    mapa_vinculos_prof=mapa_vinculos_prof,
                    disciplina_id_filtro=disciplina_id,
                )
            )
            if freq_v is not None:
                todas_freqs.append(freq_v)
            if nota_v is not None:
                todas_medias.append(nota_v)

            serie_nome = bol.turma.serie if bol.turma else "Não informada"
            turma_nome = bol.turma.nome if bol.turma else str(bol.turma_id)
            turno_nome = bol.turma.turno if bol.turma else "Não informado"
            chave_per = (bol.ano_letivo, bol.periodo_letivo)

            agrup_serie_est[serie_nome].add(bol.estudante_id)
            agrup_turma_est[turma_nome].add(bol.estudante_id)
            agrup_turno_est[turno_nome].add(bol.estudante_id)
            agrup_periodo_est[chave_per].add(bol.estudante_id)

            if freq_v is not None:
                agrup_serie_freqs[serie_nome].append(freq_v)
                agrup_turma_freqs[turma_nome].append(freq_v)
                agrup_turno_freqs[turno_nome].append(freq_v)
                agrup_periodo_freqs[chave_per].append(freq_v)

            if nota_v is not None:
                agrup_serie_medias[serie_nome].append(nota_v)
                agrup_turma_medias[turma_nome].append(nota_v)
                agrup_turno_medias[turno_nome].append(nota_v)
                agrup_periodo_medias[chave_per].append(nota_v)

        total_distintos = len(estudantes_distintos_ids)

        def _montar_distribuicao(
            mapa_est: dict[str, set[uuid.UUID]],
            mapa_f: dict[str, list[float]],
            mapa_m: dict[str, list[float]],
        ) -> list[DistribuicaoItemSchema]:
            itens: list[DistribuicaoItemSchema] = []
            for ch in sorted(mapa_est.keys()):
                qtd = len(mapa_est[ch])
                perc = (
                    round((qtd / total_distintos) * 100.0, 2)
                    if total_distintos > 0
                    else 0.0
                )
                itens.append(
                    DistribuicaoItemSchema(
                        chave=ch,
                        total_estudantes=qtd,
                        percentual_estudantes=perc,
                        frequencia_media=_media_arredondada(mapa_f[ch]),
                        media_geral=_media_arredondada(mapa_m[ch]),
                    )
                )
            return itens

        # Evolução por período: se o usuário filtrou um período específico, buscamos todos os períodos
        # do mesmo recorte (sem o filtro periodo_letivo) para construir a série histórica e comparação.
        if periodo_letivo is not None:
            boletins_hist, _ = IndicadoresRepository.listar_boletins_escopo(
                db=db,
                usuario=usuario,
                escolas_autorizadas=escolas_aut,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                ano_letivo=ano_letivo,
                periodo_letivo=None,
            )
            agrup_periodo_est.clear()
            agrup_periodo_freqs.clear()
            agrup_periodo_medias.clear()
            for b_h in boletins_hist:
                ch_p = (b_h.ano_letivo, b_h.periodo_letivo)
                agrup_periodo_est[ch_p].add(b_h.estudante_id)
                f_h, n_h = (
                    IndicadoresGeraisService._extrair_freq_e_nota_boletim(
                        bol=b_h,
                        usuario=usuario,
                        mapa_vinculos_prof=mapa_vinculos_prof,
                        disciplina_id_filtro=disciplina_id,
                    )
                )
                if f_h is not None:
                    agrup_periodo_freqs[ch_p].append(f_h)
                if n_h is not None:
                    agrup_periodo_medias[ch_p].append(n_h)

        evolucao: list[EvolucaoPeriodoGeralSchema] = []
        for ano_p, per_p in sorted(agrup_periodo_est.keys()):
            evolucao.append(
                EvolucaoPeriodoGeralSchema(
                    ano_letivo=ano_p,
                    periodo_letivo=per_p,
                    total_estudantes=len(agrup_periodo_est[(ano_p, per_p)]),
                    frequencia_media=_media_arredondada(
                        agrup_periodo_freqs[(ano_p, per_p)]
                    ),
                    media_geral=_media_arredondada(
                        agrup_periodo_medias[(ano_p, per_p)]
                    ),
                )
            )

        comparacao: Optional[ComparacaoPeriodoAnteriorSchema] = None
        if len(evolucao) >= 2:
            atual_ev = evolucao[-1]
            ant_ev = evolucao[-2]
            if periodo_letivo is not None:
                for idx_e, item_ev in enumerate(evolucao):
                    if (
                        item_ev.periodo_letivo == periodo_letivo.strip()
                        and idx_e >= 1
                    ):
                        atual_ev = item_ev
                        ant_ev = evolucao[idx_e - 1]
                        break

            var_freq = (
                round(atual_ev.frequencia_media - ant_ev.frequencia_media, 2)
                if atual_ev.frequencia_media is not None
                and ant_ev.frequencia_media is not None
                else None
            )
            var_media = (
                round(atual_ev.media_geral - ant_ev.media_geral, 2)
                if atual_ev.media_geral is not None
                and ant_ev.media_geral is not None
                else None
            )
            comparacao = ComparacaoPeriodoAnteriorSchema(
                periodo_atual=f"{atual_ev.ano_letivo} - {atual_ev.periodo_letivo}",
                periodo_anterior=f"{ant_ev.ano_letivo} - {ant_ev.periodo_letivo}",
                variacao_frequencia_media=var_freq,
                variacao_media_geral=var_media,
                variacao_total_estudantes=(
                    atual_ev.total_estudantes - ant_ev.total_estudantes
                ),
            )

        return IndicadoresGeraisResponse(
            total_estudantes_distintos=total_distintos,
            total_registros_boletim=len(boletins),
            frequencia_media=_media_arredondada(todas_freqs),
            media_geral=_media_arredondada(todas_medias),
            distribuicao_por_serie=_montar_distribuicao(
                agrup_serie_est, agrup_serie_freqs, agrup_serie_medias
            ),
            distribuicao_por_turma=_montar_distribuicao(
                agrup_turma_est, agrup_turma_freqs, agrup_turma_medias
            ),
            distribuicao_por_turno=_montar_distribuicao(
                agrup_turno_est, agrup_turno_freqs, agrup_turno_medias
            ),
            evolucao_por_periodo=evolucao,
            comparacao_periodo_anterior=comparacao,
            possui_previsoes_risco=False,
            distribuicao_faixas_risco=[],
        )


class IndicadoresAvaliacoesService:
    """Cálculos de indicadores de avaliações (Bloco B / Mapa de Acertos)."""

    @staticmethod
    def calcular_indicadores_avaliacoes(
        db: Session,
        usuario: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        avaliacao_id: Optional[uuid.UUID] = None,
    ) -> IndicadoresAvaliacoesResponse:
        escolas_aut = IndicadoresRepository.validar_filtros_escopo(
            db=db,
            usuario=usuario,
            escola_id=escola_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
        )

        avaliacoes = IndicadoresRepository.listar_avaliacoes_escopo(
            db=db,
            usuario=usuario,
            escolas_autorizadas=escolas_aut,
            avaliacao_id=avaliacao_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
            ano_letivo=ano_letivo,
            periodo_letivo=periodo_letivo,
        )

        if avaliacao_id is not None and not avaliacoes:
            # Se a avaliação existe mas está fora do escopo do usuário, retorna 403/404 adequado
            from app.modules.avaliacoes.service import AvaliacaoService

            AvaliacaoService.obter_avaliacao(db, avaliacao_id, usuario)

        if not avaliacoes:
            return IndicadoresAvaliacoesResponse()

        questoes_schema: list[IndicadorQuestaoSchema] = []
        agrup_topicos: dict[str, dict[str, int]] = defaultdict(
            lambda: {"questoes": 0, "esperadas": 0, "acertos": 0}
        )
        agrup_turma_disc: dict[
            tuple[uuid.UUID, uuid.UUID],
            dict[str, object],
        ] = {}

        soma_pesos_global = 0.0
        medias_avaliacoes_escala_10: list[float] = []
        pontos_medios_avaliacoes: list[float] = []
        total_esperadas_global = 0
        total_registradas_global = 0
        total_ausentes_global = 0
        total_acertos_global = 0
        total_erros_global = 0
        total_em_branco_global = 0
        distribuicao_acertos_estudantes: list[
            DistribuicaoAcertosAvaliacaoSchema
        ] = []

        for av in avaliacoes:
            # Estudantes elegíveis na turma da avaliação (respostas esperadas):
            estudantes_turma = (
                ParticipacaoRepository.list_estudantes_elegiveis_turma(
                    db=db,
                    escola_id=av.escola_id,
                    turma_id=av.turma_id,
                )
            )
            ids_esperados_turma = {e.id for e in estudantes_turma}

            questoes_av = sorted(
                av.questoes or [], key=lambda q: q.codigo_questao
            )
            peso_total_av = sum(float(q.valor_questao) for q in questoes_av)
            soma_pesos_global += peso_total_av

            # Acumula pontuação e acertos por estudante que possui resposta na avaliação
            pontos_por_estudante: dict[uuid.UUID, float] = defaultdict(float)
            acertos_por_estudante: dict[uuid.UUID, int] = defaultdict(int)
            respondentes_avaliacao: set[uuid.UUID] = set()
            taxas_questoes_av: list[float] = []

            for q in questoes_av:
                respostas_q = list(q.respostas or [])
                ids_respondentes = {r.estudante_id for r in respostas_q}
                respondentes_avaliacao.update(ids_respondentes)
                conjunto_esperado = ids_esperados_turma | ids_respondentes
                # Denominador: total de respostas esperadas e válidas para a questão.
                # Se a turma possui estudantes vinculados, utiliza max(len(conjunto_esperado), len(respostas_q)).
                denom_esperado = (
                    len(conjunto_esperado)
                    if conjunto_esperado
                    else len(respostas_q)
                )

                acertos = 0
                erros = 0
                em_branco = 0
                notas_q: list[float] = []

                dist_alt: dict[str, int] = (
                    {alt: 0 for alt in sorted(ALTERNATIVAS_VALIDAS_GABARITO)}
                    if q.tipo_questao == TipoQuestao.FECHADA
                    else {}
                )
                if q.tipo_questao == TipoQuestao.FECHADA:
                    dist_alt["BRANCO"] = 0

                for r in respostas_q:
                    notas_q.append(float(r.nota_obtida))
                    pontos_por_estudante[r.estudante_id] += float(
                        r.nota_obtida
                    )

                    if (
                        r.em_branco
                        or (r.alternativa_marcada or "").upper() == "BRANCO"
                    ):
                        em_branco += 1
                        if q.tipo_questao == TipoQuestao.FECHADA:
                            dist_alt["BRANCO"] = dist_alt.get("BRANCO", 0) + 1
                    else:
                        if q.tipo_questao == TipoQuestao.FECHADA and r.alternativa_marcada:
                            alt_m = r.alternativa_marcada.strip().upper()
                            dist_alt[alt_m] = dist_alt.get(alt_m, 0) + 1
                        if r.acertou is True:
                            acertos += 1
                            acertos_por_estudante[r.estudante_id] += 1
                        else:
                            erros += 1

                ausentes_q = max(0, denom_esperado - len(respostas_q))
                total_esperadas_global += denom_esperado
                total_registradas_global += len(respostas_q)
                total_ausentes_global += ausentes_q
                total_acertos_global += acertos
                total_erros_global += erros
                total_em_branco_global += em_branco

                taxa_q = (
                    round((acertos / denom_esperado) * 100.0, 2)
                    if denom_esperado > 0
                    else None
                )
                if taxa_q is not None:
                    taxas_questoes_av.append(taxa_q)

                ind_q = IndicadorQuestaoSchema(
                    questao_id=q.id,
                    avaliacao_id=av.id,
                    avaliacao_codigo=av.codigo,
                    avaliacao_titulo=av.titulo,
                    periodo_letivo=av.periodo_letivo,
                    turma_id=av.turma_id,
                    turma_nome=av.turma.nome if av.turma else None,
                    disciplina_id=av.disciplina_id,
                    disciplina_codigo=(
                        av.disciplina.codigo if av.disciplina else None
                    ),
                    disciplina_nome=(
                        av.disciplina.nome if av.disciplina else None
                    ),
                    codigo_questao=q.codigo_questao,
                    tipo_questao=q.tipo_questao.value,
                    alternativa_correta=q.alternativa_correta,
                    valor_questao=float(q.valor_questao),
                    topico=q.topico,
                    faixa_dificuldade_cadastrada=q.faixa_dificuldade.value,
                    faixa_desempenho_observada=classificar_faixa_desempenho_questao(
                        taxa_q
                    ),
                    total_respostas_esperadas=denom_esperado,
                    total_respostas_registradas=len(respostas_q),
                    quantidade_respostas_ausentes=ausentes_q,
                    quantidade_acertos=acertos,
                    quantidade_erros=erros,
                    quantidade_em_branco=em_branco,
                    taxa_acerto_percentual=taxa_q,
                    media_nota_questao=_media_arredondada(notas_q),
                    distribuicao_alternativas=dist_alt,
                )
                questoes_schema.append(ind_q)

                nome_topico = (
                    q.topico.strip()
                    if q.topico and q.topico.strip()
                    else "Geral / Não especificado"
                )
                agrup_topicos[nome_topico]["questoes"] += 1
                agrup_topicos[nome_topico]["esperadas"] += denom_esperado
                agrup_topicos[nome_topico]["acertos"] += acertos

            # Distribuição geral de acertos por estudante na avaliação (Gráfico 5):
            # Calculada para os estudantes que possuem respostas registradas na avaliação.
            if len(avaliacoes) == 1 and questoes_av and respondentes_avaliacao:
                total_q_av = len(questoes_av)
                contagem_por_acertos: dict[int, int] = {
                    k: 0 for k in range(total_q_av + 1)
                }
                for est_id in respondentes_avaliacao:
                    qtd_ac_est = acertos_por_estudante.get(est_id, 0)
                    contagem_por_acertos[qtd_ac_est] = (
                        contagem_por_acertos.get(qtd_ac_est, 0) + 1
                    )
                total_resp_av = len(respondentes_avaliacao)
                for k_ac in range(total_q_av + 1):
                    qtd_est = contagem_por_acertos.get(k_ac, 0)
                    distribuicao_acertos_estudantes.append(
                        DistribuicaoAcertosAvaliacaoSchema(
                            quantidade_acertos=k_ac,
                            total_questoes_avaliacao=total_q_av,
                            percentual_acerto_estudante=round(
                                (k_ac / total_q_av) * 100.0, 2
                            ),
                            quantidade_estudantes=qtd_est,
                            percentual_estudantes=round(
                                (qtd_est / total_resp_av) * 100.0, 2
                            ),
                        )
                    )

            # Média ponderada da avaliação considerando os pesos das questões:
            # Pontuação média dos participantes avaliados normalizada para escala 0..10 (e bruta).
            media_av_10: Optional[float] = None
            if pontos_por_estudante and peso_total_av > 0.0:
                media_pts = sum(pontos_por_estudante.values()) / len(
                    pontos_por_estudante
                )
                pontos_medios_avaliacoes.append(round(media_pts, 2))
                media_av_10 = round((media_pts / peso_total_av) * 10.0, 2)
                medias_avaliacoes_escala_10.append(media_av_10)

            chave_td = (av.turma_id, av.disciplina_id)
            if chave_td not in agrup_turma_disc:
                agrup_turma_disc[chave_td] = {
                    "turma_nome": av.turma.nome if av.turma else "",
                    "disciplina_codigo": (
                        av.disciplina.codigo if av.disciplina else ""
                    ),
                    "disciplina_nome": (
                        av.disciplina.nome if av.disciplina else ""
                    ),
                    "total_avaliacoes": 0,
                    "medias": [],
                    "taxas": [],
                }
            entry_td = agrup_turma_disc[chave_td]
            entry_td["total_avaliacoes"] = int(entry_td["total_avaliacoes"]) + 1  # type: ignore[arg-type]
            if media_av_10 is not None:
                entry_td["medias"].append(media_av_10)  # type: ignore[attr-defined]
            taxa_media_av = _media_arredondada(taxas_questoes_av)
            if taxa_media_av is not None:
                entry_td["taxas"].append(taxa_media_av)  # type: ignore[attr-defined]

        questoes_com_taxa = [
            q for q in questoes_schema if q.taxa_acerto_percentual is not None
        ]
        maior_q: Optional[IndicadorQuestaoSchema] = None
        menor_q: Optional[IndicadorQuestaoSchema] = None
        if questoes_com_taxa:
            maior_q = max(
                questoes_com_taxa,
                key=lambda x: (
                    x.taxa_acerto_percentual or 0.0,
                    -questoes_schema.index(x),
                ),
            )
            menor_q = min(
                questoes_com_taxa,
                key=lambda x: (
                    x.taxa_acerto_percentual or 0.0,
                    questoes_schema.index(x),
                ),
            )

        dist_topicos: list[IndicadorTopicoAvaliacaoSchema] = []
        for topico_k in sorted(agrup_topicos.keys()):
            dados_t = agrup_topicos[topico_k]
            esp_t = dados_t["esperadas"]
            ac_t = dados_t["acertos"]
            taxa_t = round((ac_t / esp_t) * 100.0, 2) if esp_t > 0 else None
            dist_topicos.append(
                IndicadorTopicoAvaliacaoSchema(
                    topico=topico_k,
                    total_questoes=dados_t["questoes"],
                    total_respostas_esperadas=esp_t,
                    quantidade_acertos=ac_t,
                    taxa_acerto_percentual=taxa_t,
                )
            )

        desempenho_td: list[DesempenhoTurmaDisciplinaAvaliacaoSchema] = []
        for (t_id, d_id), info in agrup_turma_disc.items():
            desempenho_td.append(
                DesempenhoTurmaDisciplinaAvaliacaoSchema(
                    turma_id=t_id,
                    turma_nome=str(info["turma_nome"]),
                    disciplina_id=d_id,
                    disciplina_codigo=str(info["disciplina_codigo"]),
                    disciplina_nome=str(info["disciplina_nome"]),
                    total_avaliacoes=int(info["total_avaliacoes"]),  # type: ignore[arg-type]
                    media_avaliacoes=_media_arredondada(info["medias"]),  # type: ignore[arg-type]
                    taxa_acerto_media_percentual=_media_arredondada(
                        info["taxas"]  # type: ignore[arg-type]
                    ),
                )
            )

        taxa_acerto_geral = (
            round((total_acertos_global / total_esperadas_global) * 100.0, 2)
            if total_esperadas_global > 0
            else None
        )

        return IndicadoresAvaliacoesResponse(
            total_avaliacoes=len(avaliacoes),
            total_questoes=len(questoes_schema),
            total_respostas_esperadas=total_esperadas_global,
            total_respostas_registradas=total_registradas_global,
            total_respostas_ausentes=total_ausentes_global,
            total_acertos=total_acertos_global,
            total_erros=total_erros_global,
            total_em_branco=total_em_branco_global,
            taxa_acerto_geral_percentual=taxa_acerto_geral,
            media_avaliacao_ponderada=_media_arredondada(
                medias_avaliacoes_escala_10
            ),
            soma_pesos_avaliacao=(
                round(soma_pesos_global, 2) if soma_pesos_global > 0 else None
            ),
            media_pontos_obtidos=_media_arredondada(pontos_medios_avaliacoes),
            questao_maior_taxa_acerto=maior_q,
            questao_menor_taxa_acerto=menor_q,
            questoes=questoes_schema,
            distribuicao_acertos_estudantes=distribuicao_acertos_estudantes,
            distribuicao_por_topico=dist_topicos,
            desempenho_por_turma_disciplina=desempenho_td,
        )


class IndicadoresParticipacaoService:
    """Cálculos de indicadores de participação (Bloco C / Atividades e Entregas)."""

    @staticmethod
    def calcular_indicadores_participacao(
        db: Session,
        usuario: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        atividade_id: Optional[uuid.UUID] = None,
        estudante_id: Optional[uuid.UUID] = None,
        data_referencia: Optional[date] = None,
    ) -> IndicadoresParticipacaoResponse:
        hoje = data_referencia or date.today()
        escolas_aut = IndicadoresRepository.validar_filtros_escopo(
            db=db,
            usuario=usuario,
            escola_id=escola_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
        )

        if estudante_id is not None:
            est_filtro = EstudanteRepository.get_by_id(db, estudante_id)
            if est_filtro is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Estudante não encontrado.",
                )
            if (
                escolas_aut is not None
                and est_filtro.escola_id not in escolas_aut
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado ao estudante fora da escola autorizada.",
                )

        atividades = IndicadoresRepository.listar_atividades_escopo(
            db=db,
            usuario=usuario,
            escolas_autorizadas=escolas_aut,
            atividade_id=atividade_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
            ano_letivo=ano_letivo,
            periodo_letivo=periodo_letivo,
        )

        if atividade_id is not None and not atividades:
            from app.modules.participacao.service import ParticipacaoService

            ParticipacaoService.obter_atividade(db, atividade_id, usuario)

        if not atividades:
            return IndicadoresParticipacaoResponse()

        total_esperadas_global = 0
        realizadas_global = 0
        no_prazo_global = 0
        atrasadas_global = 0
        nao_entregues_global = 0
        pendentes_global = 0
        notas_disponiveis_global: list[float] = []

        taxa_por_atividade: list[TaxaEntregaAtividadeSchema] = []
        agrup_turma: dict[uuid.UUID, dict[str, object]] = {}
        agrup_estudante: dict[uuid.UUID, dict[str, object]] = {}
        agrup_evolucao: dict[tuple[str, date], dict[str, int]] = defaultdict(
            lambda: {"atividades": 0, "esperadas": 0, "realizadas": 0}
        )

        for at in atividades:
            entregas_at = list(at.entregas or [])
            mapa_entregas = {e.estudante_id: e for e in entregas_at}
            mapa_elegiveis: dict[uuid.UUID, Estudante] = {}

            if at.status == StatusAtividade.ABERTA or len(entregas_at) == 0:
                ano_turma = at.turma.ano_letivo if at.turma else None
                estudantes_elegiveis = (
                    ParticipacaoRepository.list_estudantes_elegiveis_turma(
                        db=db,
                        escola_id=at.escola_id,
                        turma_id=at.turma_id,
                        periodo_letivo=at.periodo_letivo,
                        ano_letivo=ano_turma,
                    )
                )
                for e in estudantes_elegiveis:
                    mapa_elegiveis[e.id] = e

            for e_reg in entregas_at:
                if e_reg.estudante is not None:
                    mapa_elegiveis.setdefault(
                        e_reg.estudante_id, e_reg.estudante
                    )

            if estudante_id is not None:
                if estudante_id not in mapa_elegiveis:
                    continue
                ids_esperados_at = [estudante_id]
            else:
                ids_esperados_at = sorted(
                    mapa_elegiveis.keys(),
                    key=lambda eid: mapa_elegiveis[eid].codigo_anonimo,
                )

            esp_at = len(ids_esperados_at)
            real_at = 0
            prazo_at = 0
            atr_at = 0
            nao_ent_at = 0
            pend_at = 0
            notas_at: list[float] = []

            for eid in ids_esperados_at:
                est_obj = mapa_elegiveis[eid]
                ent_obj = mapa_entregas.get(eid)

                if ent_obj is not None:
                    st = ent_obj.status_entrega
                    # Se o registro estava PENDENTE sem entrega e o prazo já venceu em relação a `hoje`,
                    # contabiliza como NAO_ENTREGUE após o prazo.
                    if (
                        st == StatusEntregaAtividade.PENDENTE
                        and ent_obj.data_entrega is None
                        and hoje > at.data_limite
                    ):
                        st = StatusEntregaAtividade.NAO_ENTREGUE
                    elif (
                        st == StatusEntregaAtividade.NAO_ENTREGUE
                        and ent_obj.data_entrega is None
                        and hoje <= at.data_limite
                    ):
                        st = StatusEntregaAtividade.PENDENTE
                    nota_val = (
                        float(ent_obj.nota)
                        if ent_obj.nota is not None
                        else None
                    )
                else:
                    # Estudante esperado na turma mesmo sem linha física em entregas_atividade
                    st = (
                        StatusEntregaAtividade.PENDENTE
                        if hoje <= at.data_limite
                        else StatusEntregaAtividade.NAO_ENTREGUE
                    )
                    nota_val = None

                if nota_val is not None:
                    notas_at.append(nota_val)
                    notas_disponiveis_global.append(nota_val)

                if st == StatusEntregaAtividade.ENTREGUE:
                    real_at += 1
                    prazo_at += 1
                elif st == StatusEntregaAtividade.ATRASADO:
                    real_at += 1
                    atr_at += 1
                elif st == StatusEntregaAtividade.NAO_ENTREGUE:
                    nao_ent_at += 1
                else:
                    pend_at += 1

                if eid not in agrup_estudante:
                    agrup_estudante[eid] = {
                        "codigo_anonimo": est_obj.codigo_anonimo,
                        "esperadas": 0,
                        "realizadas": 0,
                        "atrasadas": 0,
                        "nao_entregues": 0,
                        "pendentes": 0,
                        "notas": [],
                    }
                info_est = agrup_estudante[eid]
                info_est["esperadas"] = int(info_est["esperadas"]) + 1  # type: ignore[arg-type]
                if st in (
                    StatusEntregaAtividade.ENTREGUE,
                    StatusEntregaAtividade.ATRASADO,
                ):
                    info_est["realizadas"] = int(info_est["realizadas"]) + 1  # type: ignore[arg-type]
                if st == StatusEntregaAtividade.ATRASADO:
                    info_est["atrasadas"] = int(info_est["atrasadas"]) + 1  # type: ignore[arg-type]
                if st == StatusEntregaAtividade.NAO_ENTREGUE:
                    info_est["nao_entregues"] = (
                        int(info_est["nao_entregues"]) + 1  # type: ignore[arg-type]
                    )
                if st == StatusEntregaAtividade.PENDENTE:
                    info_est["pendentes"] = int(info_est["pendentes"]) + 1  # type: ignore[arg-type]
                if nota_val is not None:
                    info_est["notas"].append(nota_val)  # type: ignore[attr-defined]

            total_esperadas_global += esp_at
            realizadas_global += real_at
            no_prazo_global += prazo_at
            atrasadas_global += atr_at
            nao_entregues_global += nao_ent_at
            pendentes_global += pend_at

            taxa_at = (
                round((real_at / esp_at) * 100.0, 2) if esp_at > 0 else None
            )
            taxa_por_atividade.append(
                TaxaEntregaAtividadeSchema(
                    atividade_id=at.id,
                    codigo=at.codigo,
                    titulo=at.titulo,
                    turma_id=at.turma_id,
                    turma_nome=at.turma.nome if at.turma else "",
                    disciplina_id=at.disciplina_id,
                    disciplina_codigo=(
                        at.disciplina.codigo if at.disciplina else ""
                    ),
                    periodo_letivo=at.periodo_letivo,
                    data_limite=at.data_limite,
                    total_entregas_esperadas=esp_at,
                    entregas_realizadas=real_at,
                    entregas_no_prazo=prazo_at,
                    entregas_atrasadas=atr_at,
                    nao_entregas_apos_prazo=nao_ent_at,
                    pendentes_antes_prazo=pend_at,
                    taxa_entrega_percentual=taxa_at,
                    media_notas_disponiveis=_media_arredondada(notas_at),
                )
            )

            if at.turma_id not in agrup_turma:
                agrup_turma[at.turma_id] = {
                    "turma_nome": at.turma.nome if at.turma else "",
                    "atividades": 0,
                    "esperadas": 0,
                    "realizadas": 0,
                    "atrasadas": 0,
                    "nao_entregues": 0,
                    "pendentes": 0,
                    "notas": [],
                }
            info_t = agrup_turma[at.turma_id]
            info_t["atividades"] = int(info_t["atividades"]) + 1  # type: ignore[arg-type]
            info_t["esperadas"] = int(info_t["esperadas"]) + esp_at  # type: ignore[arg-type]
            info_t["realizadas"] = int(info_t["realizadas"]) + real_at  # type: ignore[arg-type]
            info_t["atrasadas"] = int(info_t["atrasadas"]) + atr_at  # type: ignore[arg-type]
            info_t["nao_entregues"] = int(info_t["nao_entregues"]) + nao_ent_at  # type: ignore[arg-type]
            info_t["pendentes"] = int(info_t["pendentes"]) + pend_at  # type: ignore[arg-type]
            info_t["notas"].extend(notas_at)  # type: ignore[attr-defined]

            ch_ev = (at.periodo_letivo, at.data_limite)
            agrup_evolucao[ch_ev]["atividades"] += 1
            agrup_evolucao[ch_ev]["esperadas"] += esp_at
            agrup_evolucao[ch_ev]["realizadas"] += real_at

        taxa_por_turma: list[TaxaEntregaTurmaSchema] = []
        for tid, info_t in agrup_turma.items():
            esp_t = int(info_t["esperadas"])  # type: ignore[arg-type]
            real_t = int(info_t["realizadas"])  # type: ignore[arg-type]
            taxa_por_turma.append(
                TaxaEntregaTurmaSchema(
                    turma_id=tid,
                    turma_nome=str(info_t["turma_nome"]),
                    total_atividades=int(info_t["atividades"]),  # type: ignore[arg-type]
                    total_entregas_esperadas=esp_t,
                    entregas_realizadas=real_t,
                    entregas_atrasadas=int(info_t["atrasadas"]),  # type: ignore[arg-type]
                    nao_entregas_apos_prazo=int(info_t["nao_entregues"]),  # type: ignore[arg-type]
                    pendentes_antes_prazo=int(info_t["pendentes"]),  # type: ignore[arg-type]
                    taxa_entrega_percentual=(
                        round((real_t / esp_t) * 100.0, 2)
                        if esp_t > 0
                        else None
                    ),
                    media_notas_disponiveis=_media_arredondada(
                        info_t["notas"]  # type: ignore[arg-type]
                    ),
                )
            )

        percentual_estudantes: list[PercentualIndividualEntregaSchema] = []
        for eid, info_e in sorted(
            agrup_estudante.items(),
            key=lambda item: str(item[1]["codigo_anonimo"]),
        ):
            esp_e = int(info_e["esperadas"])  # type: ignore[arg-type]
            real_e = int(info_e["realizadas"])  # type: ignore[arg-type]
            percentual_estudantes.append(
                PercentualIndividualEntregaSchema(
                    estudante_id=eid,
                    codigo_anonimo=str(info_e["codigo_anonimo"]),
                    total_atividades_esperadas=esp_e,
                    entregas_realizadas=real_e,
                    entregas_atrasadas=int(info_e["atrasadas"]),  # type: ignore[arg-type]
                    nao_entregas_apos_prazo=int(info_e["nao_entregues"]),  # type: ignore[arg-type]
                    pendentes_antes_prazo=int(info_e["pendentes"]),  # type: ignore[arg-type]
                    percentual_entregue=(
                        round((real_e / esp_e) * 100.0, 2)
                        if esp_e > 0
                        else None
                    ),
                    media_notas_disponiveis=_media_arredondada(
                        info_e["notas"]  # type: ignore[arg-type]
                    ),
                )
            )

        evolucao: list[EvolucaoParticipacaoItemSchema] = []
        for (per_ev, dt_ev), d_ev in sorted(
            agrup_evolucao.items(), key=lambda x: (x[0][1], x[0][0])
        ):
            esp_ev = d_ev["esperadas"]
            real_ev = d_ev["realizadas"]
            evolucao.append(
                EvolucaoParticipacaoItemSchema(
                    periodo_letivo=per_ev,
                    data_referencia=dt_ev,
                    total_atividades=d_ev["atividades"],
                    total_entregas_esperadas=esp_ev,
                    entregas_realizadas=real_ev,
                    taxa_entrega_percentual=(
                        round((real_ev / esp_ev) * 100.0, 2)
                        if esp_ev > 0
                        else None
                    ),
                )
            )

        taxa_geral = (
            round((realizadas_global / total_esperadas_global) * 100.0, 2)
            if total_esperadas_global > 0
            else None
        )

        return IndicadoresParticipacaoResponse(
            total_atividades=len(taxa_por_atividade),
            total_entregas_esperadas=total_esperadas_global,
            entregas_realizadas=realizadas_global,
            entregas_no_prazo=no_prazo_global,
            entregas_atrasadas=atrasadas_global,
            nao_entregas_apos_prazo=nao_entregues_global,
            atividades_pendentes_antes_prazo=pendentes_global,
            taxa_entrega_geral_percentual=taxa_geral,
            media_notas_disponiveis=_media_arredondada(
                notas_disponiveis_global
            ),
            taxa_por_atividade=taxa_por_atividade,
            taxa_por_turma=taxa_por_turma,
            percentual_por_estudante=percentual_estudantes,
            evolucao_participacao=evolucao,
        )

