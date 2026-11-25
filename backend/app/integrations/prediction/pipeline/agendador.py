"""
Agendador desacoplado do pipeline automatizado de Machine Learning do Vértice.

Executa em processo independente com:
- Ativação e desativação via `VERTICE_ML_SCHEDULER_ENABLED`.
- Intervalo configurável via `VERTICE_ML_SCHEDULER_INTERVAL_SECONDS`.
- Execução manual pontual (`--once`) e modo teste (`--dry-run`).
- Proteção contra execuções simultâneas (entre threads no mesmo processo e entre
  processos distintos do SO via lock não bloqueante em arquivo).
- Registro estruturado de início, término, duração e resultado de cada ciclo.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import signal
import sys
import threading
import time
from typing import Any, Optional

from app.integrations.prediction.pipeline.config import (
    ErroConfiguracaoPipeline,
    PipelineMLConfig,
    sanitizar_texto_segredos,
)
from app.integrations.prediction.pipeline.executor import (
    ExecutorPipelineML,
    RelatorioExecucaoPipeline,
)

if os.name == "nt":
    import msvcrt
else:
    import fcntl

logger = logging.getLogger(__name__)

_GUARD_LOCKS_PROCESSO = threading.Lock()
_LOCKS_EM_PROCESSO: dict[Path, threading.Lock] = {}


class ErroExecucaoSimultanea(RuntimeError):
    """Levantada quando já existe outra execução ativa segurando o lock do pipeline."""


def _obter_lock_em_memoria(caminho_lock: Path) -> threading.Lock:
    caminho_norm = caminho_lock.resolve()
    with _GUARD_LOCKS_PROCESSO:
        lock = _LOCKS_EM_PROCESSO.get(caminho_norm)
        if lock is None:
            lock = threading.Lock()
            _LOCKS_EM_PROCESSO[caminho_norm] = lock
        return lock


class BloqueioExecucaoSimultanea:
    """
    Lock híbrido (memória + arquivo OS não bloqueante) que impede que duas
    execuções concorrentes processem e enviem o mesmo lote de previsões.
    """

    def __init__(self, caminho_lock: Path) -> None:
        self.caminho_lock = Path(caminho_lock).resolve()
        self._mem_lock = _obter_lock_em_memoria(self.caminho_lock)
        self._mem_adquirido = False
        self._fd: Optional[int] = None

    def __enter__(self) -> "BloqueioExecucaoSimultanea":
        if not self._mem_lock.acquire(blocking=False):
            raise ErroExecucaoSimultanea(
                f"Execução simultânea detectada no lock `{self.caminho_lock}`."
            )
        self._mem_adquirido = True

        try:
            self.caminho_lock.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(
                str(self.caminho_lock),
                os.O_CREAT | os.O_RDWR,
                0o600,
            )
            self._fd = fd
            if os.name == "nt":
                # Garante pelo menos 1 byte para trava determinística via msvcrt.locking
                if os.path.getsize(self.caminho_lock) == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._liberar()
            raise ErroExecucaoSimultanea(
                f"Já existe outra instância do pipeline ativa em `{self.caminho_lock}`."
            ) from exc
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self._liberar()

    def _liberar(self) -> None:
        if self._fd is not None:
            try:
                if os.name == "nt":
                    os.lseek(self._fd, 0, os.SEEK_SET)
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

        if self._mem_adquirido:
            self._mem_lock.release()
            self._mem_adquirido = False


@dataclass
class RegistroCicloAgendador:
    """Registro de auditoria local de cada ciclo disparado pelo agendador."""

    ciclo: int
    status: str  # EXECUTADO_SUCESSO | EXECUTADO_FALHA | DESABILITADO | IGNORADO_CONCORRENCIA
    inicio_em: datetime
    fim_em: datetime
    duracao_ms: float
    sucesso: bool
    modo: str
    etapa_falha: Optional[str] = None
    erro: Optional[str] = None
    extraidos: int = 0
    validos: int = 0
    rejeitados: int = 0
    inferidos: int = 0
    persistidos: int = 0

    def to_dict(self) -> dict[str, Any]:
        dados = asdict(self)
        dados["inicio_em"] = self.inicio_em.isoformat()
        dados["fim_em"] = self.fim_em.isoformat()
        return dados


class AgendadorPipelineML:
    """Agendador periódico controlado e desacoplado da API FastAPI."""

    def __init__(
        self,
        config: PipelineMLConfig,
        *,
        executor_factory: Optional[Callable[[PipelineMLConfig], Any]] = None,
    ) -> None:
        self.config = config
        self._executor_factory = executor_factory or (
            lambda cfg: ExecutorPipelineML(cfg)
        )
        self.stop_event = threading.Event()
        self.historico: list[RegistroCicloAgendador] = []
        self._contador_ciclos = 0

    def solicitar_parada(self) -> None:
        """Sinaliza parada graciosa após o término do ciclo corrente."""
        self.stop_event.set()

    def executar_ciclo(
        self,
        *,
        enviar: bool = True,
        forcar: bool = False,
    ) -> RegistroCicloAgendador:
        """Executa um único ciclo respeitando habilitação e lock de concorrência."""
        self._contador_ciclos += 1
        num_ciclo = self._contador_ciclos
        inicio = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        modo = "send" if enviar else "dry-run"

        if not self.config.scheduler_enabled and not forcar:
            fim = datetime.now(timezone.utc)
            reg = RegistroCicloAgendador(
                ciclo=num_ciclo,
                status="DESABILITADO",
                inicio_em=inicio,
                fim_em=fim,
                duracao_ms=0.0,
                sucesso=False,
                modo=modo,
                erro=(
                    "Agendamento desabilitado (`VERTICE_ML_SCHEDULER_ENABLED=false`)."
                ),
            )
            self.historico.append(reg)
            logger.info("Ciclo %d não executado: agendamento desabilitado.", num_ciclo)
            return reg

        try:
            with BloqueioExecucaoSimultanea(self.config.lock_file):
                executor = self._executor_factory(self.config)
                rel: RelatorioExecucaoPipeline = executor.executar(enviar=enviar)
                fim = datetime.now(timezone.utc)
                duracao = round((time.perf_counter() - t0) * 1000.0, 2)
                reg = RegistroCicloAgendador(
                    ciclo=num_ciclo,
                    status="EXECUTADO_SUCESSO" if rel.sucesso else "EXECUTADO_FALHA",
                    inicio_em=inicio,
                    fim_em=fim,
                    duracao_ms=duracao,
                    sucesso=rel.sucesso,
                    modo=modo,
                    etapa_falha=rel.etapa_falha,
                    erro=rel.erro,
                    extraidos=rel.extraidos,
                    validos=rel.validos,
                    rejeitados=rel.rejeitados_transformacao,
                    inferidos=rel.inferidos,
                    persistidos=rel.persistidos,
                )
        except ErroExecucaoSimultanea as exc:
            fim = datetime.now(timezone.utc)
            duracao = round((time.perf_counter() - t0) * 1000.0, 2)
            reg = RegistroCicloAgendador(
                ciclo=num_ciclo,
                status="IGNORADO_CONCORRENCIA",
                inicio_em=inicio,
                fim_em=fim,
                duracao_ms=duracao,
                sucesso=False,
                modo=modo,
                etapa_falha="concorrencia",
                erro=str(exc),
            )
            logger.warning("Ciclo %d ignorado por lock ativo: %s", num_ciclo, exc)
        except Exception as exc:
            fim = datetime.now(timezone.utc)
            duracao = round((time.perf_counter() - t0) * 1000.0, 2)
            msg = sanitizar_texto_segredos(str(exc))
            reg = RegistroCicloAgendador(
                ciclo=num_ciclo,
                status="EXECUTADO_FALHA",
                inicio_em=inicio,
                fim_em=fim,
                duracao_ms=duracao,
                sucesso=False,
                modo=modo,
                etapa_falha="inesperada",
                erro=msg,
            )
            logger.exception("Erro inesperado no ciclo %d do agendador ML: %s", num_ciclo, msg)

        self.historico.append(reg)
        logger.info(
            "Ciclo agendador ML | ciclo=%d | status=%s | sucesso=%s | extraidos=%d | inferidos=%d | persistidos=%d | duracao_ms=%.2f",
            reg.ciclo,
            reg.status,
            reg.sucesso,
            reg.extraidos,
            reg.inferidos,
            reg.persistidos,
            reg.duracao_ms,
        )
        return reg

    def iniciar_loop(
        self,
        *,
        enviar: bool = True,
        max_cycles: Optional[int] = None,
        wait_fn: Optional[Callable[[float], bool]] = None,
    ) -> list[RegistroCicloAgendador]:
        """
        Inicia o loop periódico respeitando `scheduler_enabled` e `scheduler_interval_seconds`.
        """
        if not self.config.scheduler_enabled:
            logger.info(
                "Agendador ML desativado (`VERTICE_ML_SCHEDULER_ENABLED=false`). "
                "Nenhuma execução programada iniciada."
            )
            return []

        esperar = wait_fn or self.stop_event.wait
        executados = 0
        while not self.stop_event.is_set():
            self.executar_ciclo(enviar=enviar, forcar=False)
            executados += 1
            if max_cycles is not None and executados >= max_cycles:
                break
            if esperar(float(self.config.scheduler_interval_seconds)):
                break
        return list(self.historico)


def _construir_parser_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.integrations.prediction.pipeline.agendador",
        description="Agendador periódico independente do Pipeline ML do Vértice.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa um único ciclo manual sob lock de concorrência (ignora flag de agendamento desabilitado).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa o(s) ciclo(s) sem enviar nem persistir previsões na API.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Intervalo em segundos entre ciclos (sobrescreve VERTICE_ML_SCHEDULER_INTERVAL_SECONDS).",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Limita o número total de ciclos executados antes de encerrar.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Exibe histórico estruturado em JSON ao finalizar.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = _construir_parser_cli()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = PipelineMLConfig.from_env(
            overrides={"scheduler_interval_seconds": args.interval}
        )
    except ErroConfiguracaoPipeline as exc:
        print(f"Erro de configuração do agendador: {exc}", file=sys.stderr)
        return 2

    agendador = AgendadorPipelineML(config)

    def _tratar_sinal(_signum: int, _frame: Any) -> None:
        agendador.solicitar_parada()

    for sig_nome in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_nome, None)
        if sig is not None:
            try:
                signal.signal(sig, _tratar_sinal)
            except ValueError:
                pass

    enviar = not args.dry_run
    if args.once:
        reg = agendador.executar_ciclo(enviar=enviar, forcar=True)
        registros = [reg]
    else:
        if not config.scheduler_enabled:
            print(
                "Agendador desabilitado (`VERTICE_ML_SCHEDULER_ENABLED=false`). "
                "Defina `VERTICE_ML_SCHEDULER_ENABLED=true` ou execute com `--once`.",
                file=sys.stdout,
            )
            return 0
        registros = agendador.iniciar_loop(
            enviar=enviar,
            max_cycles=args.max_cycles,
        )

    if args.json:
        print(json.dumps([r.to_dict() for r in registros], ensure_ascii=False, indent=2))
    else:
        for r in registros:
            print(
                f"[Agendador ML] ciclo={r.ciclo} | status={r.status} | "
                f"sucesso={r.sucesso} | inferidos={r.inferidos} | "
                f"persistidos={r.persistidos} | duracao_ms={r.duracao_ms}"
            )
            if not r.sucesso and r.erro:
                print(f"Detalhe ciclo {r.ciclo}: {r.erro}", file=sys.stderr)

    if not registros:
        return 0
    return 0 if all(r.sucesso for r in registros) else 1


if __name__ == "__main__":
    raise SystemExit(main())
