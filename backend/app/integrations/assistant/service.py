"""
Serviço de construção segura, reutilização de indicadores e auditoria do Assistente IA (Fase 7).

Garante:
- Nenhuma duplicação de fórmulas de indicadores, avaliações, participação ou risco.
- Isolamento estrito de perfil, escola, turma e disciplina antes de montar o contexto.
- Registro auditável persistente de TODAS as tentativas (autorizadas e negadas) antes
  de retornar erros HTTP 403/404, sem armazenar PII, tokens ou segredos.
"""

from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.assistant.interfaces import (
    ProvedorLLMBase,
    ProvedorLLMNaoConfigurado,
)
from app.integrations.assistant.models import (
    AuditoriaConsultaIA,
    ResultadoAutorizacaoIA,
    TipoContextoAssistente,
)
from app.integrations.assistant.repository import AssistantAuditRepository
from app.integrations.assistant.schemas import (
    AuditoriaConsultaIAResponse,
    ContextoAssistenteEstruturado,
    MetadadosContextoAssistente,
    RequisicaoAssistenteLLM,
    RespostaAssistenteLLM,
    SolicitacaoContextoAssistente,
    StatusAssistenteResponse,
)
from app.integrations.prediction.service import PredictionService
from app.modules.acompanhamento.service import AcompanhamentoService
from app.modules.escolas.models import Escola
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.estudantes.service import EstudanteService
from app.modules.indicadores.repository import IndicadoresRepository
from app.modules.indicadores.service import (
    IndicadoresAvaliacoesService,
    IndicadoresGeraisService,
    IndicadoresParticipacaoService,
)
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario

GARANTIAS_PRIVACIDADE_PADRAO: list[str] = [
    "Dados estudantis anonimizados exclusivamente por `codigo_anonimo` (sem PII).",
    "Previsões probabilísticas separadas de métricas pedagógicas observadas.",
    "Nenhuma variável de desfecho pós-fato (`situacao_final`) usada em contexto preditivo.",
    "Auditoria persistente de solicitação e autorização registrada.",
]

DIRETRIZES_INTERPRETACAO_PADRAO: list[str] = [
    "Diferenciar claramente dados observados (frequência, notas, entregas, acertos) de estimativas preditivas.",
    "Não apresentar faixa ou pontuação de risco como diagnóstico definitivo.",
    "Respeitar exclusivamente o escopo autorizado para o usuário solicitante.",
]


def _filtros_estruturais(solicitacao: SolicitacaoContextoAssistente) -> dict[str, Any]:
    """Extrai apenas filtros estruturais não sensíveis para trilha de auditoria."""
    return {
        "tipo_contexto": solicitacao.tipo_contexto.value,
        "escola_id": str(solicitacao.escola_id) if solicitacao.escola_id else None,
        "turma_id": str(solicitacao.turma_id) if solicitacao.turma_id else None,
        "disciplina_id": (
            str(solicitacao.disciplina_id) if solicitacao.disciplina_id else None
        ),
        "estudante_id": (
            str(solicitacao.estudante_id) if solicitacao.estudante_id else None
        ),
        "ano_letivo": solicitacao.ano_letivo,
        "periodo_letivo": solicitacao.periodo_letivo,
        "modelo_nome": solicitacao.modelo_nome,
        "modelo_versao": solicitacao.modelo_versao,
        "incluir_acompanhamentos": solicitacao.incluir_acompanhamentos,
    }


class AssistenteContextoService:
    """Orquestra autorização, auditoria e montagem de contexto estruturado para IA."""

    @staticmethod
    def obter_status(
        provedor: Optional[ProvedorLLMBase] = None,
    ) -> StatusAssistenteResponse:
        prov = provedor or ProvedorLLMNaoConfigurado()
        configurado = prov.esta_configurado()
        return StatusAssistenteResponse(
            provedor_llm_configurado=configurado,
            provedor_nome=prov.nome_provedor,
            modo_operacao=(
                "provedor_externo_ativo"
                if configurado
                else "somente_contexto_auditado_sem_llm"
            ),
            niveis_contexto_suportados=[t.value for t in TipoContextoAssistente],
            auditoria_ativa=True,
            mensagem=(
                "Provedor LLM externo conectado e ativo."
                if configurado
                else (
                    "Camada de contexto autorizado e auditoria ativa. "
                    "Nenhum provedor LLM externo está conectado nesta fase (Fase 7); "
                    "respostas generativas não são simuladas."
                )
            ),
        )

    @staticmethod
    def _registrar_auditoria(
        db: Session,
        usuario: Usuario,
        solicitacao: SolicitacaoContextoAssistente,
        resultado: ResultadoAutorizacaoIA,
        motivo: str,
        escola_fk_segura: Optional[uuid.UUID] = None,
        turma_fk_segura: Optional[uuid.UUID] = None,
        estudante_fk_segura: Optional[uuid.UUID] = None,
        fontes: Optional[list[str]] = None,
    ) -> AuditoriaConsultaIA:
        registro = AuditoriaConsultaIA(
            usuario_id=usuario.id,
            papel_usuario=usuario.papel.value,
            escola_id_solicitada=escola_fk_segura,
            turma_id_solicitada=turma_fk_segura,
            estudante_id_solicitado=estudante_fk_segura,
            tipo_contexto=solicitacao.tipo_contexto,
            resultado_autorizacao=resultado,
            motivo_decisao=motivo[:255],
            filtros_utilizados=_filtros_estruturais(solicitacao),
            resumo_fontes_consultadas=fontes,
        )
        return AssistantAuditRepository.registrar(db, registro)

    @staticmethod
    def _resolver_fks_existentes(
        db: Session,
        solicitacao: SolicitacaoContextoAssistente,
    ) -> tuple[
        Optional[Escola],
        Optional[Turma],
        Optional[Any],
    ]:
        escola_obj = None
        if solicitacao.escola_id is not None:
            escola_obj = db.execute(
                select(Escola).where(Escola.id == solicitacao.escola_id)
            ).scalar_one_or_none()

        turma_obj = None
        if solicitacao.turma_id is not None:
            turma_obj = db.execute(
                select(Turma).where(Turma.id == solicitacao.turma_id)
            ).scalar_one_or_none()

        estudante_obj = None
        if solicitacao.estudante_id is not None:
            estudante_obj = EstudanteRepository.get_by_id(
                db, solicitacao.estudante_id
            )

        return escola_obj, turma_obj, estudante_obj

    @staticmethod
    def construir_contexto_autorizado(
        db: Session,
        solicitacao: SolicitacaoContextoAssistente,
        usuario: Usuario,
    ) -> ContextoAssistenteEstruturado:
        """
        Valida rigorosamente autorização e escopo, audita a decisão no banco e monta
        o contexto estruturado reutilizando os serviços oficiais do Vértice.
        """
        escola_obj, turma_obj, estudante_obj = (
            AssistenteContextoService._resolver_fks_existentes(db, solicitacao)
        )
        escola_fk = escola_obj.id if escola_obj else None
        turma_fk = turma_obj.id if turma_obj else None
        estudante_fk = estudante_obj.id if estudante_obj else None

        # 1) Administrador NÃO acessa contexto pedagógico de escolas/turmas/estudantes
        if usuario.papel not in {PapelUsuario.GESTOR, PapelUsuario.PROFESSOR}:
            motivo = (
                "Acesso negado: perfil administrativo não possui acesso pedagógico ao contexto de IA."
            )
            AssistenteContextoService._registrar_auditoria(
                db=db,
                usuario=usuario,
                solicitacao=solicitacao,
                resultado=ResultadoAutorizacaoIA.NEGADO,
                motivo=motivo,
                escola_fk_segura=escola_fk,
                turma_fk_segura=turma_fk,
                estudante_fk_segura=estudante_fk,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=motivo,
            )

        # 2) Validação de existência e escopo específico por nível de contexto
        escola_efetiva_id: Optional[uuid.UUID] = solicitacao.escola_id
        turma_efetiva_id: Optional[uuid.UUID] = solicitacao.turma_id

        if solicitacao.tipo_contexto == TipoContextoAssistente.TURMA:
            if turma_obj is None:
                motivo = "Turma solicitada não encontrada."
                AssistenteContextoService._registrar_auditoria(
                    db=db,
                    usuario=usuario,
                    solicitacao=solicitacao,
                    resultado=ResultadoAutorizacaoIA.NEGADO,
                    motivo=motivo,
                    escola_fk_segura=escola_fk,
                    turma_fk_segura=None,
                    estudante_fk_segura=estudante_fk,
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=motivo,
                )
            if escola_efetiva_id is None:
                escola_efetiva_id = turma_obj.escola_id
            elif escola_efetiva_id != turma_obj.escola_id:
                motivo = "Conflito de escopo: turma não pertence à escola informada."
                AssistenteContextoService._registrar_auditoria(
                    db=db,
                    usuario=usuario,
                    solicitacao=solicitacao,
                    resultado=ResultadoAutorizacaoIA.NEGADO,
                    motivo=motivo,
                    escola_fk_segura=escola_fk,
                    turma_fk_segura=turma_fk,
                    estudante_fk_segura=estudante_fk,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=motivo,
                )

        if solicitacao.tipo_contexto == TipoContextoAssistente.INDIVIDUAL:
            if estudante_obj is None:
                motivo = "Estudante solicitado não encontrado."
                AssistenteContextoService._registrar_auditoria(
                    db=db,
                    usuario=usuario,
                    solicitacao=solicitacao,
                    resultado=ResultadoAutorizacaoIA.NEGADO,
                    motivo=motivo,
                    escola_fk_segura=escola_fk,
                    turma_fk_segura=turma_fk,
                    estudante_fk_segura=None,
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=motivo,
                )
            if (
                solicitacao.escola_id is not None
                and estudante_obj.escola_id != solicitacao.escola_id
            ):
                motivo = "Acesso negado: estudante não pertence à escola solicitada."
                AssistenteContextoService._registrar_auditoria(
                    db=db,
                    usuario=usuario,
                    solicitacao=solicitacao,
                    resultado=ResultadoAutorizacaoIA.NEGADO,
                    motivo=motivo,
                    escola_fk_segura=escola_fk,
                    turma_fk_segura=turma_fk,
                    estudante_fk_segura=estudante_fk,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=motivo,
                )
            if escola_efetiva_id is None:
                escola_efetiva_id = estudante_obj.escola_id

        # 3) Validação estrita de escola/turma/disciplina contra o usuário
        try:
            escolas_aut = IndicadoresRepository.validar_filtros_escopo(
                db=db,
                usuario=usuario,
                escola_id=escola_efetiva_id,
                turma_id=turma_efetiva_id,
                disciplina_id=solicitacao.disciplina_id,
            )
        except HTTPException as exc:
            AssistenteContextoService._registrar_auditoria(
                db=db,
                usuario=usuario,
                solicitacao=solicitacao,
                resultado=ResultadoAutorizacaoIA.NEGADO,
                motivo=str(exc.detail),
                escola_fk_segura=escola_fk or escola_efetiva_id,
                turma_fk_segura=turma_fk,
                estudante_fk_segura=estudante_fk,
            )
            raise

        # Para contexto INDIVIDUAL, valida ainda o acesso ao estudante específico
        estudante_hist = None
        if solicitacao.tipo_contexto == TipoContextoAssistente.INDIVIDUAL:
            assert solicitacao.estudante_id is not None
            try:
                estudante_hist = EstudanteService.obter_estudante_com_historico(
                    db=db,
                    estudante_id=solicitacao.estudante_id,
                    usuario_solicitante=usuario,
                )
            except HTTPException as exc:
                motivo = "Acesso negado: estudante fora do escopo autorizado."
                AssistenteContextoService._registrar_auditoria(
                    db=db,
                    usuario=usuario,
                    solicitacao=solicitacao,
                    resultado=ResultadoAutorizacaoIA.NEGADO,
                    motivo=motivo,
                    escola_fk_segura=escola_fk or estudante_obj.escola_id,  # type: ignore[union-attr]
                    turma_fk_segura=turma_fk,
                    estudante_fk_segura=estudante_fk,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=motivo,
                ) from exc

        if escola_efetiva_id is None and escolas_aut:
            escola_efetiva_id = sorted(escolas_aut)[0]

        # 4) Construção do contexto reutilizando exclusivamente os serviços reais do Vértice
        fontes_utilizadas: list[str] = []
        ind_gerais = None
        ind_avaliacoes = None
        ind_participacao = None
        resumo_risco = None
        previsoes_est = None
        acompanhamentos = []

        if solicitacao.tipo_contexto in {
            TipoContextoAssistente.ESCOLA,
            TipoContextoAssistente.TURMA,
        }:
            ind_gerais = IndicadoresGeraisService.calcular_indicadores_gerais(
                db=db,
                usuario=usuario,
                escola_id=escola_efetiva_id,
                turma_id=turma_efetiva_id,
                disciplina_id=solicitacao.disciplina_id,
                ano_letivo=solicitacao.ano_letivo,
                periodo_letivo=solicitacao.periodo_letivo,
                modelo_nome=solicitacao.modelo_nome,
                modelo_versao=solicitacao.modelo_versao,
            )
            fontes_utilizadas.append("IndicadoresGeraisService")

            ind_avaliacoes = IndicadoresAvaliacoesService.calcular_indicadores_avaliacoes(
                db=db,
                usuario=usuario,
                escola_id=escola_efetiva_id,
                turma_id=turma_efetiva_id,
                disciplina_id=solicitacao.disciplina_id,
                ano_letivo=solicitacao.ano_letivo,
                periodo_letivo=solicitacao.periodo_letivo,
            )
            fontes_utilizadas.append("IndicadoresAvaliacoesService")

            ind_participacao = (
                IndicadoresParticipacaoService.calcular_indicadores_participacao(
                    db=db,
                    usuario=usuario,
                    escola_id=escola_efetiva_id,
                    turma_id=turma_efetiva_id,
                    disciplina_id=solicitacao.disciplina_id,
                    ano_letivo=solicitacao.ano_letivo,
                    periodo_letivo=solicitacao.periodo_letivo,
                )
            )
            fontes_utilizadas.append("IndicadoresParticipacaoService")

            resumo_risco = PredictionService.obter_resumo_previsoes(
                db=db,
                usuario=usuario,
                escola_id=escola_efetiva_id,
                turma_id=turma_efetiva_id,
                disciplina_id=solicitacao.disciplina_id,
                ano_letivo=solicitacao.ano_letivo,
                periodo_letivo=solicitacao.periodo_letivo,
                modelo_nome=solicitacao.modelo_nome,
                modelo_versao=solicitacao.modelo_versao,
            )
            fontes_utilizadas.append("PredictionService")

            if solicitacao.incluir_acompanhamentos:
                acompanhamentos = AcompanhamentoService.listar_acompanhamentos(
                    db=db,
                    usuario_autenticado=usuario,
                    turma_id=turma_efetiva_id,
                    limit=20,
                )
                fontes_utilizadas.append("AcompanhamentoService")
        else:
            # INDIVIDUAL
            assert solicitacao.estudante_id is not None and estudante_hist is not None
            fontes_utilizadas.append("EstudanteService")

            ind_participacao = (
                IndicadoresParticipacaoService.calcular_indicadores_participacao(
                    db=db,
                    usuario=usuario,
                    escola_id=estudante_hist.escola_id,
                    turma_id=turma_efetiva_id,
                    disciplina_id=solicitacao.disciplina_id,
                    ano_letivo=solicitacao.ano_letivo,
                    periodo_letivo=solicitacao.periodo_letivo,
                    estudante_id=solicitacao.estudante_id,
                )
            )
            fontes_utilizadas.append("IndicadoresParticipacaoService")

            previsoes_est = PredictionService.obter_historico_estudante(
                db=db,
                estudante_id=solicitacao.estudante_id,
                usuario=usuario,
                modelo_nome=solicitacao.modelo_nome,
                modelo_versao=solicitacao.modelo_versao,
            )
            fontes_utilizadas.append("PredictionService")

            if solicitacao.incluir_acompanhamentos:
                acompanhamentos = AcompanhamentoService.listar_acompanhamentos(
                    db=db,
                    usuario_autenticado=usuario,
                    turma_id=turma_efetiva_id,
                    estudante_id=solicitacao.estudante_id,
                    limit=20,
                )
                fontes_utilizadas.append("AcompanhamentoService")

        # 5) Registro auditável da autorização
        escola_aud_fk = escola_fk or (
            escola_efetiva_id
            if (
                escola_efetiva_id is not None
                and db.execute(
                    select(Escola.id).where(Escola.id == escola_efetiva_id)
                ).scalar_one_or_none()
                is not None
            )
            else None
        )
        auditoria = AssistenteContextoService._registrar_auditoria(
            db=db,
            usuario=usuario,
            solicitacao=solicitacao,
            resultado=ResultadoAutorizacaoIA.AUTORIZADO,
            motivo=f"Contexto `{solicitacao.tipo_contexto.value}` autorizado e estruturado.",
            escola_fk_segura=escola_aud_fk,
            turma_fk_segura=turma_fk,
            estudante_fk_segura=estudante_fk,
            fontes=fontes_utilizadas,
        )

        escopo_pedagogico: dict[str, Any] = {
            "nivel_contexto": solicitacao.tipo_contexto.value,
            "papel_solicitante": usuario.papel.value,
            "escola_id": str(escola_efetiva_id) if escola_efetiva_id else None,
            "turma_id": str(turma_efetiva_id) if turma_efetiva_id else None,
            "turma_nome": turma_obj.nome if turma_obj else None,
            "disciplina_id": (
                str(solicitacao.disciplina_id) if solicitacao.disciplina_id else None
            ),
            "estudante_id": (
                str(solicitacao.estudante_id) if solicitacao.estudante_id else None
            ),
            "codigo_anonimo": estudante_hist.codigo_anonimo if estudante_hist else None,
            "ano_letivo": solicitacao.ano_letivo,
            "periodo_letivo": solicitacao.periodo_letivo,
            "escopo_restrito_professor": usuario.papel == PapelUsuario.PROFESSOR,
        }

        metadados = MetadadosContextoAssistente(
            auditoria_id=auditoria.id,
            gerado_em=datetime.now(timezone.utc),
            tipo_contexto=solicitacao.tipo_contexto,
            usuario_papel=usuario.papel.value,
            escola_id=escola_efetiva_id,
            turma_id=turma_efetiva_id,
            disciplina_id=solicitacao.disciplina_id,
            estudante_id=solicitacao.estudante_id,
            codigo_anonimo=estudante_hist.codigo_anonimo if estudante_hist else None,
            ano_letivo=solicitacao.ano_letivo,
            periodo_letivo=solicitacao.periodo_letivo,
            anonimizacao_ativa=True,
            garantias_privacidade=GARANTIAS_PRIVACIDADE_PADRAO,
            fontes_utilizadas=fontes_utilizadas,
        )

        return ContextoAssistenteEstruturado(
            metadados=metadados,
            escopo_pedagogico=escopo_pedagogico,
            indicadores_gerais=ind_gerais,
            indicadores_avaliacoes=ind_avaliacoes,
            indicadores_participacao=ind_participacao,
            resumo_previsoes_risco=resumo_risco,
            estudante_historico=estudante_hist,
            previsoes_estudante=previsoes_est,
            acompanhamentos_recentes=acompanhamentos,
            diretrizes_interpretacao=DIRETRIZES_INTERPRETACAO_PADRAO,
        )

    @staticmethod
    def consultar_com_provedor(
        db: Session,
        solicitacao: SolicitacaoContextoAssistente,
        pergunta_usuario: str,
        usuario: Usuario,
        provedor: Optional[ProvedorLLMBase] = None,
    ) -> RespostaAssistenteLLM:
        """
        Prepara contexto auditado e delega para `ProvedorLLMBase`.
        Na Fase 7 usa `ProvedorLLMNaoConfigurado`, falhando de forma explícita e controlada (503).
        """
        contexto = AssistenteContextoService.construir_contexto_autorizado(
            db=db,
            solicitacao=solicitacao,
            usuario=usuario,
        )
        prov = provedor or ProvedorLLMNaoConfigurado()
        req = RequisicaoAssistenteLLM(
            pergunta_usuario=pergunta_usuario,
            contexto=contexto,
        )
        return prov.gerar_resposta(req)

    @staticmethod
    def listar_auditoria(
        db: Session,
        usuario: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        resultado_autorizacao: Optional[ResultadoAutorizacaoIA] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditoriaConsultaIAResponse]:
        escola_filtro = escola_id
        usuario_filtro = None

        if usuario.papel == PapelUsuario.ADMINISTRADOR:
            pass
        elif usuario.papel == PapelUsuario.GESTOR:
            if usuario.escola_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Gestor sem escola vinculada.",
                )
            if escola_id is not None and escola_id != usuario.escola_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: auditoria solicitada pertence a outra escola.",
                )
            escola_filtro = usuario.escola_id
        else:
            # Professor visualiza somente suas próprias consultas registradas
            usuario_filtro = usuario.id

        regs = AssistantAuditRepository.listar(
            db=db,
            escola_id=escola_filtro,
            usuario_id=usuario_filtro,
            resultado_autorizacao=resultado_autorizacao,
            skip=skip,
            limit=limit,
        )
        return [AuditoriaConsultaIAResponse.model_validate(r) for r in regs]
