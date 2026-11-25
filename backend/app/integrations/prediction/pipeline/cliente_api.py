"""
Cliente HTTP dedicado para envio de previsões em lote ao backend Vértice.

Utiliza `POST /api/v1/previsoes/lote` autenticado exclusivamente via `X-Service-Token`,
respeitando o limite máximo de 2000 itens por lote, transação atômica por lote,
timeout configurável e sem retentativas indiscriminadas que gerem conflito `409`.

Desacoplado do ORM (`app.database`) e das configurações internas do servidor (`SECRET_KEY` /
`DATABASE_URL`), validando localmente o mesmo contrato de `PrevisaoRecebimentoLoteRequest`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
from typing import Any, Literal, Optional
import uuid

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.integrations.prediction.pipeline.config import (
    ErroConfiguracaoPipeline,
    PipelineMLConfig,
    mascarar_segredo,
    sanitizar_texto_segredos,
)

logger = logging.getLogger(__name__)

LIMITE_ITENS_LOTE_API = 2000

TipoPrevisaoEnvioLiteral = Literal["EVASAO", "REPROVACAO", "RISCO_ACADEMICO"]
FaixaRiscoEnvioLiteral = Literal["BAIXO", "MODERADO", "ALTO", "CRITICO"]


class PrevisaoItemEnvio(BaseModel):
    """Espelho leve e desacoplado de `PrevisaoRecebimentoItem` da API."""

    estudante_id: Optional[uuid.UUID] = None
    codigo_anonimo: Optional[str] = Field(default=None, min_length=1, max_length=50)
    escola_id: Optional[uuid.UUID] = None
    turma_id: Optional[uuid.UUID] = None
    ano_letivo: int = Field(..., ge=2000, le=2100)
    periodo_letivo: str = Field(..., min_length=1, max_length=30)
    tipo_previsao: TipoPrevisaoEnvioLiteral = "RISCO_ACADEMICO"
    pontuacao_risco: float = Field(..., ge=0.0, le=1.0)
    faixa_risco: FaixaRiscoEnvioLiteral
    politica_classificacao_versao: Optional[str] = Field(default=None, max_length=60)
    modelo_nome: str = Field(..., min_length=2, max_length=100)
    modelo_versao: str = Field(..., min_length=1, max_length=50)
    gerado_em: datetime
    lote_externo_id: Optional[str] = Field(default=None, max_length=120)
    variaveis_utilizadas: Optional[list[str] | dict[str, Any]] = None
    metadados_tecnicos: Optional[dict[str, Any]] = None

    @field_validator("pontuacao_risco")
    @classmethod
    def _validar_pontuacao(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("`pontuacao_risco` deve ser finito entre 0.0 e 1.0.")
        if v < 0.0 or v > 1.0:
            raise ValueError("`pontuacao_risco` deve estar no intervalo [0.0, 1.0].")
        return round(float(v), 6)

    @field_validator("periodo_letivo", "modelo_nome", "modelo_versao")
    @classmethod
    def _strip_obrigatorio(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Campo textual obrigatório não pode ser vazio.")
        return s

    @field_validator("codigo_anonimo", "politica_classificacao_versao", "lote_externo_id")
    @classmethod
    def _strip_opcional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("gerado_em")
    @classmethod
    def _normalizar_gerado_em(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validar_identificacao_estudante(self) -> "PrevisaoItemEnvio":
        if self.estudante_id is None and self.codigo_anonimo is None:
            raise ValueError(
                "Informe `estudante_id` ou (`codigo_anonimo` e `escola_id`)."
            )
        if self.estudante_id is None and self.escola_id is None:
            raise ValueError(
                "Quando `estudante_id` não for informado, `escola_id` é obrigatório."
            )
        return self


class PrevisaoLoteEnvio(BaseModel):
    """Espelho leve de `PrevisaoRecebimentoLoteRequest` (máx. 2000 itens)."""

    lote_externo_id: Optional[str] = Field(default=None, max_length=120)
    itens: list[PrevisaoItemEnvio] = Field(..., min_length=1, max_length=2000)

    @field_validator("lote_externo_id")
    @classmethod
    def _strip_lote(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip() or None


class ErroEnvioPipeline(RuntimeError):
    """Erro base no envio de previsões ao backend."""

    def __init__(self, mensagem: str, *, lotes_enviados_antes_falha: int = 0) -> None:
        super().__init__(sanitizar_texto_segredos(mensagem))
        self.lotes_enviados_antes_falha = lotes_enviados_antes_falha


class ErroEnvioAutenticacao(ErroEnvioPipeline):
    """Token `X-Service-Token` ausente ou inválido (HTTP 401)."""


class ErroEnvioAutorizacao(ErroEnvioPipeline):
    """Credencial revogada, expirada ou sem permissão para escola/modelo (HTTP 403)."""


class ErroEnvioConflitoIdempotencia(ErroEnvioPipeline):
    """Duplicidade ou conflito de idempotência detectado pelo backend (HTTP 409)."""


class ErroEnvioValidacao(ErroEnvioPipeline):
    """Rejeição de validação/anti-leakage/referência pelo backend (HTTP 404/422)."""


class ErroEnvioComunicacao(ErroEnvioPipeline):
    """Timeout, falha de conexão ou erro HTTP 5xx ao enviar previsões."""


@dataclass(frozen=True)
class ResultadoSubLoteEnvio:
    """Resultado persistido de um sublote enviado à API."""

    indice_lote: int
    lote_externo_id: Optional[str]
    quantidade_enviada: int
    quantidade_recebida: int


@dataclass(frozen=True)
class ResultadoEnvioAPI:
    """Consolidação final de todos os sublotes enviados em uma execução."""

    sucesso: bool
    total_enviado: int
    total_recebido: int
    total_lotes: int
    sublotes: list[ResultadoSubLoteEnvio]


def _extrair_detalhe_erro_http(resposta: httpx.Response) -> str:
    try:
        corpo = resposta.json()
        if isinstance(corpo, dict) and "detail" in corpo:
            return sanitizar_texto_segredos(str(corpo["detail"]))
    except Exception:
        pass
    return sanitizar_texto_segredos((resposta.text or "").strip()[:300])


def _normalizar_item_envio(item: Any) -> PrevisaoItemEnvio:
    if isinstance(item, PrevisaoItemEnvio):
        return item
    if isinstance(item, BaseModel):
        return PrevisaoItemEnvio.model_validate(item.model_dump(mode="python"))
    return PrevisaoItemEnvio.model_validate(item)


class ClienteAPIPrevisoes:
    """Cliente de envio em lote para `POST /api/v1/previsoes/lote`."""

    def __init__(
        self,
        config: PipelineMLConfig,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.config = config
        self._http_client = http_client

    def enviar_previsoes(
        self,
        itens: Sequence[Any],
        *,
        lote_externo_id: Optional[str] = None,
    ) -> ResultadoEnvioAPI:
        """
        Envia previsões já formatadas para `POST /api/v1/previsoes/lote`,
        fracionando em sublotes dentro do limite da API e interrompendo
        imediatamente caso qualquer sublote falhe.
        """
        try:
            self.config.validar_para_envio()
        except ErroConfiguracaoPipeline as exc:
            raise ErroEnvioAutenticacao(str(exc)) from exc

        if not itens:
            return ResultadoEnvioAPI(
                sucesso=True,
                total_enviado=0,
                total_recebido=0,
                total_lotes=0,
                sublotes=[],
            )

        try:
            itens_validados = [_normalizar_item_envio(it) for it in itens]
        except ValidationError as exc:
            raise ErroEnvioValidacao(
                f"Item inválido para o contrato da API: {exc}"
            ) from exc

        if self._http_client is not None:
            return self._enviar_com_cliente(
                self._http_client,
                itens_validados,
                lote_externo_id=lote_externo_id,
            )

        with httpx.Client(timeout=self.config.http_timeout_seconds) as client:
            return self._enviar_com_cliente(
                client,
                itens_validados,
                lote_externo_id=lote_externo_id,
            )

    def _enviar_com_cliente(
        self,
        client: httpx.Client,
        itens: list[PrevisaoItemEnvio],
        *,
        lote_externo_id: Optional[str],
    ) -> ResultadoEnvioAPI:
        assert self.config.service_token is not None
        endpoint = f"{self.config.api_v1_url}/previsoes/lote"
        tamanho_lote = min(self.config.batch_size, LIMITE_ITENS_LOTE_API)
        total_chunks = (len(itens) + tamanho_lote - 1) // tamanho_lote

        headers = {
            "X-Service-Token": self.config.service_token,
            "Content-Type": "application/json",
        }

        sublotes_concluidos: list[ResultadoSubLoteEnvio] = []
        total_recebido = 0

        for idx_lote in range(total_chunks):
            inicio = idx_lote * tamanho_lote
            chunk = itens[inicio : inicio + tamanho_lote]
            lote_id_atual = (
                f"{lote_externo_id}-lote-{idx_lote + 1:03d}"
                if lote_externo_id and total_chunks > 1
                else lote_externo_id
            )
            itens_lote = [
                item.model_copy(update={"lote_externo_id": lote_id_atual})
                if lote_id_atual and not item.lote_externo_id
                else item
                for item in chunk
            ]
            try:
                payload_model = PrevisaoLoteEnvio(
                    lote_externo_id=lote_id_atual,
                    itens=itens_lote,
                )
            except ValidationError as exc:
                raise ErroEnvioValidacao(
                    f"Payload do lote {idx_lote + 1}/{total_chunks} inválido no cliente: {exc}",
                    lotes_enviados_antes_falha=len(sublotes_concluidos),
                ) from exc

            corpo_json: dict[str, Any] = payload_model.model_dump(mode="json")

            req_kwargs: dict[str, Any] = {}
            if type(client).__name__ != "TestClient":
                req_kwargs["timeout"] = self.config.http_timeout_seconds
            try:
                resposta = client.post(
                    endpoint,
                    json=corpo_json,
                    headers=headers,
                    **req_kwargs,
                )
            except httpx.TimeoutException as exc:
                raise ErroEnvioComunicacao(
                    f"Timeout ao enviar sublote {idx_lote + 1}/{total_chunks} após "
                    f"{self.config.http_timeout_seconds}s. Não é seguro reenviar automaticamente sem "
                    "verificar idempotência.",
                    lotes_enviados_antes_falha=len(sublotes_concluidos),
                ) from exc
            except httpx.RequestError as exc:
                raise ErroEnvioComunicacao(
                    f"Falha de rede ao enviar sublote {idx_lote + 1}/{total_chunks}: "
                    f"{sanitizar_texto_segredos(str(exc))}",
                    lotes_enviados_antes_falha=len(sublotes_concluidos),
                ) from exc

            detalhe = _extrair_detalhe_erro_http(resposta)
            if resposta.status_code == 401:
                raise ErroEnvioAutenticacao(
                    f"Token técnico rejeitado pela API (HTTP 401, credencial {mascarar_segredo(self.config.service_token)}): {detalhe}",
                    lotes_enviados_antes_falha=len(sublotes_concluidos),
                )
            if resposta.status_code == 403:
                raise ErroEnvioAutorizacao(
                    f"Credencial sem autorização para este envio (HTTP 403, credencial {mascarar_segredo(self.config.service_token)}): {detalhe}",
                    lotes_enviados_antes_falha=len(sublotes_concluidos),
                )
            if resposta.status_code == 409:
                raise ErroEnvioConflitoIdempotencia(
                    f"Conflito de idempotência no sublote {idx_lote + 1}/{total_chunks} (HTTP 409): {detalhe}",
                    lotes_enviados_antes_falha=len(sublotes_concluidos),
                )
            if resposta.status_code in (400, 404, 422):
                raise ErroEnvioValidacao(
                    f"Lote rejeitado pela validação da API (HTTP {resposta.status_code}): {detalhe}",
                    lotes_enviados_antes_falha=len(sublotes_concluidos),
                )
            if resposta.status_code >= 500 or resposta.status_code not in (200, 201):
                raise ErroEnvioComunicacao(
                    f"Erro HTTP inesperado ({resposta.status_code}) no sublote {idx_lote + 1}/{total_chunks}: {detalhe}",
                    lotes_enviados_antes_falha=len(sublotes_concluidos),
                )

            try:
                dados_resp = resposta.json()
                qtd_rec = int(dados_resp.get("quantidade_recebida", len(itens_lote)))
            except Exception as exc:
                raise ErroEnvioComunicacao(
                    f"Resposta HTTP {resposta.status_code} sem JSON válido de confirmação do lote.",
                    lotes_enviados_antes_falha=len(sublotes_concluidos),
                ) from exc

            total_recebido += qtd_rec
            sublotes_concluidos.append(
                ResultadoSubLoteEnvio(
                    indice_lote=idx_lote + 1,
                    lote_externo_id=lote_id_atual,
                    quantidade_enviada=len(itens_lote),
                    quantidade_recebida=qtd_rec,
                )
            )

        logger.info(
            "Envio ML concluído | credencial=%s | lotes=%d | enviados=%d | persistidos=%d",
            mascarar_segredo(self.config.service_token),
            len(sublotes_concluidos),
            len(itens),
            total_recebido,
        )
        return ResultadoEnvioAPI(
            sucesso=True,
            total_enviado=len(itens),
            total_recebido=total_recebido,
            total_lotes=len(sublotes_concluidos),
            sublotes=sublotes_concluidos,
        )
