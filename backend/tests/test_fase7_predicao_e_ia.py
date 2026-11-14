"""
Suíte completa de testes automatizados da Fase 7 — Integração Preditiva e Assistente IA.

Cobre integralmente:
1. Credenciais técnicas dedicadas de serviço ML (emissão admin, rejeição de JWT comum, revogação).
2. Persistência append-only, ingestão unitária e em lote atômico com rollback, validação e idempotência.
3. Disponibilização de previsões (individual, histórica, agregada com política explícita de versão única),
   integração com `/indicadores/gerais`, comportamento sem previsões e isolamento rigoroso de escopo.
4. Prevenção estrita de Data Leakage (`situacao_final`, pós-desfecho, PII, catálogo oficial e regras extensíveis).
5. Camada de contexto estruturado do Assistente IA (`ESCOLA`, `TURMA`, `INDIVIDUAL`), reutilização de
   serviços reais, interface LLM desacoplada sem simulação (`503`), isolamento RBAC e auditoria persistente
   de tentativas autorizadas e negadas.
6. Integração real do frontend (`api_client.py`, `visao_geral.py`, `estudantes.py`, `assistente_ia.py`)
   acoplado ao `TestClient`, incluindo estado sem previsões e indisponibilidade.
"""

from datetime import datetime, timedelta, timezone
import importlib
from types import SimpleNamespace
from typing import Any
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.assistant.models import (
    AuditoriaConsultaIA,
    ResultadoAutorizacaoIA,
)
from app.integrations.prediction.leakage import validar_variaveis_contra_leakage
from app.integrations.prediction.models import PrevisaoRisco
from tests.test_fase4_modulos_pedagogicos import (
    _criar_cenario_fase4,
    _login_headers,
)
from tests.test_fase5_mapa_acertos_e_frontend import (
    _garantir_ambiente_frontend_para_teste,
)
from tests.test_fase6_participacao import _adaptar_client_para_api_client


def _emitir_credencial_ml(
    client: TestClient,
    headers_admin: dict[str, str],
    *,
    nome: str = "Pipeline ML Vértice",
    escola_id: str | None = None,
    modelos_permitidos: list[str] | None = None,
    expira_em: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"nome": nome}
    if escola_id is not None:
        payload["escola_id"] = escola_id
    if modelos_permitidos is not None:
        payload["modelos_permitidos"] = modelos_permitidos
    if expira_em is not None:
        payload["expira_em"] = expira_em

    resp = client.post(
        "/api/v1/previsoes/credenciais",
        headers=headers_admin,
        json=payload,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ==============================================================================
# 1. CREDENCIAIS DE SERVIÇO E CONTROLE DE ACESSO NA INGESTÃO
# ==============================================================================
def test_fase7_credenciais_servico_e_bloqueio_tokens_comuns(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(
        client, "gestor.a@vertice.edu.br", "SenhaForte@123"
    )
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    # Apenas Administrador cria credenciais técnicas
    assert (
        client.post(
            "/api/v1/previsoes/credenciais",
            headers=headers_gestor_a,
            json={"nome": "Credencial Invasora"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/previsoes/credenciais",
            headers=headers_prof1,
            json={"nome": "Credencial Prof"},
        ).status_code
        == 403
    )

    cred_a = _emitir_credencial_ml(
        client,
        headers_admin,
        nome="ML Escola A",
        escola_id=str(cenario["escola_a"].id),
        modelos_permitidos=["vertice_evasao_xgb"],
    )
    assert cred_a["chave_secreta"].startswith("vtx_ml_")
    assert cred_a["ativo"] is True

    # Listagem nunca volta a expor a chave secreta
    resp_list = client.get("/api/v1/previsoes/credenciais", headers=headers_admin)
    assert resp_list.status_code == 200
    itens_cred = resp_list.json()
    assert len(itens_cred) == 1
    assert "chave_secreta" not in itens_cred[0]
    assert itens_cred[0]["prefixo_chave"] == cred_a["prefixo_chave"]

    payload_valido = {
        "estudante_id": str(cenario["est1"].id),
        "turma_id": str(cenario["turma_1a"].id),
        "ano_letivo": 2026,
        "periodo_letivo": "1º Bimestre",
        "tipo_previsao": "EVASAO",
        "pontuacao_risco": 0.72,
        "faixa_risco": "ALTO",
        "politica_classificacao_versao": "pol-v1",
        "modelo_nome": "vertice_evasao_xgb",
        "modelo_versao": "1.0.0",
        "gerado_em": "2026-04-10T10:00:00Z",
    }

    # Sem credencial -> 401
    assert client.post("/api/v1/previsoes", json=payload_valido).status_code == 401

    # Tokens comuns de professor, gestor ou admin NÃO autorizam ingestão -> 403
    for hdr_comum in (headers_prof1, headers_gestor_a, headers_admin):
        resp_jwt = client.post(
            "/api/v1/previsoes",
            headers=hdr_comum,
            json=payload_valido,
        )
        assert resp_jwt.status_code == 403

    # Credencial restrita à Escola A não pode enviar previsão da Escola B
    payload_escola_b = {
        **payload_valido,
        "estudante_id": str(cenario["est_b1"].id),
        "turma_id": str(cenario["turma_escola_b"].id),
    }
    resp_cross_school = client.post(
        "/api/v1/previsoes",
        headers={"X-Service-Token": cred_a["chave_secreta"]},
        json=payload_escola_b,
    )
    assert resp_cross_school.status_code == 403

    # Modelo não permitido pela credencial -> 403
    resp_modelo = client.post(
        "/api/v1/previsoes",
        headers={"X-Service-Token": cred_a["chave_secreta"]},
        json={**payload_valido, "modelo_nome": "outro_modelo_nao_autorizado"},
    )
    assert resp_modelo.status_code == 403

    # Envio autorizado com credencial válida -> 201
    resp_ok = client.post(
        "/api/v1/previsoes",
        headers={"X-Service-Token": cred_a["chave_secreta"]},
        json=payload_valido,
    )
    assert resp_ok.status_code == 201, resp_ok.text

    # Revogação impede reutilização imediata -> 403
    resp_rev = client.patch(
        f"/api/v1/previsoes/credenciais/{cred_a['id']}/revogar",
        headers=headers_admin,
    )
    assert resp_rev.status_code == 200
    assert resp_rev.json()["ativo"] is False

    resp_apos_rev = client.post(
        "/api/v1/previsoes",
        headers={"X-Service-Token": cred_a["chave_secreta"]},
        json={**payload_valido, "gerado_em": "2026-04-11T10:00:00Z"},
    )
    assert resp_apos_rev.status_code == 403

    # Credencial expirada também é bloqueada -> 403
    cred_exp = _emitir_credencial_ml(
        client,
        headers_admin,
        nome="Credencial Expirada",
        expira_em=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    )
    resp_exp = client.post(
        "/api/v1/previsoes",
        headers={"X-Service-Token": cred_exp["chave_secreta"]},
        json={**payload_valido, "gerado_em": "2026-04-12T10:00:00Z"},
    )
    assert resp_exp.status_code == 403


# ==============================================================================
# 2. LOTE ATÔMICO, ROLLBACK, IDEMPOTÊNCIA E HISTÓRICO APPEND-ONLY
# ==============================================================================
def test_fase7_lote_atomico_rollback_idempotencia_e_append_only(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    cred = _emitir_credencial_ml(client, headers_admin, nome="ML Global Batch")
    svc_headers = {"X-Service-Token": cred["chave_secreta"]}

    # 1) Lote com 1 item inválido (estudante inexistente) deve sofrer rollback completo
    lote_falho = {
        "lote_externo_id": "lote-falho-01",
        "itens": [
            {
                "estudante_id": str(cenario["est1"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.15,
                "faixa_risco": "BAIXO",
                "modelo_nome": "modelo_risco_escolar",
                "modelo_versao": "1.0.0",
                "gerado_em": "2026-05-01T08:00:00Z",
            },
            {
                "estudante_id": str(uuid.uuid4()),  # inexistente -> aborta todo o lote
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.91,
                "faixa_risco": "CRITICO",
                "modelo_nome": "modelo_risco_escolar",
                "modelo_versao": "1.0.0",
                "gerado_em": "2026-05-01T08:00:00Z",
            },
        ],
    }
    resp_falha = client.post("/api/v1/previsoes/lote", headers=svc_headers, json=lote_falho)
    assert resp_falha.status_code == 404
    assert db_session.execute(select(PrevisaoRisco)).scalars().all() == []

    # 2) Validação de limites de pontuação e faixa controlada
    resp_score_bad = client.post(
        "/api/v1/previsoes",
        headers=svc_headers,
        json={
            "estudante_id": str(cenario["est1"].id),
            "ano_letivo": 2026,
            "periodo_letivo": "1º Bimestre",
            "tipo_previsao": "EVASAO",
            "pontuacao_risco": 1.25,
            "faixa_risco": "ALTO",
            "modelo_nome": "modelo_risco_escolar",
            "modelo_versao": "1.0.0",
            "gerado_em": "2026-05-01T08:00:00Z",
        },
    )
    assert resp_score_bad.status_code == 422

    # 3) Ingestão em lote válida por `codigo_anonimo` + `escola_id` e `estudante_id`
    lote_v1 = {
        "lote_externo_id": "lote-v1-20260501",
        "itens": [
            {
                "codigo_anonimo": "EST-001",
                "escola_id": str(cenario["escola_a"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.18,
                "faixa_risco": "BAIXO",
                "modelo_nome": "modelo_risco_escolar",
                "modelo_versao": "1.0.0",
                "gerado_em": "2026-05-01T08:00:00Z",
                "variaveis_utilizadas": ["frequencia_percentual", "faltas", "media_geral"],
            },
            {
                "estudante_id": str(cenario["est2"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.87,
                "faixa_risco": "CRITICO",
                "modelo_nome": "modelo_risco_escolar",
                "modelo_versao": "1.0.0",
                "gerado_em": "2026-05-01T08:00:00Z",
            },
        ],
    }
    resp_ok = client.post("/api/v1/previsoes/lote", headers=svc_headers, json=lote_v1)
    assert resp_ok.status_code == 201, resp_ok.text
    assert resp_ok.json()["quantidade_recebida"] == 2

    # 4) Reenvio idêntico deve ser bloqueado por idempotência (409)
    resp_dup = client.post("/api/v1/previsoes/lote", headers=svc_headers, json=lote_v1)
    assert resp_dup.status_code == 409

    # 5) Nova execução com nova versão / timestamp é adicionada em append-only sem sobrescrever
    resp_v2 = client.post(
        "/api/v1/previsoes",
        headers=svc_headers,
        json={
            "estudante_id": str(cenario["est1"].id),
            "turma_id": str(cenario["turma_1a"].id),
            "ano_letivo": 2026,
            "periodo_letivo": "1º Bimestre",
            "tipo_previsao": "EVASAO",
            "pontuacao_risco": 0.44,
            "faixa_risco": "MODERADO",
            "modelo_nome": "modelo_risco_escolar",
            "modelo_versao": "2.0.0",
            "gerado_em": "2026-05-15T12:00:00Z",
        },
    )
    assert resp_v2.status_code == 201

    todos = db_session.execute(
        select(PrevisaoRisco).where(PrevisaoRisco.estudante_id == cenario["est1"].id)
    ).scalars().all()
    assert len(todos) == 2
    assert {r.modelo_versao for r in todos} == {"1.0.0", "2.0.0"}


# ==============================================================================
# 3. PREVENÇÃO ESTRITA DE DATA LEAKAGE E LGPD
# ==============================================================================
def test_fase7_prevencao_data_leakage_e_regras_extensiveis(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor = _login_headers(
        client, "gestor.a@vertice.edu.br", "SenhaForte@123"
    )
    cred = _emitir_credencial_ml(client, headers_admin, nome="ML Leakage Guard")
    svc_headers = {"X-Service-Token": cred["chave_secreta"]}

    # Catálogo oficial disponível via API
    resp_cat = client.get("/api/v1/previsoes/contrato-variaveis", headers=headers_gestor)
    assert resp_cat.status_code == 200
    dados_cat = resp_cat.json()
    assert dados_cat["politica_anti_leakage_ativa"] is True
    assert "situacao_final" in dados_cat["campos_proibidos_base"]
    nomes_elegiveis = {v["nome"] for v in dados_cat["variaveis_elegiveis"]}
    assert {"frequencia_percentual", "faltas", "media_geral", "taxa_entrega_atividades"} <= nomes_elegiveis

    # Bloqueio de `situacao_final`, derivadas e PII no recebimento de previsão
    base_prev = {
        "estudante_id": str(cenario["est1"].id),
        "turma_id": str(cenario["turma_1a"].id),
        "ano_letivo": 2026,
        "periodo_letivo": "1º Bimestre",
        "tipo_previsao": "EVASAO",
        "pontuacao_risco": 0.55,
        "faixa_risco": "MODERADO",
        "modelo_nome": "modelo_leakage_check",
        "modelo_versao": "1.0.0",
        "gerado_em": "2026-05-05T10:00:00Z",
    }

    resp_leak_1 = client.post(
        "/api/v1/previsoes",
        headers=svc_headers,
        json={**base_prev, "variaveis_utilizadas": ["frequencia_percentual", "situacao_final"]},
    )
    assert resp_leak_1.status_code == 422
    assert "situacao_final" in resp_leak_1.json()["detail"]

    resp_leak_2 = client.post(
        "/api/v1/previsoes",
        headers=svc_headers,
        json={
            **base_prev,
            "metadados_tecnicos": {"features": {"evadiu": False, "cpf": "00000000000"}},
        },
    )
    assert resp_leak_2.status_code == 422

    # Inspeção preventiva com lista limpa vs extensão dinâmica
    resp_val_ok = client.post(
        "/api/v1/previsoes/validar-variaveis",
        headers=headers_gestor,
        json={"variaveis": ["frequencia_percentual", "taxa_entrega_atividades"]},
    )
    assert resp_val_ok.status_code == 200
    assert resp_val_ok.json()["valido"] is True

    resp_val_ext = client.post(
        "/api/v1/previsoes/validar-variaveis",
        headers=headers_gestor,
        json={
            "variaveis": ["frequencia_percentual", "nota_conselho_final_ano"],
            "campos_proibidos_extras": ["nota_conselho_final_ano"],
        },
    )
    assert resp_val_ext.status_code == 200
    res_ext = resp_val_ext.json()
    assert res_ext["valido"] is False
    assert "nota_conselho_final_ano" in res_ext["variaveis_proibidas_detectadas"]

    # Validador Python diretamente também permite regras adicionais extensíveis
    res_py = validar_variaveis_contra_leakage(
        {"frequencia_percentual": 88.0, "campo_futuro": 1},
        campos_proibidos_extras={"campo_futuro": "Disponível apenas após encerramento anual."},
        lancar_excecao=False,
    )
    assert res_py.valido is False


# ==============================================================================
# 4. DISPONIBILIZAÇÃO, VERSÃO ÚNICA, INDICADORES GERAIS E ISOLAMENTO DE ESCOPO
# ==============================================================================
def test_fase7_disponibilizacao_escopo_versao_unica_e_indicadores_gerais(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(
        client, "gestor.a@vertice.edu.br", "SenhaForte@123"
    )
    headers_gestor_b = _login_headers(
        client, "gestor.b@vertice.edu.br", "SenhaForte@123"
    )
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    headers_prof2 = _login_headers(client, "prof2@vertice.edu.br", "SenhaForte@123")

    # Sem previsões registradas ainda -> comportamento honesto (sem dados falsos)
    resp_ind_vazio = client.get("/api/v1/indicadores/gerais", headers=headers_gestor_a)
    assert resp_ind_vazio.status_code == 200
    ind_vazio = resp_ind_vazio.json()
    assert ind_vazio["possui_previsoes_risco"] is False
    assert ind_vazio["distribuicao_faixas_risco"] == []

    cred = _emitir_credencial_ml(client, headers_admin, nome="ML Multi Versao")
    svc_headers = {"X-Service-Token": cred["chave_secreta"]}

    # Versão v1 para est1 (BAIXO) e est2 (ALTO) na Turma 1A, est4 (CRITICO) na Turma 3A, est_b1 na Escola B
    # + Versão v2 mais recente APENAS para est1 (MODERADO) e est2 (BAIXO)
    lote = {
        "lote_externo_id": "lote-politica-versao",
        "itens": [
            {
                "estudante_id": str(cenario["est1"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.12,
                "faixa_risco": "BAIXO",
                "modelo_nome": "modelo_vtx",
                "modelo_versao": "1.0.0",
                "gerado_em": "2026-06-01T10:00:00Z",
            },
            {
                "estudante_id": str(cenario["est2"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.78,
                "faixa_risco": "ALTO",
                "modelo_nome": "modelo_vtx",
                "modelo_versao": "1.0.0",
                "gerado_em": "2026-06-01T10:00:00Z",
            },
            {
                "estudante_id": str(cenario["est4"].id),
                "turma_id": str(cenario["turma_3a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.92,
                "faixa_risco": "CRITICO",
                "modelo_nome": "modelo_vtx",
                "modelo_versao": "1.0.0",
                "gerado_em": "2026-06-01T10:00:00Z",
            },
            {
                "estudante_id": str(cenario["est_b1"].id),
                "turma_id": str(cenario["turma_escola_b"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.88,
                "faixa_risco": "CRITICO",
                "modelo_nome": "modelo_vtx",
                "modelo_versao": "1.0.0",
                "gerado_em": "2026-06-01T10:00:00Z",
            },
            # v2 mais recente para est1 e est2 na Turma 1A
            {
                "estudante_id": str(cenario["est1"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.45,
                "faixa_risco": "MODERADO",
                "modelo_nome": "modelo_vtx",
                "modelo_versao": "2.0.0",
                "gerado_em": "2026-06-15T10:00:00Z",
            },
            {
                "estudante_id": str(cenario["est2"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.21,
                "faixa_risco": "BAIXO",
                "modelo_nome": "modelo_vtx",
                "modelo_versao": "2.0.0",
                "gerado_em": "2026-06-15T10:00:00Z",
            },
        ],
    }
    assert client.post("/api/v1/previsoes/lote", headers=svc_headers, json=lote).status_code == 201

    # Administrador NÃO acessa rotas pedagógicas de previsões -> 403
    assert client.get("/api/v1/previsoes", headers=headers_admin).status_code == 403
    assert client.get("/api/v1/previsoes/resumo", headers=headers_admin).status_code == 403
    assert (
        client.get(
            f"/api/v1/previsoes/estudantes/{cenario['est1'].id}",
            headers=headers_admin,
        ).status_code
        == 403
    )

    # Gestor A em /indicadores/gerais sem `modelo_versao`: seleciona automaticamente v2.0.0 (mais recente),
    # sem misturar com v1.0.0 -> est1 (MODERADO) + est2 (BAIXO) = 2 estudantes
    resp_ind_a = client.get("/api/v1/indicadores/gerais", headers=headers_gestor_a)
    assert resp_ind_a.status_code == 200
    ind_a = resp_ind_a.json()
    assert ind_a["possui_previsoes_risco"] is True
    assert ind_a["modelo_versao_vigente"] == "2.0.0"
    mapa_faixas_v2 = {f["faixa"]: f["quantidade"] for f in ind_a["distribuicao_faixas_risco"]}
    assert mapa_faixas_v2 == {"BAIXO": 1, "MODERADO": 1, "ALTO": 0, "CRITICO": 0}

    # Filtrando explicitamente `modelo_versao=1.0.0`: Gestor A vê v1.0.0 de toda a Escola A (est1, est2, est4)
    resp_ind_a_v1 = client.get(
        "/api/v1/indicadores/gerais",
        headers=headers_gestor_a,
        params={"modelo_versao": "1.0.0"},
    )
    assert resp_ind_a_v1.status_code == 200
    ind_a_v1 = resp_ind_a_v1.json()
    assert ind_a_v1["modelo_versao_vigente"] == "1.0.0"
    mapa_faixas_v1 = {f["faixa"]: f["quantidade"] for f in ind_a_v1["distribuicao_faixas_risco"]}
    assert mapa_faixas_v1 == {"BAIXO": 1, "MODERADO": 0, "ALTO": 1, "CRITICO": 1}

    # Histórico individual de est1 mostra v2.0.0 mais recente seguida de v1.0.0
    resp_hist_1 = client.get(
        f"/api/v1/previsoes/estudantes/{cenario['est1'].id}",
        headers=headers_prof1,
    )
    assert resp_hist_1.status_code == 200
    hist_1 = resp_hist_1.json()
    assert hist_1["codigo_anonimo"] == "EST-001"
    assert hist_1["total_previsoes"] == 2
    assert hist_1["previsao_mais_recente"]["modelo_versao"] == "2.0.0"

    # Isolamento de professor e escola:
    # Prof1 não acessa est4 (Turma 3A, Prof2) nem est_b1 (Escola B)
    assert (
        client.get(
            f"/api/v1/previsoes/estudantes/{cenario['est4'].id}",
            headers=headers_prof1,
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/previsoes/estudantes/{cenario['est_b1'].id}",
            headers=headers_prof1,
        ).status_code
        == 403
    )
    # Prof2 não vê previsões da Turma 1A em /previsoes
    lista_prof2 = client.get("/api/v1/previsoes", headers=headers_prof2).json()
    assert all(p["estudante_id"] == str(cenario["est4"].id) for p in lista_prof2)
    # Gestor B vê somente est_b1 da Escola B e é bloqueado ao filtrar Escola A
    lista_gb = client.get("/api/v1/previsoes", headers=headers_gestor_b).json()
    assert len(lista_gb) == 1 and lista_gb[0]["codigo_anonimo"] == "EST-B01"
    assert (
        client.get(
            "/api/v1/previsoes",
            headers=headers_gestor_b,
            params={"escola_id": str(cenario["escola_a"].id)},
        ).status_code
        == 403
    )


# ==============================================================================
# 5. ASSISTENTE IA: CONTEXTO, REUSO DE SERVIÇOS, RBAC E AUDITORIA PERSISTENTE
# ==============================================================================
def test_fase7_assistente_contexto_autorizacao_reuso_e_auditoria(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(
        client, "gestor.a@vertice.edu.br", "SenhaForte@123"
    )
    headers_gestor_b = _login_headers(
        client, "gestor.b@vertice.edu.br", "SenhaForte@123"
    )
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    cred = _emitir_credencial_ml(client, headers_admin, nome="ML Contexto IA")
    assert (
        client.post(
            "/api/v1/previsoes",
            headers={"X-Service-Token": cred["chave_secreta"]},
            json={
                "estudante_id": str(cenario["est1"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "tipo_previsao": "EVASAO",
                "pontuacao_risco": 0.35,
                "faixa_risco": "MODERADO",
                "modelo_nome": "modelo_ia_ctx",
                "modelo_versao": "1.0.0",
                "gerado_em": "2026-06-20T10:00:00Z",
            },
        ).status_code
        == 201
    )

    # 1) Status sem LLM real conectado (nunca simula)
    resp_status = client.get("/api/v1/assistente/status", headers=headers_gestor_a)
    assert resp_status.status_code == 200
    st_json = resp_status.json()
    assert st_json["provedor_llm_configurado"] is False
    assert st_json["auditoria_ativa"] is True

    # Consulta LLM controlada retorna 503 explícito após auditar contexto autorizado
    resp_503 = client.post(
        "/api/v1/assistente/consultar",
        headers=headers_gestor_a,
        json={
            "tipo_contexto": "ESCOLA",
            "pergunta_usuario": "Quais turmas exigem atenção prioritária?",
        },
    )
    assert resp_503.status_code == 503

    # 2) Níveis ESCOLA, TURMA e INDIVIDUAL reutilizando os mesmos valores dos endpoints reais
    ind_direto = client.get("/api/v1/indicadores/gerais", headers=headers_gestor_a).json()
    ctx_escola = client.post(
        "/api/v1/assistente/contexto",
        headers=headers_gestor_a,
        json={"tipo_contexto": "ESCOLA"},
    )
    assert ctx_escola.status_code == 200, ctx_escola.text
    dados_ctx_esc = ctx_escola.json()
    assert (
        dados_ctx_esc["indicadores_gerais"]["total_estudantes_distintos"]
        == ind_direto["total_estudantes_distintos"]
    )
    assert (
        dados_ctx_esc["indicadores_gerais"]["frequencia_media"]
        == ind_direto["frequencia_media"]
    )
    assert dados_ctx_esc["resumo_previsoes_risco"]["possui_previsoes"] is True
    assert "IndicadoresGeraisService" in dados_ctx_esc["metadados"]["fontes_utilizadas"]

    ctx_turma = client.post(
        "/api/v1/assistente/contexto",
        headers=headers_prof1,
        json={
            "tipo_contexto": "TURMA",
            "turma_id": str(cenario["turma_1a"].id),
        },
    )
    assert ctx_turma.status_code == 200, ctx_turma.text
    assert ctx_turma.json()["metadados"]["turma_id"] == str(cenario["turma_1a"].id)

    ctx_ind = client.post(
        "/api/v1/assistente/contexto",
        headers=headers_prof1,
        json={
            "tipo_contexto": "INDIVIDUAL",
            "estudante_id": str(cenario["est1"].id),
        },
    )
    assert ctx_ind.status_code == 200, ctx_ind.text
    dados_ctx_ind = ctx_ind.json()
    assert dados_ctx_ind["estudante_historico"]["codigo_anonimo"] == "EST-001"
    assert dados_ctx_ind["previsoes_estudante"]["total_previsoes"] == 1
    assert "cpf" not in str(dados_ctx_ind).lower()
    assert "nome_completo" not in str(dados_ctx_ind).lower()

    # 3) Tentativas NÃO AUTORIZADAS retornam 403 e DEVEM ser auditadas como NEGADO
    # Admin tentando contexto escolar
    assert (
        client.post(
            "/api/v1/assistente/contexto",
            headers=headers_admin,
            json={"tipo_contexto": "ESCOLA", "escola_id": str(cenario["escola_a"].id)},
        ).status_code
        == 403
    )
    # Gestor B tentando turma da Escola A
    assert (
        client.post(
            "/api/v1/assistente/contexto",
            headers=headers_gestor_b,
            json={"tipo_contexto": "TURMA", "turma_id": str(cenario["turma_1a"].id)},
        ).status_code
        == 403
    )
    # Prof1 tentando estudante da Turma 3A (Prof2)
    assert (
        client.post(
            "/api/v1/assistente/contexto",
            headers=headers_prof1,
            json={"tipo_contexto": "INDIVIDUAL", "estudante_id": str(cenario["est4"].id)},
        ).status_code
        == 403
    )
    # Alvo inexistente não pode falhar FK na auditoria -> 404 + registro NEGADO
    assert (
        client.post(
            "/api/v1/assistente/contexto",
            headers=headers_gestor_a,
            json={"tipo_contexto": "TURMA", "turma_id": str(uuid.uuid4())},
        ).status_code
        == 404
    )

    auditorias = db_session.execute(select(AuditoriaConsultaIA)).scalars().all()
    autorizados = [
        a for a in auditorias if a.resultado_autorizacao == ResultadoAutorizacaoIA.AUTORIZADO
    ]
    negados = [
        a for a in auditorias if a.resultado_autorizacao == ResultadoAutorizacaoIA.NEGADO
    ]
    assert len(autorizados) >= 4
    assert len(negados) == 4

    # Consulta de auditoria via API respeita escopo
    resp_aud_admin = client.get("/api/v1/assistente/auditoria", headers=headers_admin)
    assert resp_aud_admin.status_code == 200
    assert len(resp_aud_admin.json()) == len(auditorias)


# ==============================================================================
# 6. INTEGRAÇÃO DO FRONTEND (`api_client`, `visao_geral`, `estudantes`, `assistente_ia`)
# ==============================================================================
def test_fase7_integracao_frontend_com_backend_e_estado_sem_previsoes(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")

    _garantir_ambiente_frontend_para_teste()
    import streamlit as st
    import data.api_client as api_client
    import pages.assistente_ia as pg_assistente
    import pages.estudantes as pg_estudantes
    import pages.visao_geral as pg_visao_geral

    importlib.reload(api_client)
    importlib.reload(pg_visao_geral)
    importlib.reload(pg_estudantes)
    importlib.reload(pg_assistente)

    st.session_state.clear()

    # 1) Offline / indisponibilidade explícita sem simular dados
    def _offline(*_args: Any, **_kwargs: Any) -> Any:
        import httpx

        raise httpx.ConnectError("API offline")

    api_client.configurar_cliente_http_teste(_offline)
    st.session_state["access_token"] = "token-sessao-para-teste-offline"
    resp_off = api_client.consultar_status_assistente_api()
    assert resp_off.ok is False and resp_off.indisponivel is True
    st.session_state.clear()

    # 2) Conectado ao backend real com TestClient (primeiro SEM previsões cadastradas)
    api_client.configurar_cliente_http_teste(_adaptar_client_para_api_client(client))
    try:
        assert api_client.autenticar_usuario_api(
            "gestor.a@vertice.edu.br", "SenhaForte@123"
        ).ok

        resp_ind_vazio = api_client.consultar_indicadores_gerais_api()
        assert resp_ind_vazio.ok is True
        dados_vazio = resp_ind_vazio.dados

        kpis_vazios = pg_visao_geral.montar_kpis_visao_geral(dados_vazio)
        assert kpis_vazios[3][0] == "Sem previsões"
        possui_r0, df_r0, nota_r0 = pg_visao_geral.preparar_dados_risco_visao_geral(dados_vazio)
        assert possui_r0 is False and df_r0.empty and nota_r0 is not None

        # 3) Após ingerir previsão real, frontend passa a exibir risco + modelo/versão reais
        cred = _emitir_credencial_ml(client, headers_admin, nome="ML Frontend Test")
        assert (
            client.post(
                "/api/v1/previsoes",
                headers={"X-Service-Token": cred["chave_secreta"]},
                json={
                    "estudante_id": str(cenario["est2"].id),
                    "turma_id": str(cenario["turma_1a"].id),
                    "ano_letivo": 2026,
                    "periodo_letivo": "1º Bimestre",
                    "tipo_previsao": "EVASAO",
                    "pontuacao_risco": 0.91,
                    "faixa_risco": "CRITICO",
                    "modelo_nome": "xgb_frontend",
                    "modelo_versao": "1.2.0",
                    "gerado_em": "2026-07-01T09:30:00Z",
                },
            ).status_code
            == 201
        )

        resp_ind_real = api_client.consultar_indicadores_gerais_api()
        assert resp_ind_real.ok is True
        dados_reais = resp_ind_real.dados
        kpis_reais = pg_visao_geral.montar_kpis_visao_geral(dados_reais)
        assert kpis_reais[3][0] == "1"
        assert "xgb_frontend" in kpis_reais[3][2]
        possui_r1, df_r1, nota_r1 = pg_visao_geral.preparar_dados_risco_visao_geral(dados_reais)
        assert possui_r1 is True and not df_r1.empty
        assert "xgb_frontend" in str(nota_r1) and "1.2.0" in str(nota_r1)

        # Estudantes + Previsões reais sem PII
        resp_ests = api_client.listar_estudantes_api()
        resp_prevs = api_client.listar_previsoes_api()
        assert resp_ests.ok and resp_prevs.ok
        df_ests = pg_estudantes.montar_tabela_estudantes_com_risco(
            resp_ests.dados, resp_prevs.dados
        )
        assert not df_ests.empty
        linha_est2 = df_ests[df_ests["Código anonimizado"] == "EST-002"].iloc[0]
        linha_est1 = df_ests[df_ests["Código anonimizado"] == "EST-001"].iloc[0]
        assert linha_est2["Faixa preditiva"] == "Crítico"
        assert linha_est1["Faixa preditiva"] == "Sem previsão"

        # Assistente IA: status e montagem real de contexto via api_client
        resp_st = api_client.consultar_status_assistente_api()
        assert resp_st.ok and resp_st.dados["provedor_llm_configurado"] is False
        resp_ctx = api_client.construir_contexto_assistente_api(
            tipo_contexto="INDIVIDUAL",
            estudante_id=str(cenario["est2"].id),
        )
        assert resp_ctx.ok is True
        resumo_ui = pg_assistente.montar_resumo_contexto_ui(resp_ctx.dados)
        assert resumo_ui["codigo_anonimo"] == "EST-002"
        assert resumo_ui["possui_previsoes_risco"] is True
        assert resumo_ui["auditoria_id"] is not None
    finally:
        api_client.configurar_cliente_http_teste(None)
        st.session_state.clear()
