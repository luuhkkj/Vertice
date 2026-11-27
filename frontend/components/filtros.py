"""Filtros reutilizáveis: seleção com opção "todos" e botão de limpar."""
import streamlit as st


def filtro_selecao(rotulo, opcoes, chave, todos="Todos"):
    """Caixa de seleção. Devolve a opção escolhida, ou None quando está em "todos".

    Com `todos=None` não existe a opção "todos": a primeira opção já vem escolhida.
    """
    lista = ([todos] if todos else []) + list(opcoes)
    escolha = st.selectbox(rotulo, lista, key=chave)
    return None if todos and escolha == todos else escolha


def _limpar(chaves):
    for chave in chaves:
        st.session_state.pop(chave, None)  # sem valor guardado, o widget volta ao padrão


def botao_limpar_filtros(chaves):
    """Botão que devolve todos os filtros (identificados pelas `chaves`) ao padrão."""
    st.button("Limpar filtros", on_click=_limpar, args=(chaves,))