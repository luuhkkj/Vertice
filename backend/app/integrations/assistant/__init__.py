"""
Pacote de preparação do Assistente Inteligente do Vértice (Fase 7).
"""

from typing import TYPE_CHECKING, Any

from app.integrations.assistant.interfaces import (
    ProvedorLLMBase,
    ProvedorLLMNaoConfigurado,
)
from app.integrations.assistant.models import (
    AuditoriaConsultaIA,
    ResultadoAutorizacaoIA,
    TipoContextoAssistente,
)

if TYPE_CHECKING:
    from app.integrations.assistant.router import router
    from app.integrations.assistant.service import AssistenteContextoService


def __getattr__(name: str) -> Any:
    """Carrega router e AssistenteContextoService sob demanda evitando ciclo de importação."""
    if name == "router":
        from app.integrations.assistant.router import router

        return router
    if name == "AssistenteContextoService":
        from app.integrations.assistant.service import AssistenteContextoService

        return AssistenteContextoService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AssistenteContextoService",
    "AuditoriaConsultaIA",
    "ProvedorLLMBase",
    "ProvedorLLMNaoConfigurado",
    "ResultadoAutorizacaoIA",
    "TipoContextoAssistente",
    "router",
]
