"""
Testes automatizados de governança e paridade entre código, OpenAPI e documentação.
"""

from __future__ import annotations

from pathlib import Path
import re

from app.integrations.prediction.leakage import CATALOGO_VARIAVEIS_PREDITIVAS
from app.main import app
from app.modules.usuarios.models import PapelUsuario

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
API_ENDPOINTS_MD = BACKEND_DIR / "docs" / "API_ENDPOINTS.md"
FASE7_MD = BACKEND_DIR / "docs" / "FASE7_INTEGRACAO_PREDITIVA_E_IA.md"


def test_openapi_e_api_endpoints_md_em_paridade() -> None:
    """
    Garante que todas as operações HTTP expostas no schema OpenAPI do FastAPI
    estejam documentadas em `backend/docs/API_ENDPOINTS.md` e vice-versa.
    """
    spec = app.openapi()
    metodos_http = {"get", "post", "put", "patch", "delete", "options", "head"}
    openapi_ops = {
        (metodo.upper(), rota)
        for rota, item in spec["paths"].items()
        for metodo in item
        if metodo.lower() in metodos_http
    }

    conteudo = API_ENDPOINTS_MD.read_text(encoding="utf-8")
    doc_ops = {
        (metodo.upper(), rota)
        for metodo, rota in re.findall(
            r"\|\s*`([A-Z]+)`\s*\|\s*`(/[^`]*)`\s*\|",
            conteudo,
        )
    }

    ausentes_na_doc = sorted(openapi_ops - doc_ops)
    inexistentes_na_api = sorted(doc_ops - openapi_ops)
    assert not ausentes_na_doc, f"Rotas presentes no OpenAPI ausentes em API_ENDPOINTS.md: {ausentes_na_doc}"
    assert not inexistentes_na_api, f"Rotas documentadas inexistentes no OpenAPI: {inexistentes_na_api}"
    assert str(len(openapi_ops)) in conteudo


def test_documentacao_interativa_reflete_configuracao_main() -> None:
    """Confirma coerência entre caminhos de OpenAPI/Swagger/ReDoc em app/main.py e docs."""
    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/api/v1/openapi.json"

    conteudo = API_ENDPOINTS_MD.read_text(encoding="utf-8")
    assert "/api/v1/openapi.json" in conteudo
    assert "apenas quando `DEBUG=True`" not in conteudo


def test_papeis_canonicos_sem_coordenador() -> None:
    """Assegura que os papéis canônicos do sistema permanecem exclusivamente três."""
    valores = {papel.value for papel in PapelUsuario}
    assert valores == {"administrador", "gestor", "professor"}
    assert "coordenador" not in valores


def test_catalogo_preditivo_alinhado_com_doc_fase7() -> None:
    """Garante que a lista de variáveis elegíveis da documentação Fase 7 reflita leakage.py."""
    conteudo = FASE7_MD.read_text(encoding="utf-8")
    m = re.search(
        r"\*\*Variáveis elegíveis \(`CATALOGO_VARIAVEIS_PREDITIVAS`\):\*\*\s*(.+)",
        conteudo,
    )
    assert m is not None, "Linha de CATALOGO_VARIAVEIS_PREDITIVAS não encontrada na doc Fase 7."
    variaveis_doc = set(re.findall(r"`([a-z0-9_]+)`", m.group(1)))
    assert variaveis_doc == {item.nome for item in CATALOGO_VARIAVEIS_PREDITIVAS}


def test_documentacao_raiz_e_seguranca_compose_padrao() -> None:
    """Verifica existência dos guias operacionais e ausência de porta 5432 no compose padrão."""
    assert (REPO_ROOT / "docs" / "INSTALACAO_E_COLD_START.md").is_file()
    assert (REPO_ROOT / "docs" / "MANUTENCAO_E_DESENVOLVIMENTO.md").is_file()
    assert (REPO_ROOT / "docs" / "ARQUITETURA_E_COMPATIBILIDADE.md").is_file()
    assert (REPO_ROOT / "docker-compose.postgres-local.yml").is_file()

    compose_txt = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert ":5432" not in compose_txt
