"""Cartões reutilizáveis: KPI (indicador) e caixa com título para gráficos/tabelas.

Cada cartão recebe uma chave (key) para o CSS conseguir estilizá-lo: a chave vira a classe
`st-key-<chave>`. Os estilos ficam em styles/cards.css.
"""
import re
import unicodedata

import streamlit as st


def _chave(prefixo, texto):
    """('card', 'Entrega por turma') -> 'card_entrega_por_turma'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return f"{prefixo}_{re.sub(r'[^a-z0-9]+', '_', sem_acento.lower()).strip('_')}"


def card_kpi(valor, rotulo, rodape=None, cor=None):
    """Cartão de indicador: valor grande, rótulo e (opcional) uma linha de rodapé.

    `cor` (opcional): "azul", "verde", "laranja" ou "vermelho" pinta o cartão inteiro.
    Sem `cor`, o cartão é branco.
    """
    with st.container(key=_chave(f"kpi_{cor}" if cor else "kpi", rotulo)):
        st.metric(label=rotulo, value=valor)
        if rodape:
            st.caption(rodape)


def card(titulo):
    """Caixa com título. Use com `with card("Título"):` e ponha o conteúdo dentro."""
    caixa = st.container(key=_chave("card", titulo))
    caixa.subheader(titulo, anchor=False)
    return caixa