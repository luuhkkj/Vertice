"""Contrato desacoplado para provedores do Assistente IA."""

from abc import ABC, abstractmethod

from fastapi import HTTPException, status

from app.integrations.assistant.schemas import (
    RequisicaoAssistenteLLM,
    RespostaAssistenteLLM,
)


class ProvedorLLMBase(ABC):
    """Interface padrão para provedores LLM."""

    nome_provedor: str

    @abstractmethod
    def esta_configurado(self) -> bool:
        """Indica se o provedor está configurado."""

    @abstractmethod
    def gerar_resposta(
        self,
        requisicao: RequisicaoAssistenteLLM,
    ) -> RespostaAssistenteLLM:
        """Gera uma resposta a partir do contexto estruturado autorizado."""


class ProvedorLLMNaoConfigurado(ProvedorLLMBase):
    """Estado explícito quando nenhum provedor local foi configurado."""

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
                "O provedor de IA local não está configurado. Configure o Ollama e "
                "um modelo gratuito para responder às perguntas."
            ),
        )
