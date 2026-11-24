"""
Serviço de construção segura, reutilização de indicadores e auditoria do Assistente IA (Fase 7).

Garante:
- Nenhuma duplicação de fórmulas de indicadores, avaliações, participação ou risco.
- Isolamento estrito de perfil, escola, turma e disciplina antes de montar o contexto.
- Registro auditável persistente de TODAS as tentativas (autorizadas e negadas) antes
  de retornar erros HTTP 403/404, sem armazenar PII, tokens ou segredos.
"""

from datetime import datetime, timezone
import json
import secrets
import threading
import time
from typing import Any, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.assistant.interfaces import (
    ProvedorLLMBase,
    ProvedorLLMNaoConfigurado,
)
from app.integrations.assistant.models import (
    AuditoriaConsultaIA,
    ResultadoAutorizacaoIA,
    TipoContextoAssistente,
)
from app.integrations.assistant.ollama import ProvedorLLMOllama
from app.integrations.assistant.repository import AssistantAuditRepository
from app.integrations.assistant.schemas import (
    AuditoriaConsultaIAResponse,
    ContextoAssistenteEstruturado,
    DocumentoAssistenteLLM,
    MetadadosContextoAssistente,
    MensagemConversaLLM,
    RequisicaoAssistenteLLM,
    RespostaAssistenteLLM,
    SolicitacaoContextoAssistente,
    StatusAssistenteResponse,
)
from app.integrations.prediction.service import PredictionService
from app.modules.acompanhamento.service import AcompanhamentoService
from app.modules.escolas.models import Escola
from app.modules.escolas.service import _escola_ids_autorizadas_professor
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


def _criar_provedor_llm_padrao() -> ProvedorLLMBase:
    if settings.ASSISTENTE_LLM_PROVEDOR == "ollama":
        return ProvedorLLMOllama(
            base_url=settings.ASSISTENTE_OLLAMA_BASE_URL,
            modelo=settings.ASSISTENTE_OLLAMA_MODELO,
            timeout_segundos=settings.ASSISTENTE_OLLAMA_TIMEOUT_SEGUNDOS,
        )
    return ProvedorLLMNaoConfigurado()


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
        "conversation_id": (
            str(solicitacao.conversation_id)
            if solicitacao.conversation_id
            else None
        ),
    }


class AssistenteContextoService:
    """Orquestra autorização, auditoria e montagem de contexto estruturado para IA."""

    _cache_contextos: dict[str, dict[str, Any]] = {}
    _cache_lock = threading.RLock()

    @staticmethod
    def _criar_provedor_para_stream() -> ProvedorLLMBase:
        return _criar_provedor_llm_padrao()

    @staticmethod
    def _fingerprint_contexto(
        usuario: Usuario,
        solicitacao: SolicitacaoContextoAssistente,
    ) -> str:
        dados = _filtros_estruturais(solicitacao)
        dados["usuario_id"] = str(usuario.id)
        dados.pop("conversation_id", None)
        return json.dumps(dados, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _obter_contexto_em_cache(
        usuario: Usuario,
        solicitacao: SolicitacaoContextoAssistente,
        db: Session,
    ) -> Optional[ContextoAssistenteEstruturado]:
        cache_id = solicitacao.context_cache_id
        if not cache_id:
            return None
        now = time.monotonic()
        with AssistenteContextoService._cache_lock:
            entrada = AssistenteContextoService._cache_contextos.get(cache_id)
            if not entrada:
                return None
            if entrada["expira_em"] <= now:
                AssistenteContextoService._cache_contextos.pop(cache_id, None)
                return None
            if entrada["usuario_id"] != str(usuario.id):
                return None
            if (
                entrada.get("conversation_id")
                and solicitacao.conversation_id
                and entrada["conversation_id"] != str(solicitacao.conversation_id)
            ):
                return None
            if entrada["fingerprint"] != AssistenteContextoService._fingerprint_contexto(
                usuario, solicitacao
            ):
                return None

        if usuario.papel not in {PapelUsuario.GESTOR, PapelUsuario.PROFESSOR}:
            AssistenteContextoService._cache_contextos.pop(cache_id, None)
            return None

        try:
            escola_obj, turma_obj, estudante_obj = (
                AssistenteContextoService._resolver_fks_existentes(db, solicitacao)
            )
            escola_efetiva = solicitacao.escola_id
            turma_efetiva = solicitacao.turma_id
            if solicitacao.tipo_contexto == TipoContextoAssistente.TURMA:
                if turma_obj is None:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, "Turma solicitada não encontrada.")
                escola_efetiva = solicitacao.escola_id or turma_obj.escola_id
            if solicitacao.tipo_contexto == TipoContextoAssistente.INDIVIDUAL:
                if estudante_obj is None:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, "Estudante solicitado não encontrado.")
                escola_efetiva = solicitacao.escola_id or estudante_obj.escola_id
                EstudanteService.obter_estudante_com_historico(
                    db=db,
                    estudante_id=solicitacao.estudante_id,
                    usuario_solicitante=usuario,
                )
            IndicadoresRepository.validar_filtros_escopo(
                db=db,
                usuario=usuario,
                escola_id=escola_efetiva,
                turma_id=turma_efetiva,
                disciplina_id=solicitacao.disciplina_id,
            )
        except HTTPException:
            AssistenteContextoService._cache_contextos.pop(cache_id, None)
            raise

        entrada["ultimo_acesso"] = now
        return entrada["contexto"].model_copy(deep=True)

    @staticmethod
    def _armazenar_contexto_em_cache(
        usuario: Usuario,
        solicitacao: SolicitacaoContextoAssistente,
        contexto: ContextoAssistenteEstruturado,
    ) -> ContextoAssistenteEstruturado:
        cache_id = secrets.token_urlsafe(32)
        ttl = settings.ASSISTENTE_CONTEXTO_CACHE_TTL_SEGUNDOS
        with AssistenteContextoService._cache_lock:
            expirados = [
                chave
                for chave, entrada in AssistenteContextoService._cache_contextos.items()
                if entrada["expira_em"] <= time.monotonic()
            ]
            for chave in expirados:
                AssistenteContextoService._cache_contextos.pop(chave, None)
            limite = settings.ASSISTENTE_CONTEXTO_CACHE_MAX_ITENS
            while len(AssistenteContextoService._cache_contextos) >= limite:
                chave_antiga = min(
                    AssistenteContextoService._cache_contextos,
                    key=lambda chave: AssistenteContextoService._cache_contextos[chave]["ultimo_acesso"],
                )
                AssistenteContextoService._cache_contextos.pop(chave_antiga, None)
            AssistenteContextoService._cache_contextos[cache_id] = {
                "usuario_id": str(usuario.id),
                "conversation_id": (
                    str(solicitacao.conversation_id)
                    if solicitacao.conversation_id
                    else None
                ),
                "fingerprint": AssistenteContextoService._fingerprint_contexto(usuario, solicitacao),
                "expira_em": time.monotonic() + ttl,
                "ultimo_acesso": time.monotonic(),
                "contexto": contexto,
            }
        metadados = contexto.metadados.model_copy(update={"context_cache_id": cache_id})
        return contexto.model_copy(update={"metadados": metadados})

    @classmethod
    def invalidar_cache(
        cls,
        *,
        usuario_id: Optional[uuid.UUID | str] = None,
        escola_id: Optional[uuid.UUID | str] = None,
        turma_id: Optional[uuid.UUID | str] = None,
        estudante_id: Optional[uuid.UUID | str] = None,
        cache_id: Optional[str] = None,
    ) -> int:
        """Invalida seletivamente entradas do cache de contexto pedagógico."""
        removidos = 0
        with cls._cache_lock:
            chaves = list(cls._cache_contextos.keys())
            for chave in chaves:
                entrada = cls._cache_contextos.get(chave)
                if not entrada:
                    continue
                remover = False
                if cache_id and chave == cache_id:
                    remover = True
                if usuario_id and entrada.get("usuario_id") == str(usuario_id):
                    remover = True
                ctx = entrada.get("contexto")
                if ctx and hasattr(ctx, "metadados"):
                    if escola_id and str(ctx.metadados.escola_id) == str(escola_id):
                        remover = True
                    if turma_id and str(ctx.metadados.turma_id) == str(turma_id):
                        remover = True
                    if estudante_id and str(ctx.metadados.estudante_id) == str(estudante_id):
                        remover = True
                if remover:
                    cls._cache_contextos.pop(chave, None)
                    removidos += 1
        return removidos

    @classmethod
    def limpar_cache_completo(cls) -> None:
        """Limpa integralmente o cache em memória (manutenção e testes)."""
        with cls._cache_lock:
            cls._cache_contextos.clear()

    @classmethod
    def obter_ou_construir_contexto_autorizado(
        cls,
        *,
        db: Session,
        solicitacao: SolicitacaoContextoAssistente,
        usuario: Usuario,
        motivo_reuso: str = "Consulta autorizada reutilizando contexto preparado e revalidado.",
    ) -> tuple[ContextoAssistenteEstruturado, bool]:
        """Recupera contexto em cache revalidado ou constrói novo contexto auditado."""
        contexto = cls._obter_contexto_em_cache(
            usuario=usuario,
            solicitacao=solicitacao,
            db=db,
        )
        if contexto is not None:
            request_id = uuid.uuid4()
            auditoria = cls._registrar_auditoria(
                db=db,
                usuario=usuario,
                solicitacao=solicitacao,
                resultado=ResultadoAutorizacaoIA.AUTORIZADO,
                motivo=motivo_reuso,
                request_id=request_id,
                escola_fk_segura=contexto.metadados.escola_id,
                turma_fk_segura=contexto.metadados.turma_id,
                estudante_fk_segura=contexto.metadados.estudante_id,
                fontes=contexto.metadados.fontes_utilizadas,
            )
            metadados = contexto.metadados.model_copy(
                update={
                    "auditoria_id": auditoria.id,
                    "request_id": request_id,
                    "gerado_em": datetime.now(timezone.utc),
                }
            )
            return contexto.model_copy(update={"metadados": metadados}), True

        novo_contexto = cls.construir_contexto_autorizado(
            db=db,
            solicitacao=solicitacao,
            usuario=usuario,
        )
        return novo_contexto, False

    @staticmethod
    def obter_status(
        provedor: Optional[ProvedorLLMBase] = None,
    ) -> StatusAssistenteResponse:
        prov = provedor or _criar_provedor_llm_padrao()
        configurado = prov.esta_configurado()
        return StatusAssistenteResponse(
            provedor_llm_configurado=configurado,
            provedor_nome=prov.nome_provedor,
            modo_operacao=(
                "ollama_local_configurado"
                if configurado
                else "somente_contexto_auditado_sem_llm"
            ),
            niveis_contexto_suportados=[t.value for t in TipoContextoAssistente],
            auditoria_ativa=True,
            mensagem=(
                "Modelo Ollama local configurado; as consultas permanecem no ambiente local."
                if configurado
                else (
                    "Contexto autorizado e auditoria ativos. Configure o Ollama local "
                    "e um modelo gratuito para habilitar respostas generativas."
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
        request_id: uuid.UUID,
        escola_fk_segura: Optional[uuid.UUID] = None,
        turma_fk_segura: Optional[uuid.UUID] = None,
        estudante_fk_segura: Optional[uuid.UUID] = None,
        fontes: Optional[list[str]] = None,
    ) -> AuditoriaConsultaIA:
        registro = AuditoriaConsultaIA(
            request_id=request_id,
            conversation_id=solicitacao.conversation_id,
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
        Valida rigorosamente autorização e escopo, gera `request_id` único no backend,
        audita a decisão no banco (inclusive em falhas inesperadas) e monta o contexto estruturado.
        """
        request_id = uuid.uuid4()
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
                request_id=request_id,
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
                    request_id=request_id,
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
                    request_id=request_id,
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
                    request_id=request_id,
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
                    request_id=request_id,
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
                request_id=request_id,
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
                    request_id=request_id,
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

        # 4) Construção do contexto reutilizando exclusivamente os serviços reais do Vértice
        fontes_utilizadas: list[str] = []
        ind_gerais = None
        ind_avaliacoes = None
        ind_participacao = None
        resumo_risco = None
        previsoes_est = None
        acompanhamentos = []

        try:
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

                ind_avaliacoes = (
                    IndicadoresAvaliacoesService.calcular_indicadores_avaliacoes(
                        db=db,
                        usuario=usuario,
                        escola_id=escola_efetiva_id,
                        turma_id=turma_efetiva_id,
                        disciplina_id=solicitacao.disciplina_id,
                        ano_letivo=solicitacao.ano_letivo,
                        periodo_letivo=solicitacao.periodo_letivo,
                    )
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
        except HTTPException as exc:
            db.rollback()
            resultado_falha = (
                ResultadoAutorizacaoIA.NEGADO
                if exc.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
                else ResultadoAutorizacaoIA.ERRO_EXECUCAO
            )
            AssistenteContextoService._registrar_auditoria(
                db=db,
                usuario=usuario,
                solicitacao=solicitacao,
                resultado=resultado_falha,
                motivo=f"Falha controlada durante montagem do contexto ({exc.status_code}).",
                request_id=request_id,
                escola_fk_segura=escola_aud_fk,
                turma_fk_segura=turma_fk,
                estudante_fk_segura=estudante_fk,
                fontes=fontes_utilizadas,
            )
            raise
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            AssistenteContextoService._registrar_auditoria(
                db=db,
                usuario=usuario,
                solicitacao=solicitacao,
                resultado=ResultadoAutorizacaoIA.ERRO_EXECUCAO,
                motivo=f"Erro inesperado na montagem do contexto: {type(exc).__name__}.",
                request_id=request_id,
                escola_fk_segura=escola_aud_fk,
                turma_fk_segura=turma_fk,
                estudante_fk_segura=estudante_fk,
                fontes=fontes_utilizadas,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Não foi possível concluir a montagem segura do contexto "
                    f"(request_id={request_id})."
                ),
            ) from exc

        # 5) Registro auditável somente após montagem integralmente concluída
        auditoria = AssistenteContextoService._registrar_auditoria(
            db=db,
            usuario=usuario,
            solicitacao=solicitacao,
            resultado=ResultadoAutorizacaoIA.AUTORIZADO,
            motivo=f"Contexto `{solicitacao.tipo_contexto.value}` autorizado e estruturado.",
            request_id=request_id,
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
            request_id=request_id,
            conversation_id=solicitacao.conversation_id,
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

        contexto = ContextoAssistenteEstruturado(
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
        return AssistenteContextoService._armazenar_contexto_em_cache(
            usuario=usuario,
            solicitacao=solicitacao,
            contexto=contexto,
        )

    @staticmethod
    def consultar_com_provedor(
        db: Session,
        solicitacao: SolicitacaoContextoAssistente,
        pergunta_usuario: str,
        usuario: Usuario,
        provedor: Optional[ProvedorLLMBase] = None,
        historico_mensagens: Optional[list[MensagemConversaLLM]] = None,
        documentos_anexados: Optional[list[DocumentoAssistenteLLM]] = None,
    ) -> RespostaAssistenteLLM:
        """
        Prepara contexto auditado e delega para `ProvedorLLMBase`.
        O provedor padrão usa Ollama local quando configurado; sem ele, falha explicitamente (503).
        """
        contexto, _ = AssistenteContextoService.obter_ou_construir_contexto_autorizado(
            db=db,
            solicitacao=solicitacao,
            usuario=usuario,
        )
        prov = provedor or _criar_provedor_llm_padrao()
        req = RequisicaoAssistenteLLM(
            pergunta_usuario=pergunta_usuario,
            contexto=contexto,
            historico_mensagens=historico_mensagens or [],
            documentos_anexados=documentos_anexados or [],
        )
        return prov.gerar_resposta(req)

    @staticmethod
    def listar_auditoria(
        db: Session,
        usuario: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        resultado_autorizacao: Optional[ResultadoAutorizacaoIA] = None,
        request_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
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
            # Professor visualiza somente suas próprias consultas registradas e apenas dentro de escolas do seu escopo
            if escola_id is not None:
                escolas_prof = _escola_ids_autorizadas_professor(db, usuario)
                if escola_id not in escolas_prof:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Acesso negado: auditoria solicitada pertence a escola fora do escopo do professor.",
                    )
            usuario_filtro = usuario.id

        regs = AssistantAuditRepository.listar(
            db=db,
            escola_id=escola_filtro,
            usuario_id=usuario_filtro,
            resultado_autorizacao=resultado_autorizacao,
            request_id=request_id,
            conversation_id=conversation_id,
            skip=skip,
            limit=limit,
        )
        respostas = [AuditoriaConsultaIAResponse.model_validate(r) for r in regs]
        if usuario.papel == PapelUsuario.ADMINISTRADOR:
            respostas_redigidas: list[AuditoriaConsultaIAResponse] = []
            for resp in respostas:
                filtros_limpos = (
                    {
                        k: v
                        for k, v in resp.filtros_utilizados.items()
                        if k not in {"estudante_id", "codigo_anonimo"}
                    }
                    if isinstance(resp.filtros_utilizados, dict)
                    else resp.filtros_utilizados
                )
                respostas_redigidas.append(
                    resp.model_copy(
                        update={
                            "estudante_id_solicitado": None,
                            "filtros_utilizados": filtros_limpos,
                        }
                    )
                )
            return respostas_redigidas
        return respostas
