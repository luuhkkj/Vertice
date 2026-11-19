"""Schemas leves da inferência local, sem dependência do ORM ou da configuração da API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PrevisaoRiscoModeloResponse(BaseModel):
    """Resultado da função de inferência local para cada estudante anonimizado."""

    id_estudante: str
    pontuacao_risco: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    faixa_risco: Literal[
        "BAIXO",
        "MODERADO",
        "ALTO",
        "SEM_PREVISAO_VALIDA",
    ]
    status_acompanhamento: Literal[
        "Estável",
        "Atenção",
        "Prioritário",
        "Dados insuficientes",
    ]
    versao_modelo: str
    data_processamento: datetime
    aviso_metodologico: str = (
        "Prova de conceito treinada em rótulos derivados do UCI Student Performance. "
        "Não representa probabilidade validada para estudantes do Vértice e não deve "
        "ser usada para decisões pedagógicas automáticas."
    )
