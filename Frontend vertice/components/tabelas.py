"""Tabela com paginação."""
from math import ceil

import streamlit as st

from utils.formatacao import numero_br


def _mudar_pagina(chave, passo):
    st.session_state[chave] += passo


def tabela_paginada(dados, tamanho_pagina=5, chave="tabela", reiniciar_quando=None, selecionavel=False):
    """Mostra `dados` (DataFrame) uma página por vez, com "Anterior" e "Próxima".

    `reiniciar_quando`: qualquer valor que, ao mudar (ex.: os filtros), volta para a página 1.
    `selecionavel`: permite clicar numa linha. Nesse caso devolve a posição da linha escolhida
    dentro de `dados` (não só da página), ou None se nenhuma estiver escolhida.
    """
    total = len(dados)
    total_paginas = max(1, ceil(total / tamanho_pagina))

    if st.session_state.get(f"{chave}_ref") != reiniciar_quando:
        st.session_state[f"{chave}_ref"] = reiniciar_quando
        st.session_state[chave] = 1
    pagina = min(max(st.session_state.get(chave, 1), 1), total_paginas)
    st.session_state[chave] = pagina

    inicio = (pagina - 1) * tamanho_pagina
    fim = min(inicio + tamanho_pagina, total)

    posicao_escolhida = None
    if selecionavel:
        # A chave inclui a página: ao trocar de página a seleção começa vazia.
        posicao_na_pagina = tabela_selecionavel(dados.iloc[inicio:fim], f"{chave}_tabela_{pagina}")
        if posicao_na_pagina is not None:
            posicao_escolhida = inicio + posicao_na_pagina
    else:
        st.dataframe(dados.iloc[inicio:fim], hide_index=True, width="stretch")

    col_info, col_anterior, col_pagina, col_proxima = st.columns([5, 1, 2, 1])
    if total:
        col_info.caption(f"Mostrando {inicio + 1}-{fim} de {numero_br(total)}")
    else:
        col_info.caption("Nenhum resultado encontrado")
    col_anterior.button("Anterior", key=f"{chave}_ant", on_click=_mudar_pagina,
                        args=(chave, -1), disabled=pagina == 1)
    col_pagina.caption(f"Página {numero_br(pagina)} de {numero_br(total_paginas)}")
    col_proxima.button("Próxima", key=f"{chave}_prox", on_click=_mudar_pagina,
                       args=(chave, 1), disabled=pagina == total_paginas)
    return posicao_escolhida

    

def tabela_selecionavel(dados, chave):
    """Tabela em que se clica numa linha. Devolve a posição da linha escolhida, ou None."""
    evento = st.dataframe(
        dados, hide_index=True, width="stretch",
        on_select="rerun", selection_mode="single-row", key=chave,
    )
    linhas = evento.selection.rows
    return linhas[0] if linhas else None