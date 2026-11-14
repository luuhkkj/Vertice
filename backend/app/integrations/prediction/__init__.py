"""
Pacote de integração preditiva do Vértice (Fase 7).
"""

from app.integrations.prediction.leakage import (
    CAMPOS_PROIBIDOS_PREDICAO,
    CATALOGO_VARIAVEIS_PREDITIVAS,
    validar_variaveis_contra_leakage,
)
from app.integrations.prediction.models import (
    CredencialIntegracaoPredicao,
    FaixaRisco,
    PrevisaoRisco,
    TipoPrevisao,
)
from app.integrations.prediction.router import router
from app.integrations.prediction.service import PredictionService

__all__ = [
    "CAMPOS_PROIBIDOS_PREDICAO",
    "CATALOGO_VARIAVEIS_PREDITIVAS",
    "CredencialIntegracaoPredicao",
    "FaixaRisco",
    "PredictionService",
    "PrevisaoRisco",
    "TipoPrevisao",
    "router",
    "validar_variaveis_contra_leakage",
]
