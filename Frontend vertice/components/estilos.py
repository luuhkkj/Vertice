"""Aplica o CSS do projeto: lê todos os arquivos .css da pasta styles/ e injeta na página."""
from pathlib import Path

import streamlit as st

PASTA_STYLES = Path(__file__).resolve().parent.parent / "styles"


def _ordem(arquivo):
    """base.css primeiro (cores e fonte); os demais em ordem alfabética, por cima dele."""
    return (arquivo.stem != "base", arquivo.name)


def carregar_estilos():
    """Chame uma vez por execução do app (em app.py)."""
    arquivos = sorted(PASTA_STYLES.glob("*.css"), key=_ordem)
    if not arquivos:
        st.warning(f"Nenhum arquivo .css encontrado em: {PASTA_STYLES}")
        return

    css = "\n".join(arquivo.read_text(encoding="utf-8") for arquivo in arquivos)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)