"""
Camada de serviço para Administração Técnica e Auditoria de Operações Sensíveis.
"""

import re
from typing import Any, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.assistant.models import AuditoriaConsultaIA
from app.integrations.prediction.models import CredencialIntegracaoPredicao
from app.modules.admin.models import AuditoriaOperacaoTecnica
from app.modules.admin.repository import AdminAuditRepository
from app.modules.admin.schemas import (
    AuditoriaOperacaoTecnicaResponse,
    ResumoOperacionalAdminResponse,
)
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario

_CHAVES_PERMITIDAS_AUDITORIA = {
    "prefixo_chave",
    "senha_alterada",
}
_CHAVES_SENSIVEIS_AUDITORIA = {
    "senha",
    "senha_hash",
    "password",
    "hash",
    "hash_chave",
    "chave_secreta",
    "access_token",
    "token",
    "secret",
    "secret_key",
    "api_key",
    "credencial",
    "estudante_id",
    "codigo_anonimo",
    "nota",
    "media_geral",
    "frequencia_percentual",
    "faltas",
    "boletins",
    "respostas",
    "alternativa_marcada",
    "alternativa_correta",
    "pontuacao_risco",
    "faixa_risco",
}
_TERMOS_CHAVE_SEGREDO = (
    "senha",
    "password",
    "secret",
    "token",
    "hash",
    "chave_secreta",
    "api_key",
    "credencial",
)
_PADROES_VALOR_SENSIVEL = (
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    re.compile(r"\$(?:argon2[a-z]*|2[aby])\$", re.IGNORECASE),
    re.compile(r"\bvtx_ml_[A-Za-z0-9_-]{14,}", re.IGNORECASE),
)


def _valor_texto_sensivel(valor: str) -> bool:
    return any(p.search(valor) for p in _PADROES_VALOR_SENSIVEL)


def _sanitizar_valor(valor: Any) -> Any:
    if isinstance(valor, dict):
        return _sanitizar_detalhes(valor)
    if isinstance(valor, list):
        return [_sanitizar_valor(item) for item in valor]
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, str) and _valor_texto_sensivel(valor):
        return "[REDIGIDO]"
    return valor


def _sanitizar_detalhes(detalhes: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Remove recursivamente segredos, tokens e chaves pedagógicas antes de persistir auditoria."""
    if not isinstance(detalhes, dict):
        return None
    limpo: dict[str, Any] = {}
    for chave, valor in detalhes.items():
        chave_norm = str(chave).strip().lower()
        if chave_norm not in _CHAVES_PERMITIDAS_AUDITORIA and (
            chave_norm in _CHAVES_SENSIVEIS_AUDITORIA
            or any(termo in chave_norm for termo in _TERMOS_CHAVE_SEGREDO)
        ):
            continue
        limpo[chave] = _sanitizar_valor(valor)
    return limpo


def _garantir_administrador(usuario: Usuario) -> None:
    if usuario.papel != PapelUsuario.ADMINISTRADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: recurso exclusivo de administração técnica.",
        )


class AdminAuditService:
    """Registra e consulta auditorias técnicas e contadores operacionais da plataforma."""

    @staticmethod
    def registrar_evento(
        db: Session,
        *,
        acao: str,
        entidade: str,
        entidade_id: Optional[uuid.UUID] = None,
        usuario_ator: Optional[Usuario] = None,
        detalhes: Optional[dict[str, Any]] = None,
    ) -> AuditoriaOperacaoTecnica:
        registro = AuditoriaOperacaoTecnica(
            usuario_ator_id=usuario_ator.id if usuario_ator else None,
            papel_ator=usuario_ator.papel.value if usuario_ator else "sistema_cli",
            acao=acao.strip().upper()[:80],
            entidade=entidade.strip().lower()[:60],
            entidade_id=entidade_id,
            detalhes=_sanitizar_detalhes(detalhes),
        )
        return AdminAuditRepository.registrar(db, registro)

    @staticmethod
    def listar_auditoria_tecnica(
        db: Session,
        *,
        usuario: Usuario,
        acao: Optional[str] = None,
        entidade: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditoriaOperacaoTecnicaResponse]:
        _garantir_administrador(usuario)
        itens = AdminAuditRepository.listar(
            db,
            acao=acao,
            entidade=entidade,
            skip=skip,
            limit=limit,
        )
        return [AuditoriaOperacaoTecnicaResponse.model_validate(item) for item in itens]

    @staticmethod
    def obter_resumo_operacional(
        db: Session,
        *,
        usuario: Usuario,
    ) -> ResumoOperacionalAdminResponse:
        from app.integrations.assistant.interfaces import ProvedorLLMNaoConfigurado

        _garantir_administrador(usuario)

        total_usuarios = int(db.execute(select(func.count(Usuario.id))).scalar() or 0)
        usuarios_ativos = int(
            db.execute(select(func.count(Usuario.id)).where(Usuario.ativo.is_(True))).scalar()
            or 0
        )
        linhas_papeis = db.execute(
            select(Usuario.papel, func.count(Usuario.id)).group_by(Usuario.papel)
        ).all()
        contagem_papeis: dict[str, int] = {
            p.value: 0 for p in (PapelUsuario.ADMINISTRADOR, PapelUsuario.GESTOR, PapelUsuario.PROFESSOR)
        }
        for papel, qtd in linhas_papeis:
            chave = papel.value if isinstance(papel, PapelUsuario) else str(papel)
            contagem_papeis[chave] = int(qtd or 0)

        total_escolas = int(db.execute(select(func.count(Escola.id))).scalar() or 0)
        escolas_ativas = int(
            db.execute(select(func.count(Escola.id)).where(Escola.ativo.is_(True))).scalar()
            or 0
        )
        total_turmas = int(db.execute(select(func.count(Turma.id))).scalar() or 0)
        turmas_ativas = int(
            db.execute(select(func.count(Turma.id)).where(Turma.ativo.is_(True))).scalar()
            or 0
        )
        total_disciplinas = int(db.execute(select(func.count(Disciplina.id))).scalar() or 0)
        disciplinas_ativas = int(
            db.execute(
                select(func.count(Disciplina.id)).where(Disciplina.ativo.is_(True))
            ).scalar()
            or 0
        )
        total_creds = int(
            db.execute(select(func.count(CredencialIntegracaoPredicao.id))).scalar() or 0
        )
        creds_ativas = int(
            db.execute(
                select(func.count(CredencialIntegracaoPredicao.id)).where(
                    CredencialIntegracaoPredicao.ativo.is_(True)
                )
            ).scalar()
            or 0
        )
        total_aud_tec = int(
            db.execute(select(func.count(AuditoriaOperacaoTecnica.id))).scalar() or 0
        )
        total_aud_ia = int(
            db.execute(select(func.count(AuditoriaConsultaIA.id))).scalar() or 0
        )

        return ResumoOperacionalAdminResponse(
            total_usuarios=total_usuarios,
            usuarios_ativos=usuarios_ativos,
            usuarios_por_papel=contagem_papeis,
            total_escolas=total_escolas,
            escolas_ativas=escolas_ativas,
            total_turmas=total_turmas,
            turmas_ativas=turmas_ativas,
            total_disciplinas=total_disciplinas,
            disciplinas_ativas=disciplinas_ativas,
            total_credenciais_ml=total_creds,
            credenciais_ml_ativas=creds_ativas,
            total_eventos_auditoria_tecnica=total_aud_tec,
            total_eventos_auditoria_ia=total_aud_ia,
            provedor_llm_configurado=ProvedorLLMNaoConfigurado().esta_configurado(),
            ambiente=settings.ENVIRONMENT,
            versao_aplicacao=settings.VERSION,
            debug_ativo=bool(settings.DEBUG),
            algoritmo_jwt=settings.ALGORITHM,
            expiracao_token_minutos=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
