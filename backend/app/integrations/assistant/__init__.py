"""
Pacote de preparação do Assistente Inteligente do Vértice (Fase 7).
"""

from app.integrations.assistant.interfaces import (
    ProvedorLLMBase,
    ProvedorLLMNaoConfigurado,
)
from app.integrations.assistant.models import (
    AuditoriaConsultaIA,
    ResultadoAutorizacaoIA,
    TipoContextoAssistente,
)
from app.integrations.assistant.router import router
from app.integrations.assistant.service import AssistenteContextoService

__all__ = [
    "AssistenteContextoService",
    "AuditoriaConsultaIA",
    "ProvedorLLMBase",
    "ProvedorLLMNaoConfigurado",
    "ResultadoAutorizacaoIA",
    "TipoContextoAssistente",
    "router",
]
