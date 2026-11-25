"""
Suíte completa de testes da integração simplificada e do Pipeline ML do Vértice:
1. Descoberta dinâmica de modelos (`catalogo_modelos.py` e `GET /api/v1/previsoes/modelos-disponiveis`)
   e tela simplificada de emissão/revogação de Credenciais ML (`administracao_tecnica.py`).
2. Credencial técnica única (`X-Service-Token`) autorizando extração controlada
   (`GET /api/v1/previsoes/exportacao-inferencia`) e envio em lote (`POST /api/v1/previsoes/lote`),
   com bloqueio para credenciais legadas (`permite_leitura_inferencia=False`), revogadas e JWT comum.
3. Descoberta automática de escola e modelo no pipeline sem `VERTICE_ML_SCHOOL_ID`,
   `VERTICE_ML_MODEL_NAME` ou segunda chave de exportação.
4. Transformação anti-Data Leakage, inferência local (e falha clara com artefato ausente),
   cliente HTTP, agendador concorrente e fluxo ponta a ponta até `indicadores/gerais` e `visao_geral.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
from typing import Any
import uuid

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.prediction.catalogo_modelos import (
    listar_modelos_preditivos,
    obter_modelo_preditivo,
)
from app.integrations.prediction.models import (
    CredencialIntegracaoPredicao,
    PrevisaoRisco,
    TipoPrevisao,
)
from app.integrations.prediction.pipeline.agendador import (
    AgendadorPipelineML,
    BloqueioExecucaoSimultanea,
)
from app.integrations.prediction.pipeline.cliente_api import (
    ClienteAPIPrevisoes,
    ErroEnvioAutenticacao,
    ErroEnvioAutorizacao,
    ErroEnvioComunicacao,
    ErroEnvioConflitoIdempotencia,
    ErroEnvioValidacao,
    PrevisaoItemEnvio,
)
from app.integrations.prediction.pipeline.config import PipelineMLConfig
from app.integrations.prediction.pipeline.executor import ExecutorPipelineML
from app.integrations.prediction.pipeline.extrator import (
    ErroExtracaoAutorizacao,
    ErroExtracaoComunicacao,
    ErroExtracaoConfiguracao,
    ExtratorDadosInferencia,
)
from app.integrations.prediction.pipeline.transformador import (
    ErroTransformacaoLeakage,
    TransformadorDadosInferencia,
)
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import BoletimPeriodo
from tests.test_fase4_modulos_pedagogicos import _criar_cenario_fase4
from tests.test_fase8_integracao_final import _adaptar_testclient_completo, _preparar_frontend

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _login_headers(client: TestClient, email: str, senha: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "senha": senha})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _emitir_credencial_ml_simplificada(
    client: TestClient,
    headers_admin: dict[str, str],
    *,
    nome: str,
    escola_id: uuid.UUID,
    modelo_autorizado: str = "regressao_logistica",
) -> tuple[str, str]:
    resp = client.post(
        "/api/v1/previsoes/credenciais",
        json={
            "nome": nome,
            "escola_id": str(escola_id),
            "modelo_autorizado": modelo_autorizado,
        },
        headers=headers_admin,
    )
    assert resp.status_code == 201, resp.text
    dados = resp.json()
    assert str(dados["chave_secreta"]).startswith("vtx_ml_")
    assert dados["permite_leitura_inferencia"] is True
    assert dados["modelo_autorizado"] == modelo_autorizado
    return str(dados["id"]), str(dados["chave_secreta"])


def _instrumentar_ui_stub(st_mod: Any) -> list[dict[str, Any]]:
    """Instrumenta stub compatível com `administracao_tecnica.py` e `visao_geral.py`."""
    registros: list[dict[str, Any]] = []

    go_mod = sys.modules.get("plotly.graph_objects")
    if go_mod is not None and not hasattr(go_mod, "Figure"):

        class _FakeGoFigure:
            def __init__(self, *_a: Any, **_kw: Any) -> None:
                self.layout: dict[str, Any] = {}

            def update_layout(self, **kwargs: Any) -> "_FakeGoFigure":
                self.layout.update(kwargs)
                return self

        go_mod.Figure = _FakeGoFigure

    class _BoxStub:
        def __init__(self, key: str | None = None, border: bool | None = None) -> None:
            self.key = key
            self.border = border
            self.subheaders: list[str] = []
            self.captions: list[str] = []
            self.metrics: list[tuple[Any, Any]] = []

        def __enter__(self) -> "_BoxStub":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def subheader(self, texto: Any, **_kw: Any) -> None:
            self.subheaders.append(str(texto))

        def caption(self, texto: Any, **_kw: Any) -> None:
            self.captions.append(str(texto))

        def metric(self, label: Any = None, value: Any = None, *_a: Any, **_kw: Any) -> None:
            self.metrics.append((label, value))
            registros.append({"tipo": "metric", "label": label, "value": value})

    def _container(*, key: str | None = None, border: bool | None = None, **_kw: Any) -> _BoxStub:
        box = _BoxStub(key=key, border=border)
        registros.append({"tipo": "container", "key": key, "box": box})
        return box

    def _registrar(tipo: str):
        def _fn(msg: Any = "", *args: Any, **kwargs: Any) -> Any:
            registros.append({"tipo": tipo, "mensagem": msg, "args": args, "kwargs": kwargs})
            return None

        return _fn

    def _selectbox(label: str, options=(), **kwargs: Any) -> Any:
        registros.append({"tipo": "selectbox", "label": label, "options": list(options)})
        return list(options)[0] if options else None

    st_mod.container = _container
    st_mod.columns = lambda spec, **_kw: [
        _BoxStub(key=f"col_{i}") for i in range(spec if isinstance(spec, int) else len(spec))
    ]
    st_mod.form = lambda key="", **_kw: _BoxStub(key=f"form_{key}")
    st_mod.expander = lambda label="", **_kw: _BoxStub(key=f"exp_{label}")
    st_mod.metric = lambda label=None, value=None, *_a, **_kw: registros.append(
        {"tipo": "metric", "label": label, "value": value}
    )
    st_mod.selectbox = _selectbox
    st_mod.empty = lambda: SimpleNamespace(selectbox=st_mod.selectbox)
    st_mod.text_input = lambda label, value="", **_kw: value
    st_mod.form_submit_button = lambda *_a, **_kw: False
    st_mod.code = _registrar("code")
    st_mod.plotly_chart = _registrar("plotly_chart")
    st_mod.dataframe = _registrar("dataframe")
    st_mod.caption = _registrar("caption")
    st_mod.subheader = _registrar("subheader")
    st_mod.info = _registrar("info")
    st_mod.warning = _registrar("warning")
    st_mod.error = _registrar("error")
    st_mod.success = _registrar("success")
    st_mod.title = _registrar("title")
    st_mod.markdown = _registrar("markdown")
    st_mod.page_link = _registrar("page_link")
    st_mod.button = lambda *_a, **_kw: False
    st_mod.switch_page = _registrar("switch_page")
    return registros


def _config_para_testclient(
    *,
    service_token: str | None = None,
    batch_size: int = 500,
    page_size: int = 200,
    periodo_letivo: str = "1º Bimestre",
    lock_file: Path | None = None,
    scheduler_enabled: bool = False,
    scheduler_interval_seconds: int = 60,
) -> PipelineMLConfig:
    kwargs: dict[str, object] = {
        "api_url": "http://testserver",
        "service_token": service_token,
        "batch_size": batch_size,
        "page_size": page_size,
        "periodo_letivo": periodo_letivo,
        "scheduler_enabled": scheduler_enabled,
        "scheduler_interval_seconds": scheduler_interval_seconds,
    }
    if lock_file is not None:
        kwargs["lock_file"] = lock_file
    return PipelineMLConfig(**kwargs)  # type: ignore[arg-type]


# ==============================================================================
# 1. EMISSÃO DE CREDENCIAIS E DESCOBERTA DE MODELOS (API + UI ADMIN)
# ==============================================================================


def test_emissao_credenciais_catalogo_modelos_exibicao_unica_e_revogacao(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Valida:
    - Lista de modelos vem preenchida dinamicamente dos modelos disponíveis.
    - Modelo e escola selecionados ficam vinculados à credencial.
    - Token completo só é exibido na emissão (nunca na listagem).
    - Revogação funciona e bloqueia leitura e envio.
    - Tela `Credenciais ML` lista escolas ativas e modelos sem entrada manual separada por vírgula.
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")

    # 1. Rota `/modelos-disponiveis` restrita a Administrador e coerente com `catalogo_modelos`
    assert client.get("/api/v1/previsoes/modelos-disponiveis", headers=headers_gestor).status_code == 403
    resp_modelos = client.get("/api/v1/previsoes/modelos-disponiveis", headers=headers_admin)
    assert resp_modelos.status_code == 200, resp_modelos.text
    modelos_api = resp_modelos.json()
    modelos_cat = listar_modelos_preditivos(apenas_disponiveis=True)
    assert len(modelos_api) == len(modelos_cat) >= 1
    assert modelos_api[0]["modelo_nome"] == "regressao_logistica"
    assert modelos_api[0]["modelo_versao"] == "poc-risco-academico-uci-v1"
    assert modelos_api[0]["disponivel_inferencia"] is True

    # 2. Modelo inexistente é rejeitado na emissão
    resp_invalido = client.post(
        "/api/v1/previsoes/credenciais",
        json={
            "nome": "Modelo Inexistente",
            "escola_id": str(cenario["escola_a"].id),
            "modelo_autorizado": "modelo_fantasma",
        },
        headers=headers_admin,
    )
    assert resp_invalido.status_code == 422

    # 3. Emissão válida vincula escola + modelo + leitura e exibe token somente na criação
    cred_id, segredo = _emitir_credencial_ml_simplificada(
        client,
        headers_admin,
        nome="Pipeline Escola A",
        escola_id=cenario["escola_a"].id,
        modelo_autorizado="regressao_logistica",
    )
    resp_lista = client.get("/api/v1/previsoes/credenciais", headers=headers_admin)
    assert resp_lista.status_code == 200
    itens = resp_lista.json()
    criada = next(it for it in itens if it["id"] == cred_id)
    assert "chave_secreta" not in criada
    assert criada["escola_id"] == str(cenario["escola_a"].id)
    assert criada["modelo_autorizado"] == "regressao_logistica"
    assert criada["modelos_permitidos"] == ["regressao_logistica"]
    assert criada["permite_leitura_inferencia"] is True
    assert criada["ativo"] is True

    # 4. Revogação funciona
    resp_rev = client.patch(
        f"/api/v1/previsoes/credenciais/{cred_id}/revogar",
        headers=headers_admin,
    )
    assert resp_rev.status_code == 200
    assert resp_rev.json()["ativo"] is False
    assert (
        client.get(
            "/api/v1/previsoes/exportacao-inferencia",
            headers={"X-Service-Token": segredo},
        ).status_code
        == 403
    )

    # 5. Tela administrativa simplificada consome `/previsoes/modelos-disponiveis` e submete modelo selecionado
    st_mod = _preparar_frontend()
    registros_ui = _instrumentar_ui_stub(st_mod)

    import components.cards as cards_mod
    import data.api_client as api_client
    import pages.administracao_tecnica as pg_adm

    importlib.reload(cards_mod)
    importlib.reload(api_client)
    importlib.reload(pg_adm)
    api_client.configurar_cliente_http_teste(_adaptar_testclient_completo(client))

    try:
        assert api_client.autenticar_usuario_api("admin@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        st_mod.session_state["logado"] = True

        st_mod.text_input = lambda label, value="", **_kw: (
            "Pipeline Via Tela Admin" if "Identificação" in label else value
        )
        st_mod.form_submit_button = lambda *_a, **_kw: True

        pg_adm.render_credenciais_ml()

        selectboxes = [r for r in registros_ui if r["tipo"] == "selectbox"]
        sb_escola = next(s for s in selectboxes if s["label"] == "Escola")
        sb_modelo = next(s for s in selectboxes if s["label"] == "Modelo de Machine Learning")
        assert "Escola Estadual Norte" in sb_escola["options"][0]
        assert any("Risco Acadêmico" in opt for opt in sb_modelo["options"])
        assert not any("separados por vírgula" in s["label"] for s in selectboxes)

        # Verifica no banco que a credencial emitida pela UI foi salva corretamente
        cred_ui = (
            db_session.query(CredencialIntegracaoPredicao)
            .filter(CredencialIntegracaoPredicao.nome == "Pipeline Via Tela Admin")
            .one()
        )
        assert cred_ui.escola_id == cenario["escola_a"].id
        assert cred_ui.modelos_permitidos == ["regressao_logistica"]
        assert cred_ui.permite_leitura_inferencia is True
    finally:
        api_client.configurar_cliente_http_teste(None)
        st_mod.session_state.clear()


# ==============================================================================
# 2. EXTRAÇÃO CONTROLADA COM TOKEN ÚNICO E ISOLAMENTO DE ESCOLA
# ==============================================================================


def test_extracao_token_unico_escopo_revogacao_legado_paginacao_e_vazio(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Valida que o mesmo `X-Service-Token` autoriza leitura escopada à escola, enquanto
    credenciais sem `permite_leitura_inferencia`, revogadas, tokens comuns e inválidos são bloqueados.
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")

    for est_key, idade_val in (("est1", 15), ("est2", 17), ("est3", 16), ("est4", 18)):
        bol = db_session.execute(
            select(BoletimPeriodo).where(
                BoletimPeriodo.estudante_id == cenario[est_key].id,
                BoletimPeriodo.periodo_letivo == "1º Bimestre",
            )
        ).scalar_one()
        bol.idade = idade_val
    db_session.commit()

    cred_id_a, token_a = _emitir_credencial_ml_simplificada(
        client,
        headers_admin,
        nome="Pipeline Unificado Escola A",
        escola_id=cenario["escola_a"].id,
        modelo_autorizado="regressao_logistica",
    )

    # 1. Credencial legada (sem permissão de leitura explícita) continua sendo somente escrita -> 403 na leitura
    resp_legada = client.post(
        "/api/v1/previsoes/credenciais",
        json={
            "nome": "Credencial Legada Somente Envio",
            "escola_id": str(cenario["escola_a"].id),
            "modelos_permitidos": ["regressao_logistica"],
            "permite_leitura_inferencia": False,
        },
        headers=headers_admin,
    )
    assert resp_legada.status_code == 201
    token_legado = resp_legada.json()["chave_secreta"]
    assert (
        client.get(
            "/api/v1/previsoes/exportacao-inferencia",
            headers={"X-Service-Token": token_legado},
        ).status_code
        == 403
    )

    # 2. Token comum JWT (gestor/admin) ou token inválido/ausente são rejeitados na exportação
    assert client.get("/api/v1/previsoes/exportacao-inferencia").status_code == 401
    assert (
        client.get(
            "/api/v1/previsoes/exportacao-inferencia",
            headers={"X-Service-Token": "vtx_ml_TokenInvalido123456"},
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/previsoes/exportacao-inferencia",
            headers=headers_gestor_a,
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/previsoes/exportacao-inferencia",
            headers=headers_admin,
        ).status_code
        == 403
    )

    # 3. Tentativa de consultar outra escola via query param é bloqueada com 403
    assert (
        client.get(
            "/api/v1/previsoes/exportacao-inferencia",
            params={"escola_id": str(cenario["escola_b"].id)},
            headers={"X-Service-Token": token_a},
        ).status_code
        == 403
    )

    # 4. Período pós-corte é bloqueado com 422
    assert (
        client.get(
            "/api/v1/previsoes/exportacao-inferencia",
            params={"periodo_letivo": "2º Bimestre"},
            headers={"X-Service-Token": token_a},
        ).status_code
        == 422
    )

    # 5. Extrator automático sem `VERTICE_ML_SCHOOL_ID` descobre escola/modelo e pagina corretamente
    cfg_paginado = _config_para_testclient(service_token=token_a, page_size=2)
    res_extracao = ExtratorDadosInferencia(cfg_paginado, http_client=client).extrair()
    assert res_extracao.escola_id == cenario["escola_a"].id
    assert res_extracao.modelo_nome == "regressao_logistica"
    assert res_extracao.modelo_versao == "poc-risco-academico-uci-v1"
    assert res_extracao.total_reportado == 4
    assert res_extracao.paginas_consultadas == 2
    assert len(res_extracao.registros) == 4
    assert all(r["escola_id"] == str(cenario["escola_a"].id) for r in res_extracao.registros)
    assert str(cenario["est_b1"].id) not in {r["estudante_id"] for r in res_extracao.registros}

    # 6. Escola sem estudantes retorna lista vazia limpa com metadados da credencial
    escola_vazia = Escola(nome="Escola Sem Alunos", codigo="ESA-01", ativo=True)
    db_session.add(escola_vazia)
    db_session.commit()
    _, token_vazio = _emitir_credencial_ml_simplificada(
        client,
        headers_admin,
        nome="Pipeline Escola Vazia",
        escola_id=escola_vazia.id,
        modelo_autorizado="regressao_logistica",
    )
    res_vazia = ExtratorDadosInferencia(
        _config_para_testclient(service_token=token_vazio),
        http_client=client,
    ).extrair()
    assert res_vazia.total_reportado == 0
    assert res_vazia.registros == []
    assert res_vazia.escola_id == escola_vazia.id
    assert res_vazia.modelo_nome == "regressao_logistica"

    # 7. Credencial revogada é bloqueada na extração
    assert (
        client.patch(
            f"/api/v1/previsoes/credenciais/{cred_id_a}/revogar",
            headers=headers_admin,
        ).status_code
        == 200
    )
    with pytest.raises(ErroExtracaoAutorizacao, match="revogada"):
        ExtratorDadosInferencia(cfg_paginado, http_client=client).extrair()


def test_extrator_falha_comunicacao_e_ausencia_token() -> None:
    """Erro de rede/timeout e ausência de token geram exceções explícitas."""
    with pytest.raises(ErroExtracaoConfiguracao, match="VERTICE_ML_SERVICE_TOKEN"):
        ExtratorDadosInferencia(_config_para_testclient(service_token=None)).extrair()

    def _falha_rede(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Backend inacessível")

    cliente_falho = httpx.Client(transport=httpx.MockTransport(_falha_rede))
    cfg = _config_para_testclient(service_token="vtx_ml_TokenTesteRede1234567890")
    with pytest.raises(ErroExtracaoComunicacao, match="comunicação"):
        ExtratorDadosInferencia(cfg, http_client=cliente_falho).extrair()


# ==============================================================================
# 3. TRANSFORMAÇÃO E PROTEÇÃO ANTI-DATA LEAKAGE
# ==============================================================================


def test_transformacao_validos_ausentes_tipos_limites_e_anti_leakage() -> None:
    """Valida regras de transformação sem alterar silenciosamente valores inválidos."""
    escola_id = uuid.uuid4()
    turma_id = uuid.uuid4()
    transf = TransformadorDadosInferencia(escola_id_esperada=escola_id)

    est_ok = str(uuid.uuid4())
    est_g1 = str(uuid.uuid4())
    est_sem_nota = str(uuid.uuid4())
    est_sem_contexto = str(uuid.uuid4())
    est_tipo_invalido = str(uuid.uuid4())
    est_fora_limite = str(uuid.uuid4())

    resultado = transf.transformar(
        [
            {
                "estudante_id": est_ok,
                "escola_id": str(escola_id),
                "turma_id": str(turma_id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "idade": 16,
                "historico_reprovacoes": 1,
                "nota_t1": 6.5,
            },
            {
                "estudante_id": est_g1,
                "escola_id": str(escola_id),
                "turma_id": str(turma_id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "idade": None,
                "historico_reprovacoes": 0,
                "G1": 14,
            },
            {
                "estudante_id": est_sem_nota,
                "escola_id": str(escola_id),
                "turma_id": str(turma_id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "idade": 16,
                "historico_reprovacoes": 0,
                "nota_t1": None,
            },
            {
                "estudante_id": est_sem_contexto,
                "escola_id": str(escola_id),
                "turma_id": str(turma_id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "idade": None,
                "historico_reprovacoes": None,
                "nota_t1": 7.0,
            },
            {
                "estudante_id": est_tipo_invalido,
                "escola_id": str(escola_id),
                "turma_id": str(turma_id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "idade": True,
                "historico_reprovacoes": 0,
                "nota_t1": 7.0,
            },
            {
                "estudante_id": est_fora_limite,
                "escola_id": str(escola_id),
                "turma_id": str(turma_id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "idade": 16,
                "historico_reprovacoes": 0,
                "nota_t1": 11.5,
            },
        ]
    )

    assert resultado.total_recebidos == 6
    assert resultado.total_validos == 2
    assert resultado.total_rejeitados == 4
    assert [str(r.estudante_id) for r in resultado.validos] == [est_ok, est_g1]
    assert resultado.validos[1].nota_t1 == 7.0
    assert resultado.validos[1].variaveis_utilizadas == ["historico_reprovacoes", "nota_t1"]

    for campo_proibido, valor in [
        ("situacao_final", "Aprovado"),
        ("target", 1),
        ("classe_real", 0),
        ("nota_t2", 7.5),
        ("g2", 14),
        ("nota_t3", 8.0),
        ("g3", 16),
        ("media_geral", 7.2),
        ("ausencias", 5),
        ("absences", 4),
        ("faltas", 3),
        ("frequencia_percentual", 92.0),
        ("nome", "Estudante Não Anonimizado"),
    ]:
        with pytest.raises(ErroTransformacaoLeakage):
            transf.transformar(
                [
                    {
                        "estudante_id": str(uuid.uuid4()),
                        "escola_id": str(escola_id),
                        "ano_letivo": 2026,
                        "periodo_letivo": "1º Bimestre",
                        "idade": 16,
                        "historico_reprovacoes": 0,
                        "nota_t1": 7.0,
                        campo_proibido: valor,
                    }
                ]
            )


# ==============================================================================
# 4. INFERÊNCIA, FALHA SEM ARTEFATO DO MODELO VINCULADO E SAÍDA INVÁLIDA
# ==============================================================================


def test_inferencia_interrompe_quando_artefato_da_credencial_indisponivel(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Se o artefato correspondente ao modelo da credencial não estiver disponível, o pipeline
    deve interromper imediatamente sem treinar nem substituir silenciosamente por outro modelo.
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    bol = db_session.execute(
        select(BoletimPeriodo).where(
            BoletimPeriodo.estudante_id == cenario["est1"].id,
            BoletimPeriodo.periodo_letivo == "1º Bimestre",
        )
    ).scalar_one()
    bol.idade = 16
    db_session.commit()

    _, token_a = _emitir_credencial_ml_simplificada(
        client,
        headers_admin,
        nome="Pipeline Artefato Ausente",
        escola_id=cenario["escola_a"].id,
        modelo_autorizado="regressao_logistica",
    )

    cfg = _config_para_testclient(service_token=token_a)
    pasta_vazia = tmp_path / "artifacts_vazios"
    pasta_vazia.mkdir()

    rel_sem_artefato = ExecutorPipelineML(
        cfg,
        http_client=client,
        diretorio_artefatos=pasta_vazia,
    ).executar(enviar=False)

    assert rel_sem_artefato.sucesso is False
    assert rel_sem_artefato.etapa_falha == "carregamento_modelo"
    assert rel_sem_artefato.modelo_nome == "regressao_logistica"
    assert "treinar_modelo_risco" in (rel_sem_artefato.erro or "")
    assert list(pasta_vazia.iterdir()) == []

    # Também interrompe se a saída do modelo for inválida
    monkeypatch.setattr(
        "app.integrations.prediction.modelo_risco.prever_risco",
        lambda *_a, **_kw: [
            SimpleNamespace(
                id_estudante=str(cenario["est1"].id),
                pontuacao_risco=2.5,
                faixa_risco="ALTO",
                versao_modelo="poc-risco-academico-uci-v1",
                data_processamento=datetime.now(timezone.utc),
            )
        ],
    )
    rel_invalido = ExecutorPipelineML(cfg, http_client=client).executar(
        enviar=False,
        registros_locais=[
            {
                "estudante_id": str(cenario["est1"].id),
                "escola_id": str(cenario["escola_a"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "idade": 16,
                "historico_reprovacoes": 0,
                "nota_t1": 7.0,
            }
        ],
        escola_id_local=cenario["escola_a"].id,
        modelo_nome_local="regressao_logistica",
    )
    assert rel_invalido.sucesso is False
    assert rel_invalido.etapa_falha == "inferencia"


# ==============================================================================
# 5. ENVIO COM TOKEN ÚNICO, VALIDAÇÕES DE ESCOLA/MODELO, CHUNKING E IDEMPOTÊNCIA
# ==============================================================================


def test_envio_validacoes_escola_modelo_revogacao_chunking_e_idempotencia(
    client: TestClient,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Valida envio unificado, rejeição de escola/modelo divergentes, revogação, 409 e chunking."""
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    cred_id_a, token_a = _emitir_credencial_ml_simplificada(
        client,
        headers_admin,
        nome="ML Unico Escola A",
        escola_id=cenario["escola_a"].id,
        modelo_autorizado="regressao_logistica",
    )

    descritor = obter_modelo_preditivo("regressao_logistica")
    assert descritor is not None

    agora = datetime.now(timezone.utc)
    item_valido = PrevisaoItemEnvio(
        estudante_id=cenario["est1"].id,
        escola_id=cenario["escola_a"].id,
        turma_id=cenario["turma_1a"].id,
        ano_letivo=2026,
        periodo_letivo="1º Bimestre",
        tipo_previsao="RISCO_ACADEMICO",
        pontuacao_risco=0.18,
        faixa_risco="BAIXO",
        modelo_nome=descritor.modelo_nome,
        modelo_versao=descritor.modelo_versao,
        gerado_em=agora,
        lote_externo_id="lote-unico-01",
        variaveis_utilizadas=["idade", "historico_reprovacoes", "nota_t1"],
    )

    # 1. Token ausente
    with pytest.raises(ErroEnvioAutenticacao, match="VERTICE_ML_SERVICE_TOKEN"):
        ClienteAPIPrevisoes(
            _config_para_testclient(service_token=None),
            http_client=client,
        ).enviar_previsoes([item_valido])

    # 2. Token inválido mascarado nos logs e exceções
    token_falso = "vtx_ml_TokenInvalidoTesteSeguranca99999999"
    with caplog.at_level(logging.INFO):
        with pytest.raises(ErroEnvioAutenticacao) as exc_401:
            ClienteAPIPrevisoes(
                _config_para_testclient(service_token=token_falso),
                http_client=client,
            ).enviar_previsoes([item_valido])
    assert token_falso not in str(exc_401.value)
    assert token_falso not in caplog.text

    # 3. Modelo não autorizado rejeitado (403)
    with pytest.raises(ErroEnvioAutorizacao):
        ClienteAPIPrevisoes(
            _config_para_testclient(service_token=token_a),
            http_client=client,
        ).enviar_previsoes([item_valido.model_copy(update={"modelo_nome": "outro_modelo"})])

    # 4. Versão divergente rejeitada (422)
    with pytest.raises(ErroEnvioValidacao, match="Versão de modelo"):
        ClienteAPIPrevisoes(
            _config_para_testclient(service_token=token_a),
            http_client=client,
        ).enviar_previsoes([item_valido.model_copy(update={"modelo_versao": "9.9.9"})])

    # 5. Estudante de outra escola rejeitado (403)
    item_outra_escola = item_valido.model_copy(
        update={
            "estudante_id": cenario["est_b1"].id,
            "escola_id": cenario["escola_b"].id,
            "turma_id": cenario["turma_escola_b"].id,
        }
    )
    with pytest.raises(ErroEnvioAutorizacao):
        ClienteAPIPrevisoes(
            _config_para_testclient(service_token=token_a),
            http_client=client,
        ).enviar_previsoes([item_outra_escola])

    # 6. Envio válido + Conflito de idempotência (409)
    res_ok = ClienteAPIPrevisoes(
        _config_para_testclient(service_token=token_a),
        http_client=client,
    ).enviar_previsoes([item_valido])
    assert res_ok.sucesso is True
    assert res_ok.total_recebido == 1

    with pytest.raises(ErroEnvioConflitoIdempotencia):
        ClienteAPIPrevisoes(
            _config_para_testclient(service_token=token_a),
            http_client=client,
        ).enviar_previsoes([item_valido])

    # 7. Revogação bloqueia envio imediatamente (403)
    assert (
        client.patch(
            f"/api/v1/previsoes/credenciais/{cred_id_a}/revogar",
            headers=headers_admin,
        ).status_code
        == 200
    )
    with pytest.raises(ErroEnvioAutorizacao, match="revogada"):
        ClienteAPIPrevisoes(
            _config_para_testclient(service_token=token_a),
            http_client=client,
        ).enviar_previsoes([item_valido.model_copy(update={"lote_externo_id": "lote-unico-02"})])

    # 8. Timeout + chunking > 2000
    def _mock_timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timeout simulado")

    with pytest.raises(ErroEnvioComunicacao, match="Timeout"):
        ClienteAPIPrevisoes(
            _config_para_testclient(service_token=token_a),
            http_client=httpx.Client(transport=httpx.MockTransport(_mock_timeout)),
        ).enviar_previsoes([item_valido])

    tamanhos_enviados: list[int] = []

    def _mock_chunk_parcial(request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content.decode("utf-8"))
        qtd = len(corpo["itens"])
        tamanhos_enviados.append(qtd)
        if len(tamanhos_enviados) == 1:
            return httpx.Response(201, json={"quantidade_recebida": qtd, "itens": []})
        return httpx.Response(422, json={"detail": "Falha no segundo sublote"})

    lote_grande = [
        item_valido.model_copy(update={"estudante_id": uuid.uuid4(), "lote_externo_id": None})
        for _ in range(2500)
    ]
    with pytest.raises(ErroEnvioValidacao) as exc_chunk:
        ClienteAPIPrevisoes(
            _config_para_testclient(service_token=token_a, batch_size=2000),
            http_client=httpx.Client(transport=httpx.MockTransport(_mock_chunk_parcial)),
        ).enviar_previsoes(lote_grande, lote_externo_id="lote-grande")
    assert tamanhos_enviados == [2000, 500]
    assert exc_chunk.value.lotes_enviados_antes_falha == 1


# ==============================================================================
# 6. AGENDAMENTO E CONCORRÊNCIA
# ==============================================================================


def test_agendador_habilitado_desabilitado_intervalo_e_concorrencia(tmp_path: Path) -> None:
    """Valida ativação/desativação, intervalo configurável e lock contra execuções simultâneas."""
    lock_path = tmp_path / "pipeline_test.lock"

    class _FakeExecutor:
        def executar(self, *, enviar: bool = False):  # type: ignore[no-untyped-def]
            from app.integrations.prediction.pipeline.executor import RelatorioExecucaoPipeline

            agora = datetime.now(timezone.utc)
            return RelatorioExecucaoPipeline(
                execucao_id="fake-01",
                modo="send" if enviar else "dry-run",
                sucesso=True,
                inicio_em=agora,
                fim_em=agora,
                duracao_ms=5.0,
                extraidos=3,
                validos=3,
                inferidos=3,
                enviados=3 if enviar else 0,
                persistidos=3 if enviar else 0,
                lotes_enviados=1 if enviar else 0,
            )

    cfg_desab = _config_para_testclient(
        service_token="vtx_ml_AgendadorTeste123456",
        scheduler_enabled=False,
        scheduler_interval_seconds=15,
        lock_file=lock_path,
    )
    ag_desab = AgendadorPipelineML(cfg_desab, executor_factory=lambda _c: _FakeExecutor())
    assert ag_desab.iniciar_loop(enviar=False, max_cycles=2) == []
    assert ag_desab.executar_ciclo(enviar=False, forcar=False).status == "DESABILITADO"

    intervalos_esperados: list[float] = []
    cfg_hab = _config_para_testclient(
        service_token="vtx_ml_AgendadorTeste123456",
        scheduler_enabled=True,
        scheduler_interval_seconds=45,
        lock_file=lock_path,
    )
    ag_hab = AgendadorPipelineML(cfg_hab, executor_factory=lambda _c: _FakeExecutor())
    historico = ag_hab.iniciar_loop(
        enviar=True,
        max_cycles=2,
        wait_fn=lambda seg: (intervalos_esperados.append(seg), False)[1],
    )
    assert len(historico) == 2
    assert intervalos_esperados == [45.0]

    evento_dentro = threading.Event()
    evento_liberar = threading.Event()
    resultados_concorrentes: list[str] = []

    class _ExecutorLento:
        def executar(self, *, enviar: bool = False):  # type: ignore[no-untyped-def]
            evento_dentro.set()
            evento_liberar.wait(timeout=3.0)
            return _FakeExecutor().executar(enviar=enviar)

    ag_c1 = AgendadorPipelineML(cfg_hab, executor_factory=lambda _c: _ExecutorLento())
    ag_c2 = AgendadorPipelineML(cfg_hab, executor_factory=lambda _c: _FakeExecutor())

    t1 = threading.Thread(
        target=lambda: resultados_concorrentes.append(ag_c1.executar_ciclo(enviar=True).status)
    )
    t1.start()
    assert evento_dentro.wait(timeout=2.0)

    status_segundo = ag_c2.executar_ciclo(enviar=True).status
    evento_liberar.set()
    t1.join(timeout=3.0)

    assert status_segundo == "IGNORADO_CONCORRENCIA"
    assert resultados_concorrentes == ["EXECUTADO_SUCESSO"]

    with BloqueioExecucaoSimultanea(lock_path):
        pass


# ==============================================================================
# 7. FLUXO PONTA A PONTA SIMPLIFICADO (TOKEN ÚNICO -> VISÃO GERAL) & CLI
# ==============================================================================


def test_integracao_simplificada_token_unico_ponta_a_ponta_e_visao_geral(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Comprova que, configurando APENAS `VERTICE_API_URL` e `VERTICE_ML_SERVICE_TOKEN`
    (sem `VERTICE_ML_SCHOOL_ID`, sem `VERTICE_ML_MODEL_NAME`, sem segunda chave):
    1. O pipeline descobre escola e modelo automaticamente.
    2. `--dry-run` executa inferência sem gravar previsões.
    3. `--send` persiste previsões para os estudantes da escola vinculada.
    4. `/api/v1/indicadores/gerais` e `visao_geral.py` exibem os resultados reais com filtros.
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")

    for est_key, idade_val in (("est1", 15), ("est2", 18), ("est3", 17), ("est4", 16)):
        bol = db_session.execute(
            select(BoletimPeriodo).where(
                BoletimPeriodo.estudante_id == cenario[est_key].id,
                BoletimPeriodo.periodo_letivo == "1º Bimestre",
            )
        ).scalar_one()
        bol.idade = idade_val
    db_session.commit()

    _, token_unico = _emitir_credencial_ml_simplificada(
        client,
        headers_admin,
        nome="Pipeline Unificado Escola A",
        escola_id=cenario["escola_a"].id,
        modelo_autorizado="regressao_logistica",
    )

    # Garante que nenhuma variável legada precisa estar no ambiente
    env_minimo = {
        "VERTICE_API_URL": "http://testserver",
        "VERTICE_ML_SERVICE_TOKEN": token_unico,
    }
    cfg = PipelineMLConfig.from_env(env=env_minimo)
    assert cfg.service_token == token_unico

    # 1. `--dry-run` não persiste nada e descobre escola/modelo automaticamente
    rel_dry = ExecutorPipelineML(cfg, http_client=client).executar(enviar=False)
    assert rel_dry.sucesso is True
    assert rel_dry.escola_id == str(cenario["escola_a"].id)
    assert rel_dry.modelo_nome == "regressao_logistica"
    assert rel_dry.modelo_versao == "poc-risco-academico-uci-v1"
    assert rel_dry.extraidos == 4
    assert rel_dry.inferidos == 4
    assert rel_dry.persistidos == 0
    assert db_session.query(PrevisaoRisco).count() == 0

    # 2. `--send` persiste usando o mesmo token único
    rel_send = ExecutorPipelineML(cfg, http_client=client).executar(enviar=True)
    assert rel_send.sucesso is True
    assert rel_send.escola_id == str(cenario["escola_a"].id)
    assert rel_send.modelo_nome == "regressao_logistica"
    assert rel_send.persistidos == 4

    persistidas = db_session.query(PrevisaoRisco).all()
    assert len(persistidas) == 4
    assert all(p.escola_id == cenario["escola_a"].id for p in persistidas)
    assert all(p.tipo_previsao == TipoPrevisao.RISCO_ACADEMICO for p in persistidas)

    # 3. `indicadores/gerais` e painel `Visão geral` refletem as previsões recebidas
    resp_ind = client.get("/api/v1/indicadores/gerais", headers=headers_gestor_a)
    assert resp_ind.status_code == 200
    ind = resp_ind.json()
    assert ind["possui_previsoes_risco"] is True
    assert ind["modelo_nome_vigente"] == "regressao_logistica"

    resp_ind_b2 = client.get(
        "/api/v1/indicadores/gerais",
        params={"periodo_letivo": "2º Bimestre"},
        headers=headers_gestor_a,
    )
    assert resp_ind_b2.status_code == 200
    assert resp_ind_b2.json()["possui_previsoes_risco"] is False

    st_mod = _preparar_frontend()
    registros_ui = _instrumentar_ui_stub(st_mod)

    import components.cards as cards_mod
    import components.graficos as graficos_mod
    import data.api_client as api_client
    import pages.visao_geral as pg_vg

    importlib.reload(cards_mod)
    importlib.reload(graficos_mod)
    importlib.reload(api_client)
    importlib.reload(pg_vg)
    api_client.configurar_cliente_http_teste(_adaptar_testclient_completo(client))

    try:
        assert api_client.autenticar_usuario_api("gestor.a@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        pg_vg.render()

        assert not [r for r in registros_ui if r["tipo"] == "error"]
        captions_ui = [str(r["mensagem"]) for r in registros_ui if r["tipo"] == "caption"]
        assert any("regressao_logistica" in cap for cap in captions_ui)
    finally:
        api_client.configurar_cliente_http_teste(None)
        st_mod.session_state.clear()


def test_cli_subprocesso_simplificado(tmp_path: Path) -> None:
    """Valida comandos reais `--check-model`, `--check-config` sem token, `--dry-run` e `agendador`."""
    env_limpo = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("VERTICE_ML_") and k not in {"VERTICE_API_URL"}
    }

    # 1. `--check-model` lista modelos disponíveis sem RuntimeWarning
    proc_modelo = subprocess.run(
        [sys.executable, "-m", "app.integrations.prediction.pipeline.executor", "--check-model"],
        cwd=str(BACKEND_DIR),
        env=env_limpo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_modelo.returncode == 0, proc_modelo.stderr
    assert "RuntimeWarning" not in proc_modelo.stderr
    dados_modelo = json.loads(proc_modelo.stdout)
    assert dados_modelo["status"] == "ok"
    assert dados_modelo["modelo_nome"] == "regressao_logistica"

    # 2. `--check-config` sem token falha claramente sem expor nada
    proc_cfg_sem = subprocess.run(
        [sys.executable, "-m", "app.integrations.prediction.pipeline.executor", "--check-config"],
        cwd=str(BACKEND_DIR),
        env=env_limpo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_cfg_sem.returncode == 2
    assert json.loads(proc_cfg_sem.stdout)["configuracao_valida"] is False

    # 3. `--dry-run --input-json` executa offline usando catálogo de modelos
    amostra_json = tmp_path / "amostra.json"
    amostra_json.write_text(
        json.dumps(
            [
                {
                    "estudante_id": str(uuid.uuid4()),
                    "escola_id": str(uuid.uuid4()),
                    "turma_id": str(uuid.uuid4()),
                    "ano_letivo": 2026,
                    "periodo_letivo": "1º Bimestre",
                    "idade": 16,
                    "historico_reprovacoes": 0,
                    "nota_t1": 7.5,
                }
            ]
        ),
        encoding="utf-8",
    )
    proc_dry = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.integrations.prediction.pipeline.executor",
            "--dry-run",
            "--input-json",
            str(amostra_json),
            "--json",
        ],
        cwd=str(BACKEND_DIR),
        env=env_limpo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_dry.returncode == 0, proc_dry.stderr
    rel_cli = json.loads(proc_dry.stdout)
    assert rel_cli["sucesso"] is True
    assert rel_cli["modelo_nome"] == "regressao_logistica"
    assert rel_cli["persistidos"] == 0

    # 4. Agendador desabilitado encerra limpo sem RuntimeWarning
    proc_ag = subprocess.run(
        [sys.executable, "-m", "app.integrations.prediction.pipeline.agendador"],
        cwd=str(BACKEND_DIR),
        env=env_limpo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_ag.returncode == 0, proc_ag.stderr
    assert "RuntimeWarning" not in proc_ag.stderr
