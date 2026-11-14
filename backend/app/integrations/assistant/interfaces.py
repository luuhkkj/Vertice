"""
Abstração desacoplada (Provider-Agnostic) para futura conexão de provedores LLM.

Nesta Fase 7 não há chamadas externas a APIs de IA e nenhuma resposta é simulada.
"""

from abc import ABC, abstractmethod

from fastapi import HTTPException, status

from app.integrations.assistant.schemas import (
    RequisicaoAssistenteLLM,
    RespostaAssistenteLLM,
)


class ProvedorLLMBase(ABC):
    """Interface padrão que qualquer provedor LLM futuro deverá implementar."""

    nome_provedor: str

    @abstractmethod
    def esta_configurado(self) -> bool:
        """Indica se há um cliente/provedor LLM externo devidamente configurado."""

    @abstractmethod
    def gerar_resposta(
        self,
        requisicao: RequisicaoAssistenteLLM,
    ) -> RespostaAssistenteLLM:
        """Gera uma resposta assistida a partir do contexto estruturado autorizado."""


class ProvedorLLMNaoConfigurado(ProvedorLLMBase):
    """
    Implementação padrão segura da Fase 7:
    prepara o contrato e responde de forma transparente que o provedor LLM
    externo ainda não foi conectado, jamais simulando respostas de IA.
    """

    nome_provedor = "nao_configurado"

    def esta_configurado(self) -> bool:
        return False

    def gerar_resposta(
        self,
        requisicao: RequisicaoAssistenteLLM,
    ) -> RespostaAssistenteLLM:
        _ = requisicao
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Provedor de IA generativa ainda não conectado nesta fase (Fase 7). "
                "O contexto estruturado foi autorizado, auditado e preparado com segurança, "
                "aguardando conexão futura de um provedor LLM."
            ),
        )
