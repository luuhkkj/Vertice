"""
Schemas Pydantic para o módulo de Administração Técnica e Auditoria Operacional.
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict


class AuditoriaOperacaoTecnicaResponse(BaseModel):
    """Registro de auditoria de uma operação técnica ou administrativa."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_ator_id: Optional[uuid.UUID] = None
    papel_ator: str
    acao: str
    entidade: str
    entidade_id: Optional[uuid.UUID] = None
    detalhes: Optional[dict[str, Any]] = None
    criado_em: datetime


class ResumoOperacionalAdminResponse(BaseModel):
    """
    Contadores estritamente técnicos e estruturais da plataforma e estado operacional não sensível.
    Não contém informações pedagógicas de estudantes, notas, avaliações ou previsões nem segredos.
    """

    total_usuarios: int
    usuarios_ativos: int
    usuarios_por_papel: dict[str, int]
    total_escolas: int
    escolas_ativas: int
    total_turmas: int
    turmas_ativas: int
    total_disciplinas: int
    disciplinas_ativas: int
    total_credenciais_ml: int
    credenciais_ml_ativas: int
    total_eventos_auditoria_tecnica: int
    total_eventos_auditoria_ia: int
    provedor_llm_configurado: bool
    ambiente: str
    versao_aplicacao: str
    debug_ativo: bool
    algoritmo_jwt: str
    expiracao_token_minutos: int
