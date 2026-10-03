"""Funções que montam os gráficos (Plotly). Cada uma recebe um DataFrame e devolve a figura.

As cores vêm de components/cores.py; a aparência comum (fonte e fundo), de _estilizar().
"""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from components.cores import (
    AZUL_ESCURO, COR_POR_CATEGORIA, FONTE, GRAFITE, SEQUENCIA_CORES, VERMELHO,
)


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
       # Ordem das barras = ordem dos dados, com a 1ª no topo (sem isso, elas se agrupam por cor).
    figura.update_yaxes(categoryorder="array", categoryarray=list(dados[y]), autorange="reversed")
    return _estilizar(figura)


def grafico_dispersao(dados, x, y):
    """Pontos soltos com linha de tendência, para ver a relação entre duas medidas."""
    figura = px.scatter(dados, x=x, y=y, color_discrete_sequence=[AZUL_ESCURO])
    inclinacao, intercepto = np.polyfit(dados[x], dados[y], 1)  # reta que melhor acompanha os pontos
    x_reta = [dados[x].min(), dados[x].max()]
    y_reta = [inclinacao * valor + intercepto for valor in x_reta]
    figura.add_trace(go.Scatter(x=x_reta, y=y_reta, mode="lines", name="Tendência",
                                line={"color": VERMELHO}))
    figura.update_layout(showlegend=False)
    return _estilizar(figura)