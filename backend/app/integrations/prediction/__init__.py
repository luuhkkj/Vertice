"""
Pacote de integração preditiva do Vértice (Fase 7).
"""

from typing import TYPE_CHECKING, Any

from app.integrations.prediction.leakage import (
    CAMPOS_PROIBIDOS_PREDICAO,
    CATALOGO_METADADOS_TECNICOS_PERMITIDOS,
    CATALOGO_VARIAVEIS_PREDITIVAS,
    validar_metadados_tecnicos,
    validar_variaveis_contra_leakage,
)
from app.integrations.prediction.models import (
    CredencialIntegracaoPredicao,
    FaixaRisco,
    PrevisaoRisco,
    TipoPrevisao,
)

if TYPE_CHECKING:
    from app.integrations.prediction.router import router
    from app.integrations.prediction.service import PredictionService


def __getattr__(name: str) -> Any:
    """Carrega router e PredictionService sob demanda evitando ciclo de importação."""
    if name == "router":
        from app.integrations.prediction.router import router

        return router
    if name == "PredictionService":
        from app.integrations.prediction.service import PredictionService

        return PredictionService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CAMPOS_PROIBIDOS_PREDICAO",
    "CATALOGO_METADADOS_TECNICOS_PERMITIDOS",
    "CATALOGO_VARIAVEIS_PREDITIVAS",
    "CredencialIntegracaoPredicao",
    "FaixaRisco",
    "PredictionService",
    "PrevisaoRisco",
    "TipoPrevisao",
    "router",
    "validar_metadados_tecnicos",
    "validar_variaveis_contra_leakage",
]
