"""
Extrator controlado de dados e metadados de execução para o pipeline ML do Vértice.

Consome exclusivamente `GET /api/v1/previsoes/exportacao-inferencia` usando a mesma
credencial técnica `X-Service-Token`, obtendo automaticamente da resposta a escola e
o modelo autorizados para a credencial sem configurações duplicadas no `.env`.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Optional
import uuid

import httpx

from app.integrations.prediction.pipeline.config import (
    ErroConfiguracaoPipeline,
    PipelineMLConfig,
    mascarar_segredo,
    sanitizar_texto_segredos,
)

logger = logging.getLogger(__name__)


class ErroExtracaoPipeline(RuntimeError):
    """Erro base da etapa de extração controlada de dados."""


class ErroExtracaoConfiguracao(ErroExtracaoPipeline):
    """Configuração de extração incompleta ou incompatível."""


class ErroExtracaoAutenticacao(ErroExtracaoPipeline):
    """Token `X-Service-Token` ausente ou inválido (HTTP 401)."""


class ErroExtracaoAutorizacao(ErroExtracaoPipeline):
    """Credencial revogada, expirada ou sem permissão de leitura/escola (HTTP 403)."""


class ErroExtracaoValidacao(ErroExtracaoPipeline):
    """Parâmetros inválidos de consulta ou violação de corte temporal (HTTP 404/422)."""


class ErroExtracaoComunicacao(ErroExtracaoPipeline):
    """Erro de rede, timeout, resposta não-JSON ou falha HTTP 5xx na extração."""


@dataclass(frozen=True)
class ResultadoExtracao:
    """Resultado consolidado da extração e dos metadados da credencial autenticada."""

    registros: list[dict[str, Any]]
    total_reportado: int
    paginas_consultadas: int
    escola_id: uuid.UUID
    credencial_nome: str
    modelo_nome: str
    modelo_versao: Optional[str]
    artefato_relativo: Optional[str]
    tipo_previsao: str
    periodo_letivo: str


def _extrair_detalhe_http(resposta: httpx.Response) -> str:
    try:
        corpo = resposta.json()
        if isinstance(corpo, dict) and "detail" in corpo:
            return sanitizar_texto_segredos(str(corpo["detail"]))
    except Exception:
        pass
    return sanitizar_texto_segredos((resposta.text or "").strip()[:300])


class ExtratorDadosInferencia:
    """Cliente de extração paginada de atributos e metadados para inferência ML."""

    def __init__(
        self,
        config: PipelineMLConfig,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.config = config
        self._http_client = http_client

    def extrair(self) -> ResultadoExtracao:
        """
        Extrai todos os registros elegíveis no corte configurado percorrendo todas
        as páginas da rota `GET /api/v1/previsoes/exportacao-inferencia`.
        """
        return self._executar(apenas_metadados=False)

    def consultar_configuracao_credencial(self) -> ResultadoExtracao:
        """Consulta uma página mínima (`limit=1`) para descobrir escola e modelo do token."""
        return self._executar(apenas_metadados=True)

    def _executar(self, *, apenas_metadados: bool) -> ResultadoExtracao:
        try:
            self.config.validar_para_extracao_remota()
        except ErroConfiguracaoPipeline as exc:
            raise ErroExtracaoConfiguracao(str(exc)) from exc

        if self._http_client is not None:
            return self._executar_extracao(
                self._http_client,
                apenas_metadados=apenas_metadados,
            )

        with httpx.Client(timeout=self.config.http_timeout_seconds) as client:
            return self._executar_extracao(
                client,
                apenas_metadados=apenas_metadados,
            )

    def _executar_extracao(
        self,
        client: httpx.Client,
        *,
        apenas_metadados: bool,
    ) -> ResultadoExtracao:
        assert self.config.service_token is not None
        headers = {"X-Service-Token": self.config.service_token}
        endpoint = f"{self.config.api_v1_url}/previsoes/exportacao-inferencia"

        registros: list[dict[str, Any]] = []
        skip = 0
        paginas = 0
        total_reportado = 0
        escola_resolvida: Optional[uuid.UUID] = None
        credencial_nome = ""
        modelo_nome = ""
        modelo_versao: Optional[str] = None
        artefato_relativo: Optional[str] = None
        tipo_previsao = "RISCO_ACADEMICO"

        limite_pagina = 1 if apenas_metadados else self.config.page_size

        while True:
            params: dict[str, Any] = {
                "periodo_letivo": self.config.periodo_letivo,
                "skip": skip,
                "limit": limite_pagina,
            }
            if self.config.turma_id is not None:
                params["turma_id"] = str(self.config.turma_id)
            if self.config.disciplina_id is not None:
                params["disciplina_id"] = str(self.config.disciplina_id)
            if self.config.ano_letivo is not None:
                params["ano_letivo"] = self.config.ano_letivo

            req_kwargs: dict[str, Any] = {}
            if type(client).__name__ != "TestClient":
                req_kwargs["timeout"] = self.config.http_timeout_seconds

            try:
                resposta = client.get(
                    endpoint,
                    params=params,
                    headers=headers,
                    **req_kwargs,
                )
            except httpx.TimeoutException as exc:
                raise ErroExtracaoComunicacao(
                    f"Timeout na extração de dados de inferência após {self.config.http_timeout_seconds}s."
                ) from exc
            except httpx.RequestError as exc:
                raise ErroExtracaoComunicacao(
                    f"Erro de comunicação durante extração: {sanitizar_texto_segredos(str(exc))}"
                ) from exc

            if resposta.status_code == 401:
                raise ErroExtracaoAutenticacao(
                    f"Credencial técnica inválida na extração (HTTP 401, {mascarar_segredo(self.config.service_token)}): "
                    f"{_extrair_detalhe_http(resposta)}"
                )
            if resposta.status_code == 403:
                raise ErroExtracaoAutorizacao(
                    f"Credencial sem permissão para extração (HTTP 403, {mascarar_segredo(self.config.service_token)}): "
                    f"{_extrair_detalhe_http(resposta)}"
                )
            if resposta.status_code in (400, 404, 422):
                raise ErroExtracaoValidacao(
                    f"Erro na consulta de extração (HTTP {resposta.status_code}): {_extrair_detalhe_http(resposta)}"
                )
            if resposta.status_code >= 500:
                raise ErroExtracaoComunicacao(
                    f"Erro interno do backend na extração (HTTP {resposta.status_code}): {_extrair_detalhe_http(resposta)}"
                )

            try:
                payload = resposta.json()
            except ValueError as exc:
                raise ErroExtracaoComunicacao(
                    "Resposta inválida da API de extração: JSON malformado."
                ) from exc

            if (
                not isinstance(payload, dict)
                or not isinstance(payload.get("itens"), list)
                or not payload.get("escola_id")
                or not payload.get("modelo_nome")
            ):
                raise ErroExtracaoComunicacao(
                    "Resposta inesperada da API de extração: metadados `escola_id`, `modelo_nome` ou `itens` ausentes."
                )

            paginas += 1
            total_reportado = int(payload.get("total", len(payload["itens"])))
            escola_resolvida = uuid.UUID(str(payload["escola_id"]))
            credencial_nome = str(payload.get("credencial_nome") or "").strip()
            modelo_nome = str(payload["modelo_nome"]).strip()
            modelo_versao = (
                str(payload["modelo_versao"]).strip()
                if payload.get("modelo_versao")
                else None
            )
            artefato_relativo = (
                str(payload["artefato_relativo"]).strip()
                if payload.get("artefato_relativo")
                else None
            )
            tipo_previsao = str(payload.get("tipo_previsao") or "RISCO_ACADEMICO").strip()

            if apenas_metadados:
                break

            itens_pagina = payload["itens"]
            if not itens_pagina:
                break

            registros.extend(itens_pagina)
            skip += len(itens_pagina)
            if skip >= total_reportado or len(itens_pagina) < limite_pagina:
                break

        assert escola_resolvida is not None
        logger.info(
            "Extração ML concluída | credencial=%s | escola_id=%s | modelo=%s | periodo=%s | paginas=%d | total=%d | extraidos=%d",
            mascarar_segredo(self.config.service_token),
            str(escola_resolvida),
            modelo_nome,
            self.config.periodo_letivo,
            paginas,
            total_reportado,
            len(registros),
        )
        return ResultadoExtracao(
            registros=registros,
            total_reportado=total_reportado,
            paginas_consultadas=paginas,
            escola_id=escola_resolvida,
            credencial_nome=credencial_nome,
            modelo_nome=modelo_nome,
            modelo_versao=modelo_versao,
            artefato_relativo=artefato_relativo,
            tipo_previsao=tipo_previsao,
            periodo_letivo=self.config.periodo_letivo,
        )
