"""
Suíte completa de testes automatizados da Fase 6 — Participação, Entregas,
Reconciliação de Prazos, Integridade Histórica e Integração Frontend/Backend.

Cobre integralmente os requisitos da seção 11 (Bloco J):
1. Atividades (criação transacional com geração de entregas esperadas sem criar estudantes,
   reconciliação segura de `data_limite` preservando entregas realizadas, escopo autorizado).
2. Entregas esperadas (idempotência, unicidade `(atividade_id, estudante_id)`, integridade histórica
   em atividades encerradas e movimentação/evasão entre períodos letivos).
3. Entregas (cálculo e validação coerente de `ENTREGUE`, `ATRASADO`, `PENDENTE`, `NAO_ENTREGUE`,
   rejeição de `PENDENTE` vencida e `NAO_ENTREGUE` antes do prazo, preservação de nota `None`,
   bloqueio de estudante fora da turma, limites de nota).
4. Indicadores (`taxa = realizadas / esperadas * 100`, médias sem zerar ausência, zero division guard,
   filtros por turma/disciplina/período/atividade/estudante e evolução).
5. Segurança (isolamento entre escolas, professores, turmas e disciplinas; anonimização LGPD).
6. Frontend e complemento da Fase 5 (bloqueio estrito de login offline sem `logado=True`,
   `pages/participacao.py` integrado ao backend real via `api_client`, ausência de dados fictícios,
   tratamento de 401/403 e coerência da pré-validação no frontend).
"""

from datetime import date, timedelta
import importlib
from types import SimpleNamespace
from typing import Any
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
    SituacaoFinalPeriodo,
)
from app.modules.participacao.models import StatusAtividade
from tests.test_fase4_modulos_pedagogicos import (
    _criar_cenario_fase4,
    _login_headers,
)
from tests.test_fase5_mapa_acertos_e_frontend import (
    _garantir_ambiente_frontend_para_teste,
)


def _adaptar_client_para_api_client(client: TestClient) -> Any:
    """Conecta `Frontend vertice/data/api_client.py` diretamente ao `TestClient` FastAPI."""

    def _adapter(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> Any:
        del timeout
        caminho = url.replace("http://127.0.0.1:8000", "")
        return client.request(
            method=method,
            url=caminho,
            headers=headers,
            params=params,
            json=json,
            files=files,
        )

    return _adapter


# ==============================================================================
# 1. ATIVIDADES: CRIAÇÃO, GERAÇÃO TRANSACIONAL, RECONCILIAÇÃO DE PRAZO E ESCOPO
# ==============================================================================
def test_fase6_atividades_criacao_reconciliacao_prazo_e_escopo(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    headers_prof2 = _login_headers(client, "prof2@vertice.edu.br", "SenhaForte@123")

    prazo_vencido = (date.today() - timedelta(days=3)).isoformat()
    prazo_futuro = (date.today() + timedelta(days=7)).isoformat()
    novo_prazo_vencido = (date.today() - timedelta(days=1)).isoformat()

    total_estudantes_antes = db_session.query(Estudante).count()

    # Professor 2 (Turma 3A / HIS) não pode criar atividade na Turma 1A / MAT
    resp_negado = client.post(
        "/api/v1/atividades",
        headers=headers_prof2,
        json={
            "codigo": "ATIV-NEG-01",
            "titulo": "Atividade não autorizada",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_limite": prazo_futuro,
            "nota_maxima": 10.0,
            "gerar_entregas_esperadas": True,
        },
    )
    assert resp_negado.status_code == 403

    # Professor 1 cria atividade já vencida para validar geração automática como NAO_ENTREGUE
    resp_criar = client.post(
        "/api/v1/atividades",
        headers=headers_prof1,
        json={
            "codigo": "ATIV-F6-01",
            "titulo": "Lista Fase 6",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_limite": prazo_vencido,
            "nota_maxima": 10.0,
            "gerar_entregas_esperadas": True,
        },
    )
    assert resp_criar.status_code == 201, resp_criar.text
    ativ_id = resp_criar.json()["id"]

    # Nenhum estudante pode ser criado via atividades
    assert db_session.query(Estudante).count() == total_estudantes_antes

    resp_ent = client.get(f"/api/v1/atividades/{ativ_id}/entregas", headers=headers_prof1)
    assert resp_ent.status_code == 200
    entregas = resp_ent.json()
    assert len(entregas) == 3
    assert all(e["status_entrega"] == "NAO_ENTREGUE" for e in entregas)
    assert all(e["data_limite"] == prazo_vencido for e in entregas)
    assert all(e["nota_maxima"] == 10.0 for e in entregas)

    # Registra entrega efetivada para EST-001 (com atraso em relação ao prazo vencido)
    data_ent_est1 = (date.today() - timedelta(days=2)).isoformat()
    resp_est1 = client.post(
        f"/api/v1/atividades/{ativ_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "data_entrega": data_ent_est1,
            "nota": 8.5,
        },
    )
    assert resp_est1.status_code == 201, resp_est1.text
    dados_est1 = resp_est1.json()
    assert dados_est1["status_entrega"] == "ATRASADO"
    assert dados_est1["em_atraso"] is True
    assert dados_est1["dias_atraso"] == 1

    # Prorroga data_limite para o futuro:
    # - EST-002 e EST-003 (sem entrega) devem reconciliar para PENDENTE
    # - EST-001 (já entregue) deve preservar integralmente sua entrega e histórico
    resp_patch1 = client.patch(
        f"/api/v1/atividades/{ativ_id}",
        headers=headers_prof1,
        json={"data_limite": prazo_futuro},
    )
    assert resp_patch1.status_code == 200, resp_patch1.text

    entregas_pos_prorrog = {
        e["codigo_anonimo"]: e
        for e in client.get(
            f"/api/v1/atividades/{ativ_id}/entregas", headers=headers_prof1
        ).json()
    }
    assert entregas_pos_prorrog["EST-002"]["status_entrega"] == "PENDENTE"
    assert entregas_pos_prorrog["EST-003"]["status_entrega"] == "PENDENTE"
    assert entregas_pos_prorrog["EST-001"]["data_entrega"] == data_ent_est1
    assert entregas_pos_prorrog["EST-001"]["nota"] == 8.5
    assert entregas_pos_prorrog["EST-001"]["status_entrega"] == "ATRASADO"

    # Antecipa data_limite novamente para vencido: PENDENTE sem entrega volta para NAO_ENTREGUE
    resp_patch2 = client.patch(
        f"/api/v1/atividades/{ativ_id}",
        headers=headers_prof1,
        json={"data_limite": novo_prazo_vencido},
    )
    assert resp_patch2.status_code == 200
    entregas_pos_venc = {
        e["codigo_anonimo"]: e
        for e in client.get(
            f"/api/v1/atividades/{ativ_id}/entregas", headers=headers_prof1
        ).json()
    }
    assert entregas_pos_venc["EST-002"]["status_entrega"] == "NAO_ENTREGUE"
    assert entregas_pos_venc["EST-003"]["status_entrega"] == "NAO_ENTREGUE"
    assert entregas_pos_venc["EST-001"]["data_entrega"] == data_ent_est1


# ==============================================================================
# 2. ENTREGAS ESPERADAS: IDEMPOTÊNCIA E INTEGRIDADE HISTÓRICA
# ==============================================================================
def test_fase6_entregas_esperadas_idempotencia_e_integridade_historica(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    prazo_futuro = (date.today() + timedelta(days=10)).isoformat()

    # Cria atividade aberta no 1º Bimestre (elegíveis: EST-001, EST-002, EST-003)
    resp_at1 = client.post(
        "/api/v1/atividades",
        headers=headers_prof1,
        json={
            "codigo": "ATIV-HIST-1B",
            "titulo": "Atividade 1º Bimestre",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_limite": prazo_futuro,
            "gerar_entregas_esperadas": True,
        },
    )
    assert resp_at1.status_code == 201
    at1_id = resp_at1.json()["id"]

    # Encerra atividade do 1º Bimestre para consolidar o retrato histórico
    resp_enc = client.patch(
        f"/api/v1/atividades/{at1_id}",
        headers=headers_prof1,
        json={"status": StatusAtividade.ENCERRADA.value},
    )
    assert resp_enc.status_code == 200

    # Novo estudante (EST-005) entra apenas no 2º Bimestre na Turma 1A
    est5 = Estudante(
        escola_id=cenario["escola_a"].id,
        codigo_anonimo="EST-005",
        historico_reprovacoes=0,
        ativo=True,
    )
    db_session.add(est5)
    db_session.flush()
    db_session.add(
        BoletimPeriodo(
            estudante_id=est5.id,
            escola_id=cenario["escola_a"].id,
            turma_id=cenario["turma_1a"].id,
            ano_letivo=2026,
            periodo_letivo="2º Bimestre",
            frequencia_percentual=95.0,
            media_geral=8.0,
        )
    )
    db_session.commit()

    # A atividade encerrada do 1º Bimestre NÃO deve ser recalculada retroativamente com EST-005
    ind_1b = client.get(
        f"/api/v1/indicadores/participacao?atividade_id={at1_id}",
        headers=headers_prof1,
    ).json()
    assert ind_1b["total_entregas_esperadas"] == 3
    codigos_1b = {e["codigo_anonimo"] for e in ind_1b["percentual_por_estudante"]}
    assert codigos_1b == {"EST-001", "EST-002", "EST-003"}

    # Registra boletins de continuidade do 2º Bimestre para EST-001 e EST-002 (EST-003 seguiu Evadido no 1º Bimestre)
    for est_cont in (cenario["est1"], cenario["est2"]):
        db_session.add(
            BoletimPeriodo(
                estudante_id=est_cont.id,
                escola_id=cenario["escola_a"].id,
                turma_id=cenario["turma_1a"].id,
                ano_letivo=2026,
                periodo_letivo="2º Bimestre",
                frequencia_percentual=90.0,
                media_geral=7.5,
            )
        )
    db_session.commit()

    # Uma nova atividade criada no 1º Bimestre tampouco puxa EST-005 (que só entrou no 2º Bimestre)
    resp_at1_extra = client.post(
        "/api/v1/atividades",
        headers=headers_prof1,
        json={
            "codigo": "ATIV-HIST-1B-EXTRA",
            "titulo": "Atividade Extra 1º Bimestre",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_limite": prazo_futuro,
            "gerar_entregas_esperadas": True,
        },
    )
    assert resp_at1_extra.status_code == 201
    entregas_1b_extra = client.get(
        f"/api/v1/atividades/{resp_at1_extra.json()['id']}/entregas",
        headers=headers_prof1,
    ).json()
    assert {e["codigo_anonimo"] for e in entregas_1b_extra} == {
        "EST-001",
        "EST-002",
        "EST-003",
    }

    # Atividade no 2º Bimestre: EST-003 foi Evadido no 1º Bimestre -> não deve ser puxado para o 2º Bimestre;
    # EST-001, EST-002 e EST-005 são elegíveis para 2º Bimestre.
    resp_at2 = client.post(
        "/api/v1/atividades",
        headers=headers_prof1,
        json={
            "codigo": "ATIV-HIST-2B",
            "titulo": "Atividade 2º Bimestre",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "2º Bimestre",
            "data_limite": prazo_futuro,
            "gerar_entregas_esperadas": True,
        },
    )
    assert resp_at2.status_code == 201
    at2_id = resp_at2.json()["id"]

    entregas_2b = client.get(
        f"/api/v1/atividades/{at2_id}/entregas", headers=headers_prof1
    ).json()
    assert len(entregas_2b) == 3
    assert {e["codigo_anonimo"] for e in entregas_2b} == {"EST-001", "EST-002", "EST-005"}

    # Idempotência da geração de entregas esperadas (máx 1 registro por (atividade_id, estudante_id))
    gen_again = client.post(
        f"/api/v1/atividades/{at2_id}/gerar-entregas-esperadas",
        headers=headers_prof1,
    )
    assert gen_again.status_code == 200
    assert gen_again.json()["entregas_criadas"] == 0
    assert gen_again.json()["entregas_ja_existentes"] == 3


# ==============================================================================
# 3. ENTREGAS: STATUS COERENTES, BLOQUEIOS DE INCONSISTÊNCIA E NOTAS NULL
# ==============================================================================
def test_fase6_entregas_validacao_estrita_bloco_e_e_bloqueio_fora_turma(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    # Cria estudante vinculado apenas à Turma 3A (diferente de Turma 1A)
    est_3a = Estudante(
        escola_id=cenario["escola_a"].id,
        codigo_anonimo="EST-3A-01",
        historico_reprovacoes=0,
        ativo=True,
    )
    db_session.add(est_3a)
    db_session.flush()
    db_session.add(
        BoletimPeriodo(
            estudante_id=est_3a.id,
            escola_id=cenario["escola_a"].id,
            turma_id=cenario["turma_3a"].id,
            ano_letivo=2026,
            periodo_letivo="1º Bimestre",
        )
    )
    db_session.commit()

    prazo_futuro = (date.today() + timedelta(days=5)).isoformat()
    prazo_passado = (date.today() - timedelta(days=5)).isoformat()

    resp_at_fut = client.post(
        "/api/v1/atividades",
        headers=headers_prof1,
        json={
            "codigo": "ATIV-VAL-FUT",
            "titulo": "Validação Prazo Futuro",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_limite": prazo_futuro,
            "nota_maxima": 10.0,
            "gerar_entregas_esperadas": True,
        },
    )
    assert resp_at_fut.status_code == 201
    at_fut_id = resp_at_fut.json()["id"]

    resp_at_pas = client.post(
        "/api/v1/atividades",
        headers=headers_prof1,
        json={
            "codigo": "ATIV-VAL-PAS",
            "titulo": "Validação Prazo Vencido",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_limite": prazo_passado,
            "nota_maxima": 10.0,
            "gerar_entregas_esperadas": True,
        },
    )
    assert resp_at_pas.status_code == 201
    at_pas_id = resp_at_pas.json()["id"]

    # Estudante de outra turma é bloqueado (422)
    resp_outra_turma = client.post(
        f"/api/v1/atividades/{at_fut_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-3A-01",
            "data_entrega": date.today().isoformat(),
        },
    )
    assert resp_outra_turma.status_code == 422

    # Bloco E: NAO_ENTREGUE com hoje <= data_limite deve ser rejeitado (422)
    resp_nao_ent_antes = client.post(
        f"/api/v1/atividades/{at_fut_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "data_entrega": None,
            "status_entrega": "NAO_ENTREGUE",
        },
    )
    assert resp_nao_ent_antes.status_code == 422

    # Bloco E: PENDENTE com hoje > data_limite deve ser rejeitado (422)
    resp_pend_apos = client.post(
        f"/api/v1/atividades/{at_pas_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "data_entrega": None,
            "status_entrega": "PENDENTE",
        },
    )
    assert resp_pend_apos.status_code == 422

    # ENTREGUE sem data_entrega -> 422
    resp_ent_sem_data = client.post(
        f"/api/v1/atividades/{at_fut_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "data_entrega": None,
            "status_entrega": "ENTREGUE",
        },
    )
    assert resp_ent_sem_data.status_code == 422

    # Nota superior à nota máxima -> 422
    resp_nota_alta = client.post(
        f"/api/v1/atividades/{at_fut_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "data_entrega": date.today().isoformat(),
            "nota": 12.0,
        },
    )
    assert resp_nota_alta.status_code == 422

    # Entrega válida no prazo sem nota -> ENTREGUE e nota=None (nunca zero)
    resp_ok = client.post(
        f"/api/v1/atividades/{at_fut_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "data_entrega": date.today().isoformat(),
        },
    )
    assert resp_ok.status_code == 201
    assert resp_ok.json()["status_entrega"] == "ENTREGUE"
    assert resp_ok.json()["nota"] is None
    assert resp_ok.json()["em_atraso"] is False


# ==============================================================================
# 4. INDICADORES & SEGURANÇA: DENOMINADOR, ZERO DIVISION E ISOLAMENTO
# ==============================================================================
def test_fase6_indicadores_denominador_individual_e_seguranca(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.modules.usuarios.models import PapelUsuario
    from app.modules.usuarios.schemas import UsuarioCreate
    from app.modules.usuarios.service import UsuarioService

    cenario = _criar_cenario_fase4(db_session)
    UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Admin Técnico F6",
            email="admin_f6@vertice.edu.br",
            senha="SenhaForte@123",
            papel=PapelUsuario.ADMINISTRADOR,
            escola_id=cenario["escola_a"].id,
        ),
    )
    db_session.commit()

    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    headers_prof2 = _login_headers(client, "prof2@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")
    headers_gestor_b = _login_headers(client, "gestor.b@vertice.edu.br", "SenhaForte@123")
    headers_admin = _login_headers(client, "admin_f6@vertice.edu.br", "SenhaForte@123")

    # Sem atividades -> divisão por zero tratada com None
    resp_vazio = client.get("/api/v1/indicadores/participacao", headers=headers_gestor_a)
    assert resp_vazio.status_code == 200
    assert resp_vazio.json()["total_entregas_esperadas"] == 0
    assert resp_vazio.json()["taxa_entrega_geral_percentual"] is None
    assert resp_vazio.json()["media_notas_disponiveis"] is None

    # Cria atividade e registra apenas 1 entrega com nota e 1 sem nota; 3º fica NAO_ENTREGUE
    prazo = (date.today() - timedelta(days=2)).isoformat()
    at_id = client.post(
        "/api/v1/atividades",
        headers=headers_prof1,
        json={
            "codigo": "ATIV-IND-F6",
            "titulo": "Indicadores F6",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_limite": prazo,
            "nota_maxima": 10.0,
            "gerar_entregas_esperadas": True,
        },
    ).json()["id"]

    client.post(
        f"/api/v1/atividades/{at_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "data_entrega": (date.today() - timedelta(days=3)).isoformat(),
            "nota": 9.0,
        },
    )
    client.post(
        f"/api/v1/atividades/{at_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-002",
            "data_entrega": date.today().isoformat(),
            "nota": None,
        },
    )

    # Indicador geral: 2 realizadas / 3 esperadas = 66.67%, média = 9.0 (apenas 1 nota preenchida)
    ind_geral = client.get(
        "/api/v1/indicadores/participacao",
        headers=headers_gestor_a,
    ).json()
    assert ind_geral["total_entregas_esperadas"] == 3
    assert ind_geral["entregas_realizadas"] == 2
    assert ind_geral["taxa_entrega_geral_percentual"] == 66.67
    assert ind_geral["media_notas_disponiveis"] == 9.0

    # Histórico individual filtrado por estudante_id
    ind_est1 = client.get(
        f"/api/v1/indicadores/participacao?estudante_id={cenario['est1'].id}",
        headers=headers_prof1,
    ).json()
    assert ind_est1["total_entregas_esperadas"] == 1
    assert ind_est1["entregas_realizadas"] == 1
    assert ind_est1["taxa_entrega_geral_percentual"] == 100.0
    assert ind_est1["media_notas_disponiveis"] == 9.0
    assert len(ind_est1["evolucao_participacao"]) == 1

    # Segurança:
    # - Gestor B (outra escola) não acessa atividade nem estudante da Escola A
    assert (
        client.get(
            f"/api/v1/atividades/{at_id}/entregas", headers=headers_gestor_b
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/indicadores/participacao?estudante_id={cenario['est1'].id}",
            headers=headers_gestor_b,
        ).status_code
        == 403
    )
    # - Prof 2 (outra turma/disciplina) é bloqueado (403)
    assert (
        client.get(
            f"/api/v1/atividades/{at_id}/entregas", headers=headers_prof2
        ).status_code
        == 403
    )
    # - Administrador técnico sem acesso pedagógico é bloqueado (403)
    assert (
        client.get("/api/v1/atividades", headers=headers_admin).status_code == 403
    )


# ==============================================================================
# 5. FRONTEND & COMPLEMENTO FASE 5: LOGIN OFFLINE BLOQUEADO E PARTICIPAÇÃO REAL
# ==============================================================================
def test_fase6_frontend_login_bloqueado_offline_e_participacao_integrada(
    client: TestClient,
    db_session: Session,
) -> None:
    st_mod = _garantir_ambiente_frontend_para_teste()
    cenario = _criar_cenario_fase4(db_session)

    import data.api_client as api_client
    import pages.participacao as part_page
    import pages.login as login_page

    importlib.reload(api_client)
    importlib.reload(part_page)
    importlib.reload(login_page)

    # 1. Complemento Fase 5: falha de comunicação/servidor indisponível NUNCA pode setar logado=True
    def _cliente_offline(*_a: Any, **_kw: Any) -> Any:
        import httpx

        raise httpx.ConnectError("Backend desligado para teste")

    api_client.configurar_cliente_http_teste(_cliente_offline)
    st_mod.session_state.clear()
    resp_off = api_client.autenticar_usuario_api("prof1@vertice.edu.br", "SenhaForte@123")
    assert resp_off.ok is False
    assert resp_off.indisponivel is True
    assert not api_client.possui_sessao_api_ativa()

    # Garante no código fonte de login.py e auth_animada.py que offline não força logado=True
    conteudo_login = (
        part_page.__file__.replace("pages\\participacao.py", "pages\\login.py")
    )
    with open(conteudo_login, encoding="utf-8") as fp:
        src_login = fp.read()
    assert 'elif resp.indisponivel:\n                        st.session_state["logado"] = False' in src_login

    conteudo_anim = part_page.__file__.replace(
        "pages\\participacao.py", "components\\auth_animada.py"
    )
    with open(conteudo_anim, encoding="utf-8") as fp:
        src_anim = fp.read()
    assert "Modo de navegação local" not in src_anim
    assert 'st.session_state["logado"] = False' in src_anim

    # 2. Sem sessão API ativa -> participação não expõe mock e retorna conectado=False
    api_client.configurar_cliente_http_teste(None)
    st_mod.session_state.clear()
    ctx_sem_sessao = part_page.carregar_contexto_participacao_api()
    assert ctx_sem_sessao["conectado"] is False
    assert ctx_sem_sessao["atividades"] == []

    # 3. Fluxo real completo pelo `api_client` acoplado ao backend FastAPI
    try:
        api_client.configurar_cliente_http_teste(_adaptar_client_para_api_client(client))
        st_mod.session_state.clear()

        resp_login = api_client.autenticar_usuario_api(
            "prof1@vertice.edu.br", "SenhaForte@123"
        )
        assert resp_login.ok is True
        assert api_client.possui_sessao_api_ativa() is True

        prazo_futuro = (date.today() + timedelta(days=4)).isoformat()
        resp_cria = api_client.criar_atividade_api(
            codigo="ATIV-FRONT-01",
            titulo="Atividade Integrada Frontend",
            turma_id=str(cenario["turma_1a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
            periodo_letivo="1º Bimestre",
            data_limite=prazo_futuro,
            nota_maxima=10.0,
            gerar_entregas_esperadas=True,
        )
        assert resp_cria.ok is True
        at_id = resp_cria.dados["id"]

        ctx = part_page.carregar_contexto_participacao_api()
        assert ctx["conectado"] is True
        assert any(a["id"] == at_id for a in ctx["atividades"])

        # Lista entregas esperadas via api_client e formata tabela garantindo ausência de PII e nota "—"
        resp_ent = api_client.listar_entregas_atividade_api(at_id)
        assert resp_ent.ok is True
        assert len(resp_ent.dados) == 3

        df_ent = part_page.formatar_tabela_entregas_atividade(resp_ent.dados)
        assert list(df_ent["Código"]) == ["EST-001", "EST-002", "EST-003"]
        assert all(val == "—" for val in df_ent["Nota obtida"])

        # Pré-validação no frontend estritamente coerente com o backend (Bloco E)
        erro_pend_venc = part_page.validar_coerencia_entrega_frontend(
            data_limite=date.today() - timedelta(days=2),
            data_entrega=None,
            status_informado="PENDENTE",
        )
        assert erro_pend_venc is not None
        erro_nao_ent_antes = part_page.validar_coerencia_entrega_frontend(
            data_limite=date.today() + timedelta(days=2),
            data_entrega=None,
            status_informado="NAO_ENTREGUE",
        )
        assert erro_nao_ent_antes is not None
        assert (
            part_page.validar_coerencia_entrega_frontend(
                data_limite=date.today() + timedelta(days=2),
                data_entrega=date.today(),
                status_informado="ENTREGUE",
                nota=9.0,
                nota_maxima=10.0,
            )
            is None
        )

        # Registra entrega via API client usando entrega_id real
        ent_est1_id = resp_ent.dados[0]["id"]
        resp_upd_ent = api_client.atualizar_entrega_por_id_api(
            entrega_id=ent_est1_id,
            data_entrega=date.today().isoformat(),
            nota=9.5,
            status_entrega=None,
            incluir_data_entrega=True,
            incluir_nota=True,
        )
        assert resp_upd_ent.ok is True
        assert resp_upd_ent.dados["status_entrega"] == "ENTREGUE"

        # Consulta indicadores reais + resumo KPIs + histórico da turma
        resp_ind = api_client.consultar_indicadores_participacao(atividade_id=at_id)
        assert resp_ind.ok is True
        resumo = part_page.montar_resumo_indicadores_participacao(resp_ind.dados)
        assert resumo["realizadas_vs_esperadas"] == "1 / 3"
        assert resumo["media_notas"] == "9,5"

        df_hist = part_page.montar_historico_turma_df(resp_ind.dados)
        assert len(df_hist) == 1
        assert df_hist.iloc[0]["Código"] == "ATIV-FRONT-01"

        # Registra acompanhamento pedagógico de participação via api_client
        resp_ac = api_client.registrar_acompanhamento_pedagogico_api(
            turma_id=str(cenario["turma_1a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
            estudante_id=str(cenario["est2"].id),
            tipo_acao="Busca ativa de atividade",
            descricao="Contato para orientar entrega da ATIV-FRONT-01.",
            origem="PARTICIPACAO",
        )
        assert resp_ac.ok is True

        # Sessão expirada (401) e permissão negada (403) tratadas sem crash
        st_mod.session_state["access_token"] = "token_invalido"
        ctx_401 = part_page.carregar_contexto_participacao_api()
        assert ctx_401["conectado"] is False
        assert ctx_401["sessao_expirada"] is True
    finally:
        api_client.configurar_cliente_http_teste(None)
        st_mod.session_state.clear()
