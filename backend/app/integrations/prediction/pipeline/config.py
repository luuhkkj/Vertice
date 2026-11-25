"""
Configuração minimalista e desacoplada do pipeline automatizado de ML do Vértice.

Requer apenas `VERTICE_ML_SERVICE_TOKEN` e `VERTICE_API_URL` (padrão `http://127.0.0.1:8000`).
Escola e modelo autorizado são descobertos automaticamente pela API a partir da credencial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping, Optional
import uuid

DEFAULT_VERTICE_API_URL = "http://127.0.0.1:8000"

_PADROES_SEGREDOS = (
    re.compile(r"vtx_ml_[A-Za-z0-9_\-]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)?"),
)

_BOOLEANOS_VERDADEIROS = {"1", "true", "t", "yes", "y", "sim", "s", "on"}
_BOOLEANOS_FALSOS = {"0", "false", "f", "no", "n", "nao", "não", "off", ""}


class ErroConfiguracaoPipeline(ValueError):
    """Configuração inválida ou incompleta para execução do pipeline ML."""


def mascarar_segredo(valor: Optional[str]) -> str:
    """Mascara tokens para exibição segura em logs e diagnósticos."""
    if not valor or not valor.strip():
        return "(não configurado)"
    limpo = valor.strip()
    if len(limpo) <= 10:
        return "***"
    prefixo = limpo[:10] if limpo.startswith("vtx_ml_") else limpo[:4]
    return f"{prefixo}...{limpo[-4:]}"


def sanitizar_texto_segredos(texto: str) -> str:
    """Remove ou mascara qualquer token/JWT acidentalmente presente em mensagens de erro."""
    resultado = texto or ""
    for padrao in _PADROES_SEGREDOS:
        resultado = padrao.sub(lambda m: mascarar_segredo(m.group(0)), resultado)
    return resultado


def normalizar_api_v1_url(url_bruta: Optional[str]) -> str:
    """
    Normaliza `VERTICE_API_URL` aceitando tanto URL base (`http://127.0.0.1:8000`)
    quanto URL com sufixo `/api/v1` (`http://127.0.0.1:8000/api/v1`).
    """
    if not url_bruta or not url_bruta.strip():
        raise ErroConfiguracaoPipeline(
            "Variável `VERTICE_API_URL` vazia. Informe uma URL iniciando com `http://` ou `https://`."
        )
    url = url_bruta.strip().rstrip("/")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ErroConfiguracaoPipeline(
            "`VERTICE_API_URL` deve iniciar com `http://` ou `https://`."
        )
    if url.endswith("/api/v1"):
        return url
    return f"{url}/api/v1"


def _parse_bool(valor: Any, nome_var: str, padrao: bool = False) -> bool:
    if valor is None:
        return padrao
    if isinstance(valor, bool):
        return valor
    texto = str(valor).strip().lower()
    if texto in _BOOLEANOS_VERDADEIROS:
        return True
    if texto in _BOOLEANOS_FALSOS:
        return False
    raise ErroConfiguracaoPipeline(
        f"Valor booleano inválido para `{nome_var}`: {valor!r}."
    )


def _parse_uuid_opcional(valor: Any, nome_var: str) -> Optional[uuid.UUID]:
    if valor is None:
        return None
    if isinstance(valor, uuid.UUID):
        return valor
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return uuid.UUID(texto)
    except ValueError as exc:
        raise ErroConfiguracaoPipeline(
            f"UUID inválido para `{nome_var}`: {texto!r}."
        ) from exc


def _parse_int(
    valor: Any,
    nome_var: str,
    padrao: Optional[int] = None,
    minimo: Optional[int] = None,
    maximo: Optional[int] = None,
) -> Optional[int]:
    if valor is None:
        return padrao
    if isinstance(valor, bool):
        raise ErroConfiguracaoPipeline(
            f"Valor inteiro inválido para `{nome_var}`."
        )
    texto = str(valor).strip()
    if not texto:
        return padrao
    try:
        numero = int(texto)
    except ValueError as exc:
        raise ErroConfiguracaoPipeline(
            f"Valor inteiro inválido para `{nome_var}`: {texto!r}."
        ) from exc
    if minimo is not None and numero < minimo:
        raise ErroConfiguracaoPipeline(
            f"`{nome_var}` deve ser maior ou igual a {minimo}."
        )
    if maximo is not None and numero > maximo:
        raise ErroConfiguracaoPipeline(
            f"`{nome_var}` deve ser menor ou igual a {maximo}."
        )
    return numero


def _parse_float(
    valor: Any,
    nome_var: str,
    padrao: float,
    minimo: float = 0.1,
) -> float:
    if valor is None:
        return padrao
    if isinstance(valor, bool):
        raise ErroConfiguracaoPipeline(
            f"Valor numérico inválido para `{nome_var}`."
        )
    texto = str(valor).strip()
    if not texto:
        return padrao
    try:
        numero = float(texto)
    except ValueError as exc:
        raise ErroConfiguracaoPipeline(
            f"Valor numérico inválido para `{nome_var}`: {texto!r}."
        ) from exc
    if numero < minimo:
        raise ErroConfiguracaoPipeline(
            f"`{nome_var}` deve ser maior ou igual a {minimo}."
        )
    return numero


@dataclass
class PipelineMLConfig:
    """Configuração operacional minimalista do pipeline de Machine Learning."""

    api_url: str = DEFAULT_VERTICE_API_URL
    service_token: Optional[str] = field(default=None, repr=False)
    turma_id: Optional[uuid.UUID] = None
    disciplina_id: Optional[uuid.UUID] = None
    ano_letivo: Optional[int] = None
    periodo_letivo: str = "1º Bimestre"
    batch_size: int = 500
    page_size: int = 200
    http_timeout_seconds: float = 30.0
    scheduler_enabled: bool = False
    scheduler_interval_seconds: int = 3600
    lock_file: Path = field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "vertice_ml_pipeline.lock"
    )

    def __post_init__(self) -> None:
        self.api_url = (
            self.api_url.strip()
            if isinstance(self.api_url, str) and self.api_url.strip()
            else DEFAULT_VERTICE_API_URL
        )
        _ = normalizar_api_v1_url(self.api_url)
        self.service_token = (
            self.service_token.strip()
            if isinstance(self.service_token, str) and self.service_token.strip()
            else None
        )
        self.periodo_letivo = (self.periodo_letivo or "1º Bimestre").strip()
        if not self.periodo_letivo:
            raise ErroConfiguracaoPipeline("`VERTICE_ML_PERIODO_LETIVO` não pode ser vazio.")
        if not isinstance(self.lock_file, Path):
            self.lock_file = Path(self.lock_file)
        if isinstance(self.batch_size, bool) or not (1 <= self.batch_size <= 2000):
            raise ErroConfiguracaoPipeline(
                "`VERTICE_ML_BATCH_SIZE` deve estar entre 1 e 2000."
            )
        if isinstance(self.page_size, bool) or not (1 <= self.page_size <= 1000):
            raise ErroConfiguracaoPipeline(
                "`VERTICE_ML_EXPORT_PAGE_SIZE` deve estar entre 1 e 1000."
            )
        if self.http_timeout_seconds <= 0:
            raise ErroConfiguracaoPipeline(
                "`VERTICE_ML_HTTP_TIMEOUT` deve ser maior que zero."
            )
        if isinstance(self.scheduler_interval_seconds, bool) or self.scheduler_interval_seconds < 1:
            raise ErroConfiguracaoPipeline(
                "`VERTICE_ML_SCHEDULER_INTERVAL_SECONDS` deve ser >= 1."
            )

    @property
    def api_v1_url(self) -> str:
        """Retorna URL normalizada terminando em `/api/v1`."""
        return normalizar_api_v1_url(self.api_url)

    @classmethod
    def from_env(
        cls,
        env: Optional[Mapping[str, str]] = None,
        *,
        overrides: Optional[Mapping[str, Any]] = None,
    ) -> "PipelineMLConfig":
        """Carrega configuração a partir de variáveis de ambiente com overrides opcionais."""
        fonte = env if env is not None else os.environ
        ov = dict(overrides or {})

        def _get(chave_ov: str, chave_env: str, padrao: Any = None) -> Any:
            if chave_ov in ov and ov[chave_ov] is not None:
                return ov[chave_ov]
            return fonte.get(chave_env, padrao)

        lock_file_raw = _get("lock_file", "VERTICE_ML_LOCK_FILE")

        return cls(
            api_url=str(
                _get("api_url", "VERTICE_API_URL", DEFAULT_VERTICE_API_URL)
                or DEFAULT_VERTICE_API_URL
            ),
            service_token=_get("service_token", "VERTICE_ML_SERVICE_TOKEN"),
            turma_id=_parse_uuid_opcional(
                _get("turma_id", "VERTICE_ML_TURMA_ID"),
                "VERTICE_ML_TURMA_ID",
            ),
            disciplina_id=_parse_uuid_opcional(
                _get("disciplina_id", "VERTICE_ML_DISCIPLINA_ID"),
                "VERTICE_ML_DISCIPLINA_ID",
            ),
            ano_letivo=_parse_int(
                _get("ano_letivo", "VERTICE_ML_ANO_LETIVO"),
                "VERTICE_ML_ANO_LETIVO",
                padrao=None,
                minimo=2000,
                maximo=2100,
            ),
            periodo_letivo=str(
                _get("periodo_letivo", "VERTICE_ML_PERIODO_LETIVO", "1º Bimestre")
                or "1º Bimestre"
            ),
            batch_size=_parse_int(
                _get("batch_size", "VERTICE_ML_BATCH_SIZE"),
                "VERTICE_ML_BATCH_SIZE",
                padrao=500,
                minimo=1,
                maximo=2000,
            )
            or 500,
            page_size=_parse_int(
                _get("page_size", "VERTICE_ML_EXPORT_PAGE_SIZE"),
                "VERTICE_ML_EXPORT_PAGE_SIZE",
                padrao=200,
                minimo=1,
                maximo=1000,
            )
            or 200,
            http_timeout_seconds=_parse_float(
                _get("http_timeout_seconds", "VERTICE_ML_HTTP_TIMEOUT"),
                "VERTICE_ML_HTTP_TIMEOUT",
                padrao=30.0,
                minimo=0.5,
            ),
            scheduler_enabled=_parse_bool(
                _get("scheduler_enabled", "VERTICE_ML_SCHEDULER_ENABLED"),
                "VERTICE_ML_SCHEDULER_ENABLED",
                padrao=False,
            ),
            scheduler_interval_seconds=_parse_int(
                _get(
                    "scheduler_interval_seconds",
                    "VERTICE_ML_SCHEDULER_INTERVAL_SECONDS",
                ),
                "VERTICE_ML_SCHEDULER_INTERVAL_SECONDS",
                padrao=3600,
                minimo=1,
            )
            or 3600,
            lock_file=(
                Path(lock_file_raw)
                if lock_file_raw
                else Path(tempfile.gettempdir()) / "vertice_ml_pipeline.lock"
            ),
        )

    def validar_configuracao(self) -> None:
        """Exige URL da API válida e credencial técnica única `VERTICE_ML_SERVICE_TOKEN`."""
        _ = self.api_v1_url
        if not self.service_token:
            raise ErroConfiguracaoPipeline(
                "Credencial técnica `VERTICE_ML_SERVICE_TOKEN` ausente. "
                "Emita manualmente o token no perfil Administrador (Credenciais ML) "
                "e configure-o na variável de ambiente `VERTICE_ML_SERVICE_TOKEN`."
            )

    def validar_para_extracao_remota(self) -> None:
        """Mantido por clareza semântica: extração usa o mesmo `VERTICE_ML_SERVICE_TOKEN`."""
        self.validar_configuracao()

    def validar_para_envio(self) -> None:
        """Valida pré-requisitos obrigatórios antes de enviar previsões em lote."""
        self.validar_configuracao()

    def resumo_seguro(self) -> dict[str, Any]:
        """Retorna resumo diagnóstico sem expor o token técnico."""
        return {
            "api_url": self.api_url,
            "api_v1_url": self.api_v1_url,
            "service_token": mascarar_segredo(self.service_token),
            "turma_id": str(self.turma_id) if self.turma_id else None,
            "disciplina_id": str(self.disciplina_id) if self.disciplina_id else None,
            "ano_letivo": self.ano_letivo,
            "periodo_letivo": self.periodo_letivo,
            "batch_size": self.batch_size,
            "page_size": self.page_size,
            "http_timeout_seconds": self.http_timeout_seconds,
            "scheduler_enabled": self.scheduler_enabled,
            "scheduler_interval_seconds": self.scheduler_interval_seconds,
            "lock_file": str(self.lock_file),
        }
