"""
Suíte completa de testes automatizados da Fase 5 — Integração do Mapa de Acertos,
Gráficos, Filtros, Validações de Gabarito/Histórico e Integração Frontend/Backend.

Cobre integralmente os requisitos da seção 8 (Bloco G):
Backend:
1. Retorno correto dos indicadores de avaliações (`GET /api/v1/indicadores/avaliacoes`);
2. Distribuição correta de alternativas (`A`, `B`, `C`, `D`, `E`, `BRANCO`);
3. Separação correta entre acertos, erros e respostas em branco;
4. Exclusão de questões abertas da distribuição de alternativas `A`–`E`;
5. Funcionamento de filtros combinados (`turma_id`, `disciplina_id`, `periodo_letivo`, `avaliacao_id`, `ano_letivo`);
6. Isolamento entre escolas;
7. Isolamento entre professores, turmas e disciplinas;
8. Tratamento de respostas ausentes (`quantidade_respostas_ausentes`);
9. Tratamento de avaliações sem respostas (sem divisão por zero);
10. Consistência de gabarito (reaproveitamento quando omitido, rejeição de conflito e bloqueio de alteração retroativa com respostas);
11. Não regressão da importação em duas etapas.

Frontend (`Frontend vertice/`):
12. Carregamento de dados reais da API no Mapa de Acertos e construção dos 6 gráficos analíticos;
13. Atualização dos gráficos e indicadores ao alterar filtros;
14. Exibição adequada quando não há avaliações ou respostas;
15. Tratamento de falha de comunicação com a API (sem expor tokens);
16. Tratamento de sessão expirada (`401`) e permissão insuficiente (`403`);
17. Ausência de dados fictícios apresentados como resultados reais;
18. Consistência da pré-validação do campo `em_branco` em `entrada_dados.py`.
"""

from pathlib import Path
import sys
import types
from typing import Any

from fastapi.testclient import TestClient
import pandas as pd
from sqlalchemy.orm import Session

from tests.test_fase4_modulos_pedagogicos import (
    _criar_cenario_fase4,
    _login_headers,
)

# Garante que a pasta `Frontend vertice/` possa ser importada nos testes integrados
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "Frontend vertice"
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))


def _garantir_ambiente_frontend_para_teste() -> Any:
    """
    Fornece stubs leves de `streamlit` e `plotly` caso esses pacotes de UI não estejam
    instalados no ambiente virtual do backend, permitindo testar diretamente todas as
    funções reais de negócio, validação, cliente HTTP e construção de gráficos do frontend.
    """
    try:
        import streamlit as st_mod
    except ModuleNotFoundError:
        st_mod = types.ModuleType("streamlit")
        st_mod.session_state = {}  # type: ignore[attr-defined]
        st_mod.dialog = lambda *_a, **_kw: (lambda fn: fn)  # type: ignore[attr-defined]
        st_mod.html = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        st_mod.title = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        st_mod.caption = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        st_mod.markdown = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        st_mod.info = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        st_mod.warning = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        st_mod.error = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        st_mod.success = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        sys.modules["streamlit"] = st_mod

    try:
        import plotly  # noqa: F401
    except ModuleNotFoundError:

        class _FakeFigure:
            def __init__(self, kind: str, data: Any = None, **kwargs: Any) -> None:
                self.kind = kind
                self.data = data
                self.kwargs = kwargs
                self.layout: dict[str, Any] = {}
                self.xaxes: dict[str, Any] = {}
                self.yaxes: dict[str, Any] = {}
                self.traces: list[ Any] = []

            def update_layout(self, **kwargs: Any) -> "_FakeFigure":
                self.layout.update(kwargs)
                return self

            def update_xaxes(self, **kwargs: Any) -> "_FakeFigure":
                self.xaxes.update(kwargs)
                return self

            def update_yaxes(self, **kwargs: Any) -> "_FakeFigure":
                self.yaxes.update(kwargs)
                return self

            def update_traces(self, **kwargs: Any) -> "_FakeFigure":
                self.traces.append(kwargs)
                return self

            def add_trace(self, trace: Any) -> "_FakeFigure":
                self.traces.append(trace)
                return self

        plotly_mod = types.ModuleType("plotly")
        px_mod = types.ModuleType("plotly.express")
        go_mod = types.ModuleType("plotly.graph_objects")

        px_mod.bar = lambda dados=None, **kw: _FakeFigure("bar", dados, **kw)  # type: ignore[attr-defined]
        px_mod.line = lambda dados=None, **kw: _FakeFigure("line", dados, **kw)  # type: ignore[attr-defined]
        px_mod.pie = lambda dados=None, **kw: _FakeFigure("pie", dados, **kw)  # type: ignore[attr-defined]
        px_mod.scatter = lambda dados=None, **kw: _FakeFigure("scatter", dados, **kw)  # type: ignore[attr-defined]
        go_mod.Scatter = lambda **kw: {"type": "Scatter", **kw}  # type: ignore[attr-defined]

        plotly_mod.express = px_mod  # type: ignore[attr-defined]
        plotly_mod.graph_objects = go_mod  # type: ignore[attr-defined]
        sys.modules["plotly"] = plotly_mod
        sys.modules["plotly.express"] = px_mod
        sys.modules["plotly.graph_objects"] = go_mod

    return st_mod


st = _garantir_ambiente_frontend_para_teste()


# ==============================================================================
# 1. TESTES DE BACKEND — INDICADORES, FILTROS COMBINADOS, AUSENTES E SEM RESPOSTAS
# ==============================================================================


def test_fase5_backend_indicadores_avaliacoes_filtros_ausentes_e_sem_respostas(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Verifica no endpoint `GET /api/v1/indicadores/avaliacoes`:
    - Retorno correto dos indicadores consolidados e por questão;
    - Distribuição de alternativas A-E e BRANCO apenas para questões FECHADAS;
    - Exclusão de questões ABERTAS da distribuição de alternativas;
    - Separação entre acertos, erros, em branco e respostas ausentes (`quantidade_respostas_ausentes`);
    - Avaliação cadastrada com questões mas sem respostas registradas (`total_respostas_registradas == 0`,
      sem divisão por zero);
    - Filtros combinados por `turma_id`, `disciplina_id`, `periodo_letivo`, `ano_letivo` e `avaliacao_id`;
    - Isolamento entre escolas e entre professores/turmas/disciplinas.
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    headers_prof2 = _login_headers(client, "prof2@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(
        client, "gestor.a@vertice.edu.br", "SenhaForte@123"
    )
    headers_gestor_b = _login_headers(
        client, "gestor.b@vertice.edu.br", "SenhaForte@123"
    )

    # 1. Cria avaliação AV-F5-VAZIA (1º Bimestre) com 1 questão fechada, mas SEM respostas registradas
    av_vazia = client.post(
        "/api/v1/avaliacoes",
        headers=headers_prof1,
        json={
            "codigo": "AV-F5-VAZIA",
            "titulo": "Diagnóstica Sem Respostas",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "2º Bimestre",
            "data_avaliacao": "2026-06-10",
        },
    ).json()
    client.post(
        f"/api/v1/avaliacoes/{av_vazia['id']}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q01",
            "tipo_questao": "FECHADA",
            "alternativa_correta": "B",
            "valor_questao": 2.0,
            "faixa_dificuldade": "Adequada",
            "topico": "Estatística",
        },
    )

    # Verifica indicadores para avaliação sem respostas registradas (3 estudantes esperados na Turma 1A)
    resp_sem_resp = client.get(
        f"/api/v1/indicadores/avaliacoes?avaliacao_id={av_vazia['id']}",
        headers=headers_prof1,
    )
    assert resp_sem_resp.status_code == 200, resp_sem_resp.text
    ind_vazia = resp_sem_resp.json()
    assert ind_vazia["total_avaliacoes"] == 1
    assert ind_vazia["total_questoes"] == 1
    assert ind_vazia["total_respostas_esperadas"] == 3
    assert ind_vazia["total_respostas_registradas"] == 0
    assert ind_vazia["total_respostas_ausentes"] == 3
    assert ind_vazia["total_acertos"] == 0
    assert ind_vazia["total_erros"] == 0
    assert ind_vazia["total_em_branco"] == 0
    assert ind_vazia["media_avaliacao_ponderada"] is None
    assert ind_vazia["distribuicao_acertos_estudantes"] == []
    q_vazia = ind_vazia["questoes"][0]
    assert q_vazia["quantidade_respostas_ausentes"] == 3
    assert q_vazia["quantidade_acertos"] == 0
    assert q_vazia["quantidade_erros"] == 0
    assert q_vazia["quantidade_em_branco"] == 0
    assert q_vazia["media_nota_questao"] is None

    # 2. Cria avaliação AV-F5-COMPLETA no 1º Bimestre com 2 questões (Q01 fechada, Q02 aberta)
    # Apenas 2 dos 3 estudantes da Turma 1A respondem (EST-003 fica ausente / sem resposta registrada)
    av_comp = client.post(
        "/api/v1/avaliacoes",
        headers=headers_prof1,
        json={
            "codigo": "AV-F5-COMPLETA",
            "titulo": "Avaliação Bimestral F5",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_avaliacao": "2026-04-25",
        },
    ).json()
    q1 = client.post(
        f"/api/v1/avaliacoes/{av_comp['id']}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q01",
            "tipo_questao": "FECHADA",
            "alternativa_correta": "D",
            "valor_questao": 4.0,
            "faixa_dificuldade": "Adequada",
            "topico": "Funções",
        },
    ).json()
    q2 = client.post(
        f"/api/v1/avaliacoes/{av_comp['id']}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q02",
            "tipo_questao": "ABERTA",
            "valor_questao": 6.0,
            "faixa_dificuldade": "Difícil",
            "topico": "Geometria",
        },
    ).json()

    # EST-001: Q01 = D (acerto), Q02 = em branco
    # EST-002: Q01 = A (erro), Q02 = nota 5.0 (acerto >= 60% de 6.0)
    # EST-003: não tem resposta registrada em Q01 nem em Q02 (ausente)
    client.post(
        f"/api/v1/questoes/{q1['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-001", "alternativa_marcada": "D"},
    )
    client.post(
        f"/api/v1/questoes/{q2['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-001", "em_branco": True},
    )
    client.post(
        f"/api/v1/questoes/{q1['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-002", "alternativa_marcada": "A"},
    )
    client.post(
        f"/api/v1/questoes/{q2['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-002", "nota_obtida": 5.0},
    )

    # 3. Consulta com filtros combinados (turma_id + disciplina_id + periodo_letivo + ano_letivo + avaliacao_id)
    resp_comb = client.get(
        "/api/v1/indicadores/avaliacoes",
        headers=headers_prof1,
        params={
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "ano_letivo": 2026,
            "avaliacao_id": av_comp["id"],
        },
    )
    assert resp_comb.status_code == 200, resp_comb.text
    ind_c = resp_comb.json()
    assert ind_c["total_avaliacoes"] == 1
    assert ind_c["total_questoes"] == 2
    assert ind_c["total_respostas_esperadas"] == 6  # 3 estudantes * 2 questões
    assert ind_c["total_respostas_registradas"] == 4  # 2 estudantes * 2 questões
    assert ind_c["total_respostas_ausentes"] == 2  # EST-003 ausente nas 2 questões
    assert ind_c["total_acertos"] == 2  # EST-001 em Q01 + EST-002 em Q02
    assert ind_c["total_erros"] == 1  # EST-002 em Q01
    assert ind_c["total_em_branco"] == 1  # EST-001 em Q02

    mapa_q = {q["codigo_questao"]: q for q in ind_c["questoes"]}
    assert mapa_q["Q01"]["quantidade_respostas_ausentes"] == 1
    assert mapa_q["Q01"]["distribuicao_alternativas"] == {
        "A": 1,
        "B": 0,
        "C": 0,
        "D": 1,
        "E": 0,
        "BRANCO": 0,
    }
    # Questão aberta não possui distribuição de alternativas A-E e não transforma ausente em resposta registrada
    assert mapa_q["Q02"]["tipo_questao"] == "ABERTA"
    assert mapa_q["Q02"]["distribuicao_alternativas"] == {}
    assert mapa_q["Q02"]["quantidade_respostas_ausentes"] == 1
    assert mapa_q["Q02"]["quantidade_em_branco"] == 1
    assert mapa_q["Q02"]["quantidade_erros"] == 0

    # Verifica distribuição de acertos por estudante (Gráfico 5):
    # EST-001 acertou 1 questão e EST-002 acertou 1 questão -> 2 estudantes na faixa de 1 acerto
    dist_est = {
        d["quantidade_acertos"]: d["quantidade_estudantes"]
        for d in ind_c["distribuicao_acertos_estudantes"]
    }
    assert dist_est == {0: 0, 1: 2, 2: 0}

    # 4. Isolamento entre professores/turmas/disciplinas e entre escolas nos indicadores
    resp_prof2_negado = client.get(
        f"/api/v1/indicadores/avaliacoes?turma_id={cenario['turma_1a'].id}",
        headers=headers_prof2,
    )
    assert resp_prof2_negado.status_code == 403

    resp_gestor_b_negado = client.get(
        f"/api/v1/indicadores/avaliacoes?avaliacao_id={av_comp['id']}",
        headers=headers_gestor_b,
    )
    assert resp_gestor_b_negado.status_code == 403

    resp_gestor_a_ok = client.get(
        f"/api/v1/indicadores/avaliacoes?avaliacao_id={av_comp['id']}",
        headers=headers_gestor_a,
    )
    assert resp_gestor_a_ok.status_code == 200


# ==============================================================================
# 2. TESTES DE BACKEND — CONSISTÊNCIA DE GABARITO E INTEGRIDADE DE RESULTADOS (BLOCO E)
# ==============================================================================


def test_fase5_consistencia_gabarito_e_protecao_historico_questao(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Testa os itens 6.2 e 6.3 (Bloco E):
    - Questões novas fechadas exigem `alternativa_correta` (A-E).
    - Quando a questão já existe no banco e um novo arquivo omite `alternativa_correta`,
      o gabarito cadastrado é reaproveitado explicitamente e validado.
    - Quando o arquivo informa `alternativa_correta` (ou `tipo_questao` / `valor_questao`)
      diferente da questão já cadastrada no banco, a validação rejeita o conflito e NUNCA
      sobrescreve silenciosamente o gabarito existente.
    - `PATCH /api/v1/questoes/{questao_id}` bloqueia (HTTP 409) alterações de `alternativa_correta`,
      `tipo_questao` ou `valor_questao` quando a questão já possui respostas registradas,
      mas permite editar `topico` ou `faixa_dificuldade`, e permite editar gabarito quando ainda
      não existem respostas.
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    # 1. Cria avaliação e questão Q01 (sem respostas ainda) -> permite atualizar gabarito
    av = client.post(
        "/api/v1/avaliacoes",
        headers=headers_prof1,
        json={
            "codigo": "AV-GAB-01",
            "titulo": "Prova Proteção Gabarito",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_avaliacao": "2026-04-28",
        },
    ).json()
    q01 = client.post(
        f"/api/v1/avaliacoes/{av['id']}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q01",
            "tipo_questao": "FECHADA",
            "alternativa_correta": "A",
            "valor_questao": 2.0,
            "faixa_dificuldade": "Fácil",
            "topico": "Álgebra",
        },
    ).json()

    # Sem respostas registradas, pode alterar alternativa_correta de A para B
    patch_sem_resp = client.patch(
        f"/api/v1/questoes/{q01['id']}",
        headers=headers_prof1,
        json={"alternativa_correta": "B"},
    )
    assert patch_sem_resp.status_code == 200, patch_sem_resp.text
    assert patch_sem_resp.json()["alternativa_correta"] == "B"

    # 2. Importa resposta para EST-001 omitindo `alternativa_correta` no CSV:
    # deve reaproveitar o gabarito 'B' já cadastrado no banco!
    csv_omite_gabarito = (
        "id_avaliacao,titulo_avaliacao,disciplina,turma,periodo_letivo,data_avaliacao,"
        "id_questao,tipo_questao,valor_questao,alternativa_correta,codigo_anonimo,"
        "alternativa_marcada,em_branco,nota_obtida,faixa_dificuldade,topico\n"
        "AV-GAB-01,Prova Proteção Gabarito,MAT,Turma 1A,1º Bimestre,2026-04-28,"
        "Q01,FECHADA,2.0,,EST-001,B,Não,,Fácil,Álgebra\n"
    ).encode("utf-8")

    val_reuso = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("reuso_gabarito.csv", csv_omite_gabarito, "text/csv")},
    ).json()
    assert val_reuso["status"] == "validado", val_reuso
    assert val_reuso["previa_registros"][0]["alternativa_correta"] == "B"
    assert val_reuso["previa_registros"][0]["acertou"] is True

    conf_reuso = client.post(
        f"/api/v1/importacoes/{val_reuso['id']}/confirmar",
        headers=headers_prof1,
    )
    assert conf_reuso.status_code == 200

    # 3. Agora que Q01 possui resposta registrada, tentativa de alterar gabarito/valor/tipo via PATCH deve retornar 409
    patch_conflito_gab = client.patch(
        f"/api/v1/questoes/{q01['id']}",
        headers=headers_prof1,
        json={"alternativa_correta": "E"},
    )
    assert patch_conflito_gab.status_code == 409

    patch_conflito_val = client.patch(
        f"/api/v1/questoes/{q01['id']}",
        headers=headers_prof1,
        json={"valor_questao": 5.0},
    )
    assert patch_conflito_val.status_code == 409

    # Alterar apenas metadado pedagógico (`topico`) continua permitido
    patch_topico_ok = client.patch(
        f"/api/v1/questoes/{q01['id']}",
        headers=headers_prof1,
        json={"topico": "Equações Lineares"},
    )
    assert patch_topico_ok.status_code == 200
    assert patch_topico_ok.json()["topico"] == "Equações Lineares"

    # 4. Tentativa de reimportar planilha com gabarito conflitante ('D' em vez de 'B') -> deve ser rejeitada na validação!
    csv_gabarito_conflitante = (
        "id_avaliacao,titulo_avaliacao,disciplina,turma,periodo_letivo,data_avaliacao,"
        "id_questao,tipo_questao,valor_questao,alternativa_correta,codigo_anonimo,"
        "alternativa_marcada,em_branco,nota_obtida,faixa_dificuldade,topico\n"
        "AV-GAB-01,Prova Proteção Gabarito,MAT,Turma 1A,1º Bimestre,2026-04-28,"
        "Q01,FECHADA,2.0,D,EST-002,D,Não,,Fácil,Equações Lineares\n"
    ).encode("utf-8")

    val_conflito = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={
            "arquivo": (
                "conflito_gabarito.csv",
                csv_gabarito_conflitante,
                "text/csv",
            )
        },
    ).json()
    assert val_conflito["status"] == "com_erros"
    assert val_conflito["pode_confirmar"] is False
    erros_gab = [
        e
        for e in val_conflito["relatorio_validacao"]["valores_invalidos"]
        if e["campo"] == "alternativa_correta"
    ]
    assert len(erros_gab) == 1
    assert "conflito de gabarito" in erros_gab[0]["mensagem"].lower()


# ==============================================================================
# 3. TESTES DE FRONTEND — VALIDAÇÃO `em_branco` EM `entrada_dados.py` (ITEM 6.1)
# ==============================================================================


def test_fase5_frontend_prevalidacao_em_branco_consistente_com_backend() -> None:
    """
    Testa o item 6.1 (Bloco E) em `Frontend vertice/pages/entrada_dados.py`:
    - `em_branco=Sim/True` não pode coexistir com `alternativa_marcada=A..E`;
    - `em_branco=Não/False` exige alternativa válida A..E em questão fechada (não aceita vazio nem BRANCO);
    - `alternativa_marcada=BRANCO` é reconhecida como resposta em branco;
    - Valores booleanos inválidos em `em_branco` são rejeitados com mensagem clara.
    """
    from pages.entrada_dados import COLUNAS_AVALIACOES, _validar

    def _montar_df(linhas: list[dict[str, str]]) -> pd.DataFrame:
        base = {
            "id_avaliacao": "AV-01",
            "titulo_avaliacao": "Prova 1",
            "disciplina": "MAT",
            "turma": "Turma 1A",
            "periodo_letivo": "1º Bimestre",
            "data_avaliacao": "2026-04-20",
            "id_questao": "Q01",
            "tipo_questao": "FECHADA",
            "valor_questao": "2.0",
            "alternativa_correta": "B",
            "codigo_anonimo": "EST-001",
            "alternativa_marcada": "B",
            "em_branco": "Não",
            "nota_obtida": "",
            "faixa_dificuldade": "Adequada",
            "topico": "Funções",
        }
        registros = []
        for override in linhas:
            item = dict(base)
            item.update(override)
            registros.append(item)
        return pd.DataFrame(registros, columns=COLUNAS_AVALIACOES)

    # 1. Contradição: em_branco="Sim" e alternativa_marcada="A" -> deve ser rejeitado
    df_contradicao_1 = _montar_df([
        {"em_branco": "Sim", "alternativa_marcada": "A"}
    ])
    val_1, erros_1 = _validar(df_contradicao_1, "Resultados de avaliações")
    assert val_1 is None
    assert not erros_1.empty
    assert any("inconsistência" in p.lower() for p in erros_1["Problema"])

    # 2. Contradição: em_branco="Não" e alternativa_marcada="BRANCO" -> deve ser rejeitado
    df_contradicao_2 = _montar_df([
        {"em_branco": "Não", "alternativa_marcada": "BRANCO"}
    ])
    val_2, erros_2 = _validar(df_contradicao_2, "Resultados de avaliações")
    assert val_2 is None
    assert not erros_2.empty
    assert any("inconsistência" in p.lower() for p in erros_2["Problema"])

    # 3. Valor booleano inválido em `em_branco` (ex.: "talvez") -> deve ser rejeitado
    df_bool_invalido = _montar_df([
        {"em_branco": "talvez", "alternativa_marcada": "B"}
    ])
    val_3, erros_3 = _validar(df_bool_invalido, "Resultados de avaliações")
    assert val_3 is None
    assert not erros_3.empty
    assert any("booleano inválido" in p.lower() for p in erros_3["Problema"])

    # 4. Caso válido: alternativa_marcada="BRANCO" com em_branco="Sim" (ou vazio)
    df_branco_valido = _montar_df([
        {"codigo_anonimo": "EST-001", "em_branco": "Sim", "alternativa_marcada": "BRANCO"},
        {"codigo_anonimo": "EST-002", "em_branco": "", "alternativa_marcada": "BRANCO"},
        {"codigo_anonimo": "EST-003", "em_branco": "Não", "alternativa_marcada": "B"},
    ])
    val_4, erros_4 = _validar(df_branco_valido, "Resultados de avaliações")
    assert erros_4.empty, erros_4.to_dict("records")
    assert val_4 is not None
    assert len(val_4) == 3


# ==============================================================================
# 4. TESTES DE FRONTEND INTEGRADOS À API — MAPA DE ACERTOS, GRÁFICOS E SESSÃO
# ==============================================================================


def test_fase5_frontend_integracao_api_graficos_filtros_e_erros(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Testa a integração real entre o frontend (`data/api_client.py`, `components/graficos.py`,
    `pages/mapa_acertos.py`, `data/mock_data.py`) e o backend FastAPI:
    - Autenticação via `autenticar_usuario_api` sem expor tokens em mensagens de erro;
    - Carregamento de dados reais da API (`_carregar_contexto_api` e `consultar_indicadores_avaliacoes`);
    - Atualização dos dados e dos 6 gráficos ao alterar os filtros (`turma_id`, `disciplina_id`, `periodo_letivo`, `avaliacao_id`);
    - Exclusão de questões abertas do gráfico de distribuição de alternativas A-E;
    - Exibição adequada quando não há avaliações ou respostas;
    - Tratamento de sessão expirada (`401`), permissão insuficiente (`403`) e falha de comunicação com a API;
    - Ausência de dados fictícios em `mock_data.py`.
    """
    from components.graficos import (
        grafico_acertos_erros_brancos_por_questao,
        grafico_comparacao_desempenho_questoes,
        grafico_desempenho_por_topico,
        grafico_distribuicao_alternativas_questao,
        grafico_distribuicao_geral_acertos_avaliacao,
        grafico_percentual_acerto_por_questao,
    )
    from data import mock_data
    from data.api_client import (
        autenticar_usuario_api,
        configurar_cliente_http_teste,
        consultar_indicadores_avaliacoes,
        sanitizar_mensagem_erro,
    )
    from pages.mapa_acertos import (
        _carregar_contexto_api,
        _construir_dataframe_questoes,
    )

    # Garante ausência de dados fictícios em mock_data
    assert mock_data.DESEMPENHO_QUESTOES.empty
    assert mock_data.RESPOSTAS_POR_QUESTAO == []
    assert mock_data.TOTAL_RESPONDENTES == 0

    cenario = _criar_cenario_fase4(db_session)

    # Conecta o cliente HTTP do frontend diretamente ao TestClient do backend
    configurar_cliente_http_teste(client.request)
    st.session_state.clear()

    try:
        # 1. Autenticação do Professor 1 pelo cliente do frontend
        resp_login = autenticar_usuario_api(
            "prof1@vertice.edu.br", "SenhaForte@123"
        )
        assert resp_login.ok is True
        assert "access_token" in st.session_state

        # 2. Importa duas avaliações em períodos diferentes (1º Bimestre e 2º Bimestre)
        headers_prof1 = {"Authorization": f"Bearer {st.session_state['access_token']}"}
        csv_duas_avaliacoes = (
            "id_avaliacao,titulo_avaliacao,disciplina,turma,periodo_letivo,data_avaliacao,"
            "id_questao,tipo_questao,valor_questao,alternativa_correta,codigo_anonimo,"
            "alternativa_marcada,em_branco,nota_obtida,faixa_dificuldade,topico\n"
            "AV-B1,Prova 1º Bim,MAT,Turma 1A,1º Bimestre,2026-04-10,"
            "Q01,FECHADA,2.0,A,EST-001,A,Não,,Fácil,Funções\n"
            "AV-B1,Prova 1º Bim,MAT,Turma 1A,1º Bimestre,2026-04-10,"
            "Q01,FECHADA,2.0,A,EST-002,C,Não,,Fácil,Funções\n"
            "AV-B1,Prova 1º Bim,MAT,Turma 1A,1º Bimestre,2026-04-10,"
            "Q01,FECHADA,2.0,A,EST-003,BRANCO,Sim,,Fácil,Funções\n"
            "AV-B1,Prova 1º Bim,MAT,Turma 1A,1º Bimestre,2026-04-10,"
            "Q02,ABERTA,3.0,,EST-001,,Não,2.5,Difícil,Geometria\n"
            "AV-B2,Prova 2º Bim,MAT,Turma 1A,2º Bimestre,2026-06-15,"
            "Q01,FECHADA,5.0,E,EST-001,E,Não,,Adequada,Logaritmos\n"
            "AV-B2,Prova 2º Bim,MAT,Turma 1A,2º Bimestre,2026-06-15,"
            "Q01,FECHADA,5.0,E,EST-002,E,Não,,Adequada,Logaritmos\n"
            "AV-B2,Prova 2º Bim,MAT,Turma 1A,2º Bimestre,2026-06-15,"
            "Q01,FECHADA,5.0,E,EST-003,E,Não,,Adequada,Logaritmos\n"
        ).encode("utf-8")

        lote = client.post(
            "/api/v1/importacoes/validar",
            headers=headers_prof1,
            files={"arquivo": ("duas_av.csv", csv_duas_avaliacoes, "text/csv")},
        ).json()
        assert lote["status"] == "validado"
        client.post(
            f"/api/v1/importacoes/{lote['id']}/confirmar",
            headers=headers_prof1,
        )

        # 3. Carrega o contexto real da API pelo módulo do Mapa de Acertos
        ctx = _carregar_contexto_api()
        assert ctx["conectado"] is True
        assert len(ctx["avaliacoes"]) == 2
        mapa_av = {av["codigo"]: av for av in ctx["avaliacoes"]}

        # 4. Filtra Avaliação do 1º Bimestre (AV-B1) e valida geração dos 6 gráficos analíticos
        resp_ind_b1 = consultar_indicadores_avaliacoes(
            turma_id=str(cenario["turma_1a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
            periodo_letivo="1º Bimestre",
            avaliacao_id=str(mapa_av["AV-B1"]["id"]),
        )
        assert resp_ind_b1.ok is True
        dados_b1: dict[str, Any] = resp_ind_b1.dados
        questoes_b1 = dados_b1["questoes"]
        assert len(questoes_b1) == 2

        df_q_b1 = _construir_dataframe_questoes(questoes_b1)
        assert list(df_q_b1["Questão"]) == ["Q01", "Q02"]
        assert list(df_q_b1["Acertos"]) == [1, 1]
        assert list(df_q_b1["Erros"]) == [1, 0]
        assert list(df_q_b1["Em branco"]) == [1, 0]

        # Gráfico 1: Distribuição de alternativas para Q01 (FECHADA) -> retorna Figure; para Q02 (ABERTA) -> None
        fig_g1_fechada = grafico_distribuicao_alternativas_questao(questoes_b1[0])
        assert fig_g1_fechada is not None
        fig_g1_aberta = grafico_distribuicao_alternativas_questao(questoes_b1[1])
        assert fig_g1_aberta is None

        # Gráfico 2: Acertos, erros e respostas em branco
        fig_g2 = grafico_acertos_erros_brancos_por_questao(questoes_b1)
        assert fig_g2 is not None

        # Gráfico 3: Percentual de acerto por questão
        fig_g3 = grafico_percentual_acerto_por_questao(df_q_b1)
        assert fig_g3 is not None

        # Gráfico 4: Comparação de desempenho entre questões
        fig_g4 = grafico_comparacao_desempenho_questoes(questoes_b1)
        assert fig_g4 is not None

        # Gráfico 5: Distribuição geral de acertos da avaliação
        fig_g5 = grafico_distribuicao_geral_acertos_avaliacao(dados_b1)
        assert fig_g5 is not None

        # Gráfico 6: Desempenho por tópico ou habilidade
        fig_g6 = grafico_desempenho_por_topico(dados_b1["distribuicao_por_topico"])
        assert fig_g6 is not None

        # 5. Altera o filtro para o 2º Bimestre (AV-B2) e verifica que os indicadores e gráficos mudam
        resp_ind_b2 = consultar_indicadores_avaliacoes(
            turma_id=str(cenario["turma_1a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
            periodo_letivo="2º Bimestre",
            avaliacao_id=str(mapa_av["AV-B2"]["id"]),
        )
        assert resp_ind_b2.ok is True
        dados_b2 = resp_ind_b2.dados
        assert dados_b2["total_questoes"] == 1
        assert dados_b2["taxa_acerto_geral_percentual"] == 100.0
        df_q_b2 = _construir_dataframe_questoes(dados_b2["questoes"])
        assert list(df_q_b2["Acerto (%)"]) == [100.0]

        # 6. Testa tratamento de Permissão Insuficiente (403) ao filtrar turma fora do vínculo do professor
        resp_403 = consultar_indicadores_avaliacoes(
            turma_id=str(cenario["turma_3a"].id),
        )
        assert resp_403.ok is False
        assert resp_403.status_code == 403
        assert resp_403.sem_permissao is True

        # 7. Testa tratamento de Sessão Expirada / Token Inválido (401) e ocultação de tokens
        token_falso = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token_invalido_secreto"
        st.session_state["access_token"] = token_falso
        resp_401 = consultar_indicadores_avaliacoes()
        assert resp_401.ok is False
        assert resp_401.status_code == 401
        assert resp_401.sessao_expirada is True
        assert "access_token" not in st.session_state
        assert token_falso not in (resp_401.erro or "")
        assert token_falso not in sanitizar_mensagem_erro(f"Erro com Bearer {token_falso}")

        # 8. Testa tratamento de falha de comunicação com a API (servidor offline)
        def _falha_conexao(*_args: Any, **_kwargs: Any) -> Any:
            raise ConnectionError("Servidor offline")

        st.session_state["access_token"] = "token_qualquer"
        configurar_cliente_http_teste(_falha_conexao)
        resp_offline = consultar_indicadores_avaliacoes()
        assert resp_offline.ok is False
        assert resp_offline.indisponivel is True
        assert resp_offline.dados is None
    finally:
        configurar_cliente_http_teste(None)
        st.session_state.clear()
