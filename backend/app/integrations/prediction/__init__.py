"""
Pacote de integração preditiva do Vértice (Fase 7).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
    from app.integrations.prediction.router import router
    from app.integrations.prediction.service import PredictionService
    from app.integrations.prediction.modelo_risco import prever_risco
    from app.integrations.prediction.pipeline import ExecutorPipelineML, PipelineMLConfig


def __getattr__(name: str) -> Any:
    """Carrega exports sob demanda, sem exigir configuração da API em scripts locais."""
    exports_leakage = {
        "CAMPOS_PROIBIDOS_PREDICAO",
        "CATALOGO_METADADOS_TECNICOS_PERMITIDOS",
        "CATALOGO_VARIAVEIS_PREDITIVAS",
        "validar_metadados_tecnicos",
        "validar_variaveis_contra_leakage",
    }
    if name in exports_leakage:
        from app.integrations.prediction import leakage

        return getattr(leakage, name)
    exports_models = {
        "CredencialIntegracaoPredicao",
        "FaixaRisco",
        "PrevisaoRisco",
        "TipoPrevisao",
    }
    if name in exports_models:
        from app.integrations.prediction import models

        return getattr(models, name)
    if name == "router":
        from app.integrations.prediction.router import router

        return router
    if name == "PredictionService":
        from app.integrations.prediction.service import PredictionService

        return PredictionService
    if name == "prever_risco":
        from app.integrations.prediction.modelo_risco import prever_risco

        return prever_risco
    if name in {"ExecutorPipelineML", "PipelineMLConfig"}:
        from app.integrations.prediction import pipeline

        return getattr(pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CAMPOS_PROIBIDOS_PREDICAO",
    "CATALOGO_METADADOS_TECNICOS_PERMITIDOS",
    "CATALOGO_VARIAVEIS_PREDITIVAS",
    "CredencialIntegracaoPredicao",
    "ExecutorPipelineML",
    "FaixaRisco",
    "PipelineMLConfig",
    "PredictionService",
    "PrevisaoRisco",
    "TipoPrevisao",
    "prever_risco",
    "router",
    "validar_metadados_tecnicos",
    "validar_variaveis_contra_leakage",
]
