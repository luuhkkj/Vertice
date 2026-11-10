"""
Schemas Pydantic v2 para o módulo de Acompanhamento Pedagógico (Fase 4).
Nota: `usuario_id` e `escola_id` NUNCA são aceitos no payload de entrada — o responsável
é obtido exclusivamente a partir da sessão autenticada (JWT).
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.acompanhamento.models import OrigemAcompanhamento


class AcompanhamentoCreate(BaseModel):
    """
    Dados para registrar uma ação pedagógica individual (`estudante_id` / `codigo_anonimo`)
    ou coletiva (`turma_id`).
    """

    estudante_id: Optional[uuid.UUID] = None
    codigo_anonimo: Optional[str] = Field(default=None, max_length=50)
    turma_id: Optional[uuid.UUID] = None
    disciplina_id: Optional[uuid.UUID] = None
    origem: OrigemAcompanhamento
    tipo_acao: str = Field(..., min_length=2, max_length=100)
    descricao: str = Field(..., min_length=3, max_length=4000)

    @model_validator(mode="after")
    def _validar_alvo_obrigatorio(self) -> "AcompanhamentoCreate":
        tem_estudante = self.estudante_id is not None or bool(
            self.codigo_anonimo and self.codigo_anonimo.strip()
        )
        tem_turma = self.turma_id is not None
        if not tem_estudante and not tem_turma:
            raise ValueError(
                "É obrigatório informar um estudante ('estudante_id' ou 'codigo_anonimo') "
                "para ação individual ou 'turma_id' para ação coletiva."
            )
        return self


class AcompanhamentoUpdate(BaseModel):
    """
    Dados para atualizar um registro de acompanhamento pedagógico.
    A versão anterior é preservada automaticamente no histórico de auditoria (`historico_alteracoes`).
    """

    origem: Optional[OrigemAcompanhamento] = None
    tipo_acao: Optional[str] = Field(default=None, min_length=2, max_length=100)
    descricao: Optional[str] = Field(default=None, min_length=3, max_length=4000)
    ativo: Optional[bool] = None


class AcompanhamentoResponse(BaseModel):
    """Representação de saída de um registro de acompanhamento pedagógico."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    escola_id: uuid.UUID
    usuario_id: uuid.UUID
    usuario_nome: Optional[str] = None
    estudante_id: Optional[uuid.UUID] = None
    codigo_anonimo: Optional[str] = None
    turma_id: Optional[uuid.UUID] = None
    turma_nome: Optional[str] = None
    disciplina_id: Optional[uuid.UUID] = None
    disciplina_codigo: Optional[str] = None
    origem: OrigemAcompanhamento
    tipo_acao: str
    descricao: str
    historico_alteracoes: list[dict[str, Any]] = []
    ativo: bool
    data_registro: datetime
    atualizado_em: datetime

