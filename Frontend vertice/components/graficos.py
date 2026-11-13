"""Funções que montam os gráficos (Plotly). Cada uma recebe um DataFrame ou estrutura do backend e devolve a figura.

As cores vêm de components/cores.py; a aparência comum (fonte e fundo), de _estilizar().
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from components.cores import (
    AZUL,
    AZUL_ESCURO,
    COR_POR_CATEGORIA,
    FONTE,
    GRAFITE,
    LARANJA,
    SEQUENCIA_CORES,
    VERDE,
    VERMELHO,
)


ALTERNATIVAS_ORDEM_OFICIAL = ["A", "B", "C", "D", "E", "BRANCO"]


def _estilizar(figura):
    """Aparência comum a todos os gráficos: fonte do projeto e fundo transparente (o cartão é branco)."""
    figura.update_layout(
        font={"family": FONTE, "color": GRAFITE},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
    )
    return figura


def grafico_linha(dados, x, y, cor=None):
    """Linhas de evolução ao longo do tempo. Com `cor`, uma linha por categoria."""
    figura = px.line(dados, x=x, y=y, color=cor, markers=True, color_discrete_sequence=SEQUENCIA_CORES)
    return _estilizar(figura)


def grafico_rosca(dados, nomes, valores):
    """Gráfico de rosca com a distribuição por categoria."""
    figura = px.pie(dados, names=nomes, values=valores, hole=0.5,
                    color=nomes, color_discrete_map=COR_POR_CATEGORIA)
    return _estilizar(figura)


def grafico_barras_horizontais(dados, x, y, cor=None):
    """Barras horizontais: `y` são as categorias, `x` os valores.

    `cor` (opcional): coluna que define a cor de cada barra e aparece na legenda.
    """
    figura = px.bar(dados, x=x, y=y, color=cor, orientation="h",
                    color_discrete_map=COR_POR_CATEGORIA, color_discrete_sequence=SEQUENCIA_CORES)
    figura.update_yaxes(categoryorder="array", categoryarray=list(dados[y]), autorange="reversed")
    return _estilizar(figura)


def grafico_dispersao(dados, x, y):
    """Pontos soltos com linha de tendência, para ver a relação entre duas medidas."""
    figura = px.scatter(dados, x=x, y=y, color_discrete_sequence=[AZUL_ESCURO])
    if len(dados) >= 2 and dados[x].nunique() >= 2:
        inclinacao, intercepto = np.polyfit(dados[x], dados[y], 1)  # reta que melhor acompanha os pontos
        x_reta = [dados[x].min(), dados[x].max()]
        y_reta = [inclinacao * valor + intercepto for valor in x_reta]
        figura.add_trace(go.Scatter(x=x_reta, y=y_reta, mode="lines", name="Tendência",
                                    line={"color": VERMELHO}))
    figura.update_layout(showlegend=False)
    return _estilizar(figura)


# ==============================================================================
# GRÁFICOS DO MAPA DE ACERTOS E AVALIAÇÕES (FASE 5 — BLOCO C)
# ==============================================================================


def grafico_percentual_acerto_por_questao(df_questoes: pd.DataFrame):
    """Gráfico 3: Percentual de acerto por questão colorido pela faixa de dificuldade."""
    figura = grafico_barras_horizontais(
        df_questoes,
        "Acerto (%)",
        "Questão",
        cor="Dificuldade",
    )
    figura.update_xaxes(
        range=[0, 108],
        tickvals=[0, 20, 40, 60, 80, 100],
        ticksuffix="%",
        title=None,
        showgrid=True,
        gridcolor="#E6E6E6",
    )
    figura.update_yaxes(title=None)
    figura.update_traces(
        texttemplate="%{x:.1f}%",
        textposition="outside",
    )
    figura.update_layout(
        height=max(280, 50 * len(df_questoes) + 80),
        autosize=True,
        margin={"l": 10, "r": 35, "t": 15, "b": 20},
        legend={"orientation": "h", "x": 0, "y": 1.12},
    )
    return figura


def grafico_distribuicao_alternativas_questao(questao_item: dict):
    """Gráfico 1: Distribuição de alternativas por questão (A, B, C, D, E e BRANCO).

    Regra obrigatória: Questões abertas NÃO aparecem na distribuição de alternativas A–E;
    para questões abertas, retorna `None` para que a interface exiba aviso explicativo.
    """
    tipo_q = str(questao_item.get("tipo_questao", "")).upper()
    if tipo_q != "FECHADA":
        return None

    dist = questao_item.get("distribuicao_alternativas") or {}
    correta = str(questao_item.get("alternativa_correta") or "").strip().upper()
    denom = int(questao_item.get("total_respostas_esperadas") or 0)

    linhas = []
    for alt in ALTERNATIVAS_ORDEM_OFICIAL:
        qtd = int(dist.get(alt, 0))
        perc = round((qtd / denom) * 100.0, 1) if denom > 0 else 0.0
        if alt == "BRANCO":
            categoria = "Em branco"
        elif alt == correta:
            categoria = "Correta (Gabarito)"
        else:
            categoria = "Distrator (Erro)"
        linhas.append({
            "Alternativa": alt,
            "Quantidade": qtd,
            "Percentual (%)": perc,
            "Classificação": categoria,
        })

    df_alt = pd.DataFrame(linhas)
    mapa_cores = {
        "Correta (Gabarito)": VERDE,
        "Distrator (Erro)": AZUL,
        "Em branco": LARANJA,
    }
    figura = px.bar(
        df_alt,
        x="Alternativa",
        y="Quantidade",
        color="Classificação",
        color_discrete_map=mapa_cores,
        text="Quantidade",
        hover_data={"Percentual (%)": ":.1f"},
    )
    figura.update_xaxes(
        categoryorder="array",
        categoryarray=ALTERNATIVAS_ORDEM_OFICIAL,
        title="Alternativa marcada",
    )
    figura.update_yaxes(
        title="Estudantes",
        showgrid=True,
        gridcolor="#E6E6E6",
    )
    figura.update_traces(textposition="outside")
    figura.update_layout(
        height=310,
        autosize=True,
        margin={"l": 10, "r": 15, "t": 25, "b": 20},
        legend={"orientation": "h", "x": 0, "y": 1.15},
    )
    return _estilizar(figura)


def grafico_acertos_erros_brancos_por_questao(questoes_api: list[dict]):
    """Gráfico 2: Acertos, erros e respostas em branco por questão.

    Regra obrigatória: Respostas em branco são contabilizadas separadamente (nunca como erro),
    e ausências de resposta não são transformadas em respostas registradas.
    """
    linhas = []
    ordem_questoes = []
    for q in questoes_api:
        cod = str(q.get("codigo_questao", ""))
        ordem_questoes.append(cod)
        linhas.append({
            "Questão": cod,
            "Resultado": "Acertos",
            "Quantidade": int(q.get("quantidade_acertos") or 0),
        })
        linhas.append({
            "Questão": cod,
            "Resultado": "Erros",
            "Quantidade": int(q.get("quantidade_erros") or 0),
        })
        linhas.append({
            "Questão": cod,
            "Resultado": "Em branco",
            "Quantidade": int(q.get("quantidade_em_branco") or 0),
        })
        ausentes = int(q.get("quantidade_respostas_ausentes") or 0)
        if ausentes > 0:
            linhas.append({
                "Questão": cod,
                "Resultado": "Sem resposta registrada",
                "Quantidade": ausentes,
            })

    df_comp = pd.DataFrame(linhas)
    mapa_cores = {
        "Acertos": VERDE,
        "Erros": VERMELHO,
        "Em branco": LARANJA,
        "Sem resposta registrada": "#9E9E9E",
    }
    figura = px.bar(
        df_comp,
        x="Questão",
        y="Quantidade",
        color="Resultado",
        barmode="group",
        color_discrete_map=mapa_cores,
        text="Quantidade",
    )
    figura.update_xaxes(
        categoryorder="array",
        categoryarray=ordem_questoes,
        title="Questão",
    )
    figura.update_yaxes(
        title="Quantidade de respostas",
        showgrid=True,
        gridcolor="#E6E6E6",
    )
    figura.update_traces(textposition="outside")
    figura.update_layout(
        height=330,
        autosize=True,
        margin={"l": 10, "r": 15, "t": 25, "b": 20},
        legend={"orientation": "h", "x": 0, "y": 1.15},
    )
    return _estilizar(figura)


def grafico_comparacao_desempenho_questoes(questoes_api: list[dict]):
    """Gráfico 4: Comparação de desempenho entre questões (Taxa de acerto % vs Aproveitamento de nota %)."""
    linhas = []
    ordem_questoes = []
    for q in questoes_api:
        cod = str(q.get("codigo_questao", ""))
        ordem_questoes.append(cod)
        taxa = q.get("taxa_acerto_percentual")
        media_nota = q.get("media_nota_questao")
        valor_q = float(q.get("valor_questao") or 0.0)
        aprov_nota = (
            round((float(media_nota) / valor_q) * 100.0, 2)
            if media_nota is not None and valor_q > 0
            else 0.0
        )
        linhas.append({
            "Questão": cod,
            "Indicador": "Taxa de acerto (%)",
            "Percentual (%)": float(taxa) if taxa is not None else 0.0,
        })
        linhas.append({
            "Questão": cod,
            "Indicador": "Aproveitamento médio de nota (%)",
            "Percentual (%)": aprov_nota,
        })

    df_cmp = pd.DataFrame(linhas)
    figura = px.bar(
        df_cmp,
        x="Questão",
        y="Percentual (%)",
        color="Indicador",
        barmode="group",
        color_discrete_map={
            "Taxa de acerto (%)": AZUL,
            "Aproveitamento médio de nota (%)": AZUL_ESCURO,
        },
    )
    figura.update_xaxes(
        categoryorder="array",
        categoryarray=ordem_questoes,
        title="Questão",
    )
    figura.update_yaxes(
        range=[0, 110],
        ticksuffix="%",
        title="Desempenho (%)",
        showgrid=True,
        gridcolor="#E6E6E6",
    )
    figura.update_traces(
        texttemplate="%{y:.1f}%",
        textposition="outside",
    )
    figura.update_layout(
        height=330,
        autosize=True,
        margin={"l": 10, "r": 15, "t": 25, "b": 20},
        legend={"orientation": "h", "x": 0, "y": 1.15},
    )
    return _estilizar(figura)


def grafico_distribuicao_geral_acertos_avaliacao(indicadores_payload: dict):
    """Gráfico 5: Distribuição geral de acertos da avaliação.

    Utiliza `distribuicao_acertos_estudantes` retornada pelo backend quando disponível,
    ou apresenta a proporção consolidada de Acertos, Erros e Em branco da avaliação.
    """
    dist_est = indicadores_payload.get("distribuicao_acertos_estudantes") or []
    if dist_est:
        linhas = []
        for item in dist_est:
            k = int(item.get("quantidade_acertos", 0))
            tot_q = int(item.get("total_questoes_avaliacao", 0))
            qtd_est = int(item.get("quantidade_estudantes", 0))
            perc_est = float(item.get("percentual_estudantes", 0.0))
            rotulo = f"{k}/{tot_q} acertos"
            linhas.append({
                "Faixa de acertos": rotulo,
                "Estudantes": qtd_est,
                "Percentual da turma (%)": perc_est,
            })
        df_dist = pd.DataFrame(linhas)
        figura = px.bar(
            df_dist,
            x="Faixa de acertos",
            y="Estudantes",
            text="Estudantes",
            color_discrete_sequence=[AZUL],
            hover_data={"Percentual da turma (%)": ":.1f"},
        )
        figura.update_xaxes(title="Total de questões acertadas pelo estudante")
        figura.update_yaxes(
            title="Quantidade de estudantes",
            showgrid=True,
            gridcolor="#E6E6E6",
        )
        figura.update_traces(textposition="outside")
        figura.update_layout(
            height=320,
            autosize=True,
            showlegend=False,
            margin={"l": 10, "r": 15, "t": 25, "b": 20},
        )
        return _estilizar(figura)

    acertos = int(indicadores_payload.get("total_acertos") or 0)
    erros = int(indicadores_payload.get("total_erros") or 0)
    brancos = int(indicadores_payload.get("total_em_branco") or 0)
    if acertos + erros + brancos == 0:
        return None

    df_resumo = pd.DataFrame([
        {"Categoria": "Acertos", "Quantidade": acertos},
        {"Categoria": "Erros", "Quantidade": erros},
        {"Categoria": "Em branco", "Quantidade": brancos},
    ])
    figura = px.pie(
        df_resumo,
        names="Categoria",
        values="Quantidade",
        hole=0.5,
        color="Categoria",
        color_discrete_map={
            "Acertos": VERDE,
            "Erros": VERMELHO,
            "Em branco": LARANJA,
        },
    )
    figura.update_layout(
        height=320,
        autosize=True,
        margin={"l": 10, "r": 15, "t": 25, "b": 20},
    )
    return _estilizar(figura)


def grafico_desempenho_por_topico(distribuicao_por_topico: list[dict]):
    """Gráfico 6: Desempenho por tópico ou habilidade (quando existirem dados suficientes)."""
    if not distribuicao_por_topico:
        return None

    linhas = []
    for item in distribuicao_por_topico:
        taxa = item.get("taxa_acerto_percentual")
        if taxa is None:
            continue
        topico = str(item.get("topico") or "Geral / Não especificado")
        linhas.append({
            "Tópico / Habilidade": topico,
            "Taxa de acerto (%)": float(taxa),
            "Questões": int(item.get("total_questoes") or 0),
            "Acertos": int(item.get("quantidade_acertos") or 0),
            "Esperadas": int(item.get("total_respostas_esperadas") or 0),
        })

    if not linhas:
        return None

    df_top = pd.DataFrame(linhas)
    figura = px.bar(
        df_top,
        x="Taxa de acerto (%)",
        y="Tópico / Habilidade",
        orientation="h",
        color_discrete_sequence=[AZUL],
        hover_data=["Questões", "Acertos", "Esperadas"],
    )
    figura.update_xaxes(
        range=[0, 108],
        ticksuffix="%",
        title="Taxa de acerto (%)",
        showgrid=True,
        gridcolor="#E6E6E6",
    )
    figura.update_yaxes(
        categoryorder="array",
        categoryarray=list(df_top["Tópico / Habilidade"]),
        autorange="reversed",
        title=None,
    )
    figura.update_traces(
        texttemplate="%{x:.1f}%",
        textposition="outside",
    )
    figura.update_layout(
        height=max(260, 52 * len(df_top) + 70),
        autosize=True,
        showlegend=False,
        margin={"l": 10, "r": 35, "t": 20, "b": 20},
    )
    return _estilizar(figura)
