"""
Schemas Pydantic v2 para o módulo de Importação de Datasets Escolares (Fase 3).
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.importacao.models import StatusLoteImportacao, TipoImportacao


class ItemProblemaValidacao(BaseModel):
    """Detalhamento de um erro ou aviso identificado na validação de uma linha ou cabeçalho."""

    linha: Optional[int] = Field(
        default=None,
        description="Número da linha no arquivo original (base 1, considerando cabeçalho na linha 1).",
    )
    categoria: str = Field(
        description="Categoria do problema (ex: coluna_ausente, pii_proibido, autorizacao, valor_invalido, duplicidade, anonimizacao)."
    )
    campo: Optional[str] = Field(
        default=None,
        description="Coluna/campo relacionado ao problema, quando aplicável.",
    )
    mensagem: str = Field(
        description="Explicação clara do problema sem expor dados pessoais proibidos."
    )


class RelatorioValidacaoSchema(BaseModel):
    """Estrutura completa do relatório de validação e qualidade de dados de um lote."""

    total_linhas: int = 0
    registros_validos: int = 0
    quantidade_erros: int = 0
    quantidade_avisos: int = 0
    registros_novos: int = 0
    registros_existentes: int = 0
    turmas_identificadas: list[str] = []
    disciplinas_identificadas: list[str] = []
    colunas_ausentes: list[str] = []
    colunas_proibidas_pii: list[str] = []
    problemas_autorizacao: list[ItemProblemaValidacao] = []
    valores_invalidos: list[ItemProblemaValidacao] = []
    duplicidades: list[ItemProblemaValidacao] = []
    problemas_anonimizacao: list[ItemProblemaValidacao] = []
    erros: list[ItemProblemaValidacao] = []
    avisos: list[ItemProblemaValidacao] = []


class RegistroPreviaItemSchema(BaseModel):
    """Representa um registro validado pronto para pré-visualização antes da confirmação."""

    linha: int
    codigo_anonimo: str
    turma_id: uuid.UUID
    turma_nome: str
    disciplina_id: Optional[uuid.UUID] = None
    disciplina_codigo: Optional[str] = None
    disciplina_nome: Optional[str] = None
    ano_letivo: int
    periodo_letivo: str
    frequencia_percentual: Optional[float] = None
    faltas: Optional[int] = None
    media_geral: Optional[float] = None
    nota_disciplina: Optional[float] = None
    nota_prova: Optional[float] = None
    nota_trabalho: Optional[float] = None
    historico_reprovacoes: Optional[int] = None
    participacao_recuperacao: Optional[bool] = None
    situacao_final: Optional[str] = None
    operacao_prevista: str = Field(
        description="'insercao' se o registro ainda não existir no período/disciplina, ou 'atualizacao' se já existir."
    )


class LoteImportacaoResumoResponse(BaseModel):
    """Resumo e status de auditoria de um lote de importação."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    escola_id: uuid.UUID
    nome_arquivo: str
    tipo_importacao: TipoImportacao
    hash_arquivo: str
    status: StatusLoteImportacao
    total_linhas: int
    registros_validos: int
    quantidade_erros: int
    quantidade_avisos: int
    registros_novos: int
    registros_existentes: int
    registros_inseridos: int
    registros_atualizados: int
    enviado_em: datetime
    validado_em: Optional[datetime] = None
    confirmado_em: Optional[datetime] = None
    atualizado_em: datetime


class LoteImportacaoPreviaResponse(LoteImportacaoResumoResponse):
    """Resposta detalhada da Etapa 1 (validação e prévia) de um lote de importação."""

    pode_confirmar: bool
    relatorio_validacao: RelatorioValidacaoSchema
    previa_registros: list[dict[str, Any]] = []


class ConfirmacaoImportacaoResponse(BaseModel):
    """Resposta da Etapa 2 (confirmação e persistência atômica)."""

    lote_id: uuid.UUID
    status: StatusLoteImportacao
    usuario_id: uuid.UUID
    escola_id: uuid.UUID
    registros_inseridos: int
    registros_atualizados: int
    confirmado_em: datetime
    mensagem: str

