"""Cartões reutilizáveis: KPI (indicador) e caixa com título para gráficos/tabelas.

Cada cartão recebe uma chave (key) para o CSS conseguir estilizá-lo: a chave vira a classe
`st-key-<chave>`. Os estilos ficam em styles/cards.css.
"""
import re
from typing import Optional
import unicodedata

import streamlit as st


def _chave(prefixo: str, texto: str) -> str:
    """('card', 'Entrega por turma') -> 'card_entrega_por_turma'."""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_") or "item"
    return f"{prefixo}_{slug}"


def card_kpi(
    valor,
    rotulo: str,
    rodape: Optional[str] = None,
    cor: Optional[str] = None,
    chave: Optional[str] = None,
):
    """Cartão de indicador: valor grande, rótulo e (opcional) uma linha de rodapé.

    `cor` (opcional): "azul", "verde", "laranja" ou "vermelho" pinta o cartão inteiro.
    Sem `cor`, o cartão é branco.
    `chave` (opcional): permite diferenciar cartões quando dois blocos exibem o mesmo rótulo.
    """
    rotulo_limpo = str(rotulo or "").strip()
    if not rotulo_limpo:
        raise ValueError("O rótulo do card_kpi é obrigatório.")
    prefixo = f"kpi_{cor}" if cor else "kpi"
    with st.container(key=_chave(prefixo, chave or rotulo_limpo)):
        st.metric(label=rotulo_limpo, value=valor)
        if rodape:
            st.caption(rodape)


def card(
    titulo: str,
    subtitulo: Optional[str] = None,
    chave: Optional[str] = None,
):
    """Caixa com título (e subtítulo opcional).

    Use com `with card("Título"):` e ponha o conteúdo dentro.
    """
    titulo_limpo = str(titulo or "").strip()
    if not titulo_limpo:
        raise ValueError("O título do card é obrigatório.")
    caixa = st.container(key=_chave("card", chave or titulo_limpo))
    caixa.subheader(titulo_limpo, anchor=False)
    if subtitulo:
        caixa.caption(subtitulo)
    return caixa
