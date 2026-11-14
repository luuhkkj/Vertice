"""
Política de Prevenção de Vazamento de Dados (Data Leakage) — Fase 7.

Define o contrato explícito de variáveis elegíveis para futura entrada de modelos
preditivos e o validador de bloqueio obrigatório para `situacao_final`, campos
diretamente derivados do desfecho, informações pós-desfecho e atributos sensíveis (LGPD).

IMPORTANTE: Esta camada prepara e impõe contratos no backend sem executar
treinamento ou inferência preditiva nesta fase.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, Field


class VariavelPreditivaContrato(BaseModel):
    """Descritor formal de uma variável prevista no catálogo preditivo do Vértice."""

    nome: str
    origem: str
    tipo: str
    descricao: str
    disponibilidade_temporal: str
    sensibilidade: str = "baixa_anonimizada"
    elegivel_predicao: bool = True


# ==============================================================================
# CATÁLOGO OFICIAL DE VARIÁVEIS ELEGÍVEIS (SEM LEAKAGE E SEM PII)
# ==============================================================================
CATALOGO_VARIAVEIS_PREDITIVAS: tuple[VariavelPreditivaContrato, ...] = (
    VariavelPreditivaContrato(
        nome="frequencia_percentual",
        origem="boletins_periodo / notas_disciplinas",
        tipo="float",
        descricao="Percentual de presença acumulado até a data de corte da previsão.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="faltas",
        origem="boletins_periodo",
        tipo="int",
        descricao="Total de faltas registradas no período até o momento da extração.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="media_geral",
        origem="boletins_periodo",
        tipo="float",
        descricao="Média parcial das avaliações disponíveis antes do fechamento do período.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="notas_baixas",
        origem="boletins_periodo",
        tipo="int",
        descricao="Quantidade de componentes com rendimento abaixo do esperado até o corte.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="historico_reprovacoes",
        origem="estudantes / boletins_periodo",
        tipo="int",
        descricao="Acumulado histórico de reprovações em anos/períodos anteriores.",
        disponibilidade_temporal="historico_anterior",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="participacao_recuperacao",
        origem="boletins_periodo",
        tipo="bool",
        descricao="Indicador de participação em ações de recuperação paralela anteriores.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="atrasos",
        origem="boletins_periodo",
        tipo="int",
        descricao="Quantidade de atrasos registrados até a data de corte.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="idade",
        origem="boletins_periodo",
        tipo="int",
        descricao="Idade do estudante na série/ano letivo de referência.",
        disponibilidade_temporal="inicio_periodo",
        sensibilidade="moderada_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="taxa_entrega_atividades",
        origem="entregas_atividade",
        tipo="float",
        descricao="Percentual de atividades entregues sobre o total de entregas esperadas até o corte.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="entregas_atrasadas",
        origem="entregas_atividade",
        tipo="int",
        descricao="Quantidade de entregas realizadas após a data limite até o corte.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="nao_entregas_apos_prazo",
        origem="entregas_atividade",
        tipo="int",
        descricao="Quantidade de atividades vencidas ainda não entregues até a data de corte.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="taxa_acerto_avaliacoes",
        origem="respostas_avaliacao",
        tipo="float",
        descricao="Percentual de acertos em avaliações aplicadas até a data de corte.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="respostas_em_branco",
        origem="respostas_avaliacao",
        tipo="int",
        descricao="Contagem de questões deixadas em branco em avaliações até a data de corte.",
        disponibilidade_temporal="ate_data_corte",
        sensibilidade="baixa_anonimizada",
        elegivel_predicao=True,
    ),
)


# ==============================================================================
# LISTA EXPLÍCITA E EXTENSÍVEL DE VARIÁVEIS PROIBIDAS (LEAKAGE & PII)
# ==============================================================================
# Regra crítica: `situacao_final` só pode ser usada futuramente como TARGET em
# treinamento supervisionado; JAMAIS pode compor variáveis de entrada (features)
# para gerar a previsão do próprio desfecho.
CAMPOS_DESFECHO_E_LEAKAGE: dict[str, str] = {
    "situacao_final": "Variável-alvo de desfecho consolidado; uso como entrada causa data leakage.",
    "situacao": "Alias de situação final consolidada (desfecho pós-período).",
    "desfecho": "Representa diretamente o resultado final que se deseja prever.",
    "desfecho_final": "Representa diretamente o resultado final que se deseja prever.",
    "target": "Variável-alvo supervisionada não pode figurar como entrada de inferência.",
    "y_target": "Variável-alvo supervisionada não pode figurar como entrada de inferência.",
    "classe_real": "Rótulo observado do desfecho final.",
    "evadiu": "Variável binária derivada diretamente de situacao_final == 'Evadido'.",
    "reprovou": "Variável binária derivada diretamente de situacao_final == 'Reprovado'.",
    "aprovado": "Variável binária derivada diretamente de situacao_final == 'Aprovado'.",
    "status_final_periodo": "Derivada diretamente do encerramento do período letivo.",
    "resultado_final": "Informação disponível somente após o encerramento do período.",
    "nota_final_anual": "Consolidação anual disponível apenas após todos os períodos.",
    "frequencia_final_consolidada": "Consolidação posterior ao encerramento do período.",
    "data_evasao": "Evento temporal ocorrido no/após o desfecho de evasão.",
    "motivo_evasao": "Informação registrada apenas após ocorrência da evasão.",
    "encerramento_matricula": "Evento administrativo posterior ao desfecho escolar.",
    "pos_desfecho": "Atributo marcado como disponível apenas após o desfecho.",
}

CAMPOS_PII_PROIBIDOS_PREDICAO: dict[str, str] = {
    "nome": "Dado pessoal identificável (LGPD).",
    "nome_completo": "Dado pessoal identificável (LGPD).",
    "cpf": "Dado pessoal identificável (LGPD).",
    "rg": "Dado pessoal identificável (LGPD).",
    "email": "Dado de contato pessoal identificável (LGPD).",
    "telefone": "Dado de contato pessoal identificável (LGPD).",
    "endereco": "Dado residencial identificável (LGPD).",
}

CAMPOS_PROIBIDOS_PREDICAO: dict[str, str] = {
    **CAMPOS_DESFECHO_E_LEAKAGE,
    **CAMPOS_PII_PROIBIDOS_PREDICAO,
}


class ResultadoValidacaoLeakage(BaseModel):
    """Resultado estruturado da inspeção contra vazamento de dados."""

    valido: bool
    variaveis_analisadas: list[str] = Field(default_factory=list)
    variaveis_permitidas_reconhecidas: list[str] = Field(default_factory=list)
    variaveis_proibidas_detectadas: dict[str, str] = Field(default_factory=dict)
    aviso_politica: str = (
        "O campo situacao_final e atributos derivados ou pós-desfecho são "
        "bloqueados como entrada preditiva para prevenir data leakage."
    )


def _normalizar_chave(chave: str) -> str:
    return (
        str(chave)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def _coletar_chaves_recursivo(objeto: Any, prefixo: str = "") -> list[str]:
    chaves: list[str] = []
    if isinstance(objeto, Mapping):
        for k, v in objeto.items():
            k_str = str(k)
            chaves.append(k_str)
            if prefixo:
                chaves.append(f"{prefixo}.{k_str}")
            chaves.extend(_coletar_chaves_recursivo(v, k_str))
    elif isinstance(objeto, (list, tuple)):
        for item in objeto:
            if isinstance(item, (Mapping, list, tuple)):
                chaves.extend(_coletar_chaves_recursivo(item, prefixo))
    return chaves


def validar_variaveis_contra_leakage(
    entrada: Mapping[str, Any] | Iterable[str],
    *,
    campos_proibidos_extras: Mapping[str, str] | Iterable[str] | None = None,
    lancar_excecao: bool = True,
) -> ResultadoValidacaoLeakage:
    """
    Valida se um conjunto de nomes de variáveis ou dicionário de features/metadados
    contém `situacao_final` ou qualquer variável proibida por data leakage / LGPD.

    - Suporta extensão dinâmica via `campos_proibidos_extras`.
    - Quando `lancar_excecao=True`, levanta `HTTP 422` se houver violação.
    """
    mapa_proibidos = dict(CAMPOS_PROIBIDOS_PREDICAO)
    if isinstance(campos_proibidos_extras, Mapping):
        for k, motivo in campos_proibidos_extras.items():
            mapa_proibidos[_normalizar_chave(k)] = str(motivo)
    elif campos_proibidos_extras is not None:
        for k in campos_proibidos_extras:
            mapa_proibidos[_normalizar_chave(k)] = (
                "Variável bloqueada pela política adicional de prevenção de leakage."
            )

    nomes_catalogados = {_normalizar_chave(v.nome) for v in CATALOGO_VARIAVEIS_PREDITIVAS}

    if isinstance(entrada, Mapping):
        brutas = _coletar_chaves_recursivo(entrada)
    else:
        brutas = [str(item) for item in entrada]

    analisadas: list[str] = []
    reconhecidas: list[str] = []
    detectadas: dict[str, str] = {}

    for nome_orig in brutas:
        norm = _normalizar_chave(nome_orig)
        if not norm:
            continue
        analisadas.append(nome_orig)
        segmentos = [seg for seg in norm.split(".") if seg]

        violacao_encontrada: str | None = None
        for candidato in [norm, *segmentos]:
            if candidato in mapa_proibidos:
                violacao_encontrada = mapa_proibidos[candidato]
                break

        if violacao_encontrada is not None:
            detectadas[nome_orig] = violacao_encontrada
        elif norm in nomes_catalogados:
            reconhecidas.append(nome_orig)

    resultado = ResultadoValidacaoLeakage(
        valido=len(detectadas) == 0,
        variaveis_analisadas=analisadas,
        variaveis_permitidas_reconhecidas=reconhecidas,
        variaveis_proibidas_detectadas=detectadas,
    )

    if not resultado.valido and lancar_excecao:
        nomes_bad = ", ".join(sorted(detectadas.keys()))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Violação de integridade preditiva (data leakage / LGPD): "
                f"variável(is) proibida(s) na entrada do modelo: {nomes_bad}."
            ),
        )

    return resultado
