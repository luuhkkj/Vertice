"""
Rotas HTTP exclusivas de Administração Técnica (`/api/v1/admin`).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.database.connection import get_db
from app.modules.admin.schemas import (
    AuditoriaOperacaoTecnicaResponse,
    ResumoOperacionalAdminResponse,
)
from app.modules.admin.service import AdminAuditService
from app.modules.usuarios.models import Usuario

router = APIRouter()


@router.get(
    "/resumo-operacional",
    response_model=ResumoOperacionalAdminResponse,
    summary="Consultar resumo operacional e inventário técnico da plataforma (Apenas Administrador)",
)
def obter_resumo_operacional(
    db: Session = Depends(get_db),
    current_admin: Usuario = Depends(require_admin),
) -> ResumoOperacionalAdminResponse:
    """Retorna apenas contadores técnicos e estruturais, sem dados pedagógicos ou PII."""
    return AdminAuditService.obter_resumo_operacional(db, usuario=current_admin)


@router.get(
    "/auditoria-tecnica",
    response_model=list[AuditoriaOperacaoTecnicaResponse],
    summary="Listar trilha de auditoria de operações técnicas sensíveis (Apenas Administrador)",
)
def listar_auditoria_tecnica(
    acao: Optional[str] = Query(default=None, max_length=80),
    entidade: Optional[str] = Query(default=None, max_length=60),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_admin: Usuario = Depends(require_admin),
) -> list[AuditoriaOperacaoTecnicaResponse]:
    """Lista operações administrativas auditadas (contas, estrutura e credenciais ML)."""
    return AdminAuditService.listar_auditoria_tecnica(
        db,
        usuario=current_admin,
        acao=acao,
        entidade=entidade,
        skip=skip,
        limit=limit,
    )
