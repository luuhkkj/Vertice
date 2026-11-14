"""
Política de Prevenção de Vazamento de Dados (Data Leakage), Contrato de Variáveis
e Contrato Estrito de Metadados Técnicos — Fase 7.

Garantias centrais:
1. Nenhuma variável desconhecida, sem contrato completo ou não elegível é aceita
   automaticamente como entrada preditiva.
2. `situacao_final` é preservada exclusivamente como referência de variável-alvo
   para futuro treinamento supervisionado e é terminantemente bloqueada como entrada.
3. Normalização Unicode (NFKD), remoção de acentos, espaços, hífens e variações de
   caixa + inspeção recursiva de listas, dicionários, prefixos e caminhos aninhados.
4. `metadados_tecnicos` possui contrato operacional próprio e fechado (extensível
   apenas por contrato explícito), impedindo PII, segredos/tokens, texto pedagógico
   identificável e contrabando de features proibidas.
"""

from collections.abc import Iterable, Mapping
from enum import Enum
import math
import re
from typing import Any, Optional
import unicodedata

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, field_validator


class DisponibilidadeTemporalVariavel(str, Enum):
    """Momento em que a informação está legitimamente disponível no fluxo escolar."""

    HISTORICO_ANTERIOR = "historico_anterior"
    INICIO_PERIODO = "inicio_periodo"
    ATE_DATA_CORTE = "ate_data_corte"
    POS_DESFECHO = "pos_desfecho"


class SensibilidadeVariavel(str, Enum):
    """Classificação de privacidade e sensibilidade (LGPD) da variável."""

    BAIXA_ANONIMIZADA = "baixa_anonimizada"
    MODERADA_ANONIMIZADA = "moderada_anonimizada"
    SENSIVEL_RESTRITA = "sensivel_restrita"
    PII_PROIBIDA = "pii_proibida"


class VariavelPreditivaContrato(BaseModel):
    """Descritor formal obrigatório de uma variável do contrato preditivo do Vértice."""

    nome: str = Field(..., min_length=2, max_length=100)
    origem: str = Field(..., min_length=2, max_length=150)
    tipo: str = Field(..., min_length=2, max_length=50)
    descricao: str = Field(..., min_length=5, max_length=300)
    disponibilidade_temporal: DisponibilidadeTemporalVariavel
    sensibilidade: SensibilidadeVariavel
    elegivel_predicao: bool
    uso_exclusivo_alvo_supervisionado: bool = False

    @field_validator("nome", "origem", "tipo", "descricao")
    @classmethod
    def _exigir_nao_vazio(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Campo obrigatório do contrato de variável não pode ser vazio.")
        return s


def normalizar_chave_politica(chave: str) -> str:
    """
    Normaliza nomes de campos removendo acentuação Unicode (NFKD),
    convertendo para minúsculas e unificando espaços/hífens/barras em `_`.
    Preserva pontos `.` apenas quando usados para separar caminhos aninhados se solicitado.
    """
    texto_nfkd = unicodedata.normalize("NFKD", str(chave or ""))
    sem_acentos = "".join(
        ch for ch in texto_nfkd if not unicodedata.combining(ch)
    )
    limpo = re.sub(r"[\s\-/]+", "_", sem_acentos.strip().lower())
    limpo = re.sub(r"[^a-z0-9_]", "_", limpo)
    limpo = re.sub(r"_+", "_", limpo).strip("_")
    return limpo


# ==============================================================================
# CATÁLOGO OFICIAL DE VARIÁVEIS ELEGÍVEIS (SEM LEAKAGE E SEM PII)
# ==============================================================================
CATALOGO_VARIAVEIS_PREDITIVAS: tuple[VariavelPreditivaContrato, ...] = (
    VariavelPreditivaContrato(
        nome="frequencia_percentual",
        origem="boletins_periodo / notas_disciplinas",
        tipo="float",
        descricao="Percentual de presença acumulado até a data de corte da previsão.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="faltas",
        origem="boletins_periodo",
        tipo="int",
        descricao="Total de faltas registradas no período até o momento da extração.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="media_geral",
        origem="boletins_periodo",
        tipo="float",
        descricao="Média parcial das avaliações disponíveis antes do fechamento do período.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="notas_baixas",
        origem="boletins_periodo",
        tipo="int",
        descricao="Quantidade de componentes com rendimento abaixo do esperado até o corte.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="historico_reprovacoes",
        origem="estudantes / boletins_periodo",
        tipo="int",
        descricao="Acumulado histórico de reprovações em anos/períodos anteriores.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.HISTORICO_ANTERIOR,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="participacao_recuperacao",
        origem="boletins_periodo",
        tipo="bool",
        descricao="Indicador de participação em ações de recuperação paralela até o corte.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="atrasos",
        origem="boletins_periodo",
        tipo="int",
        descricao="Quantidade de atrasos registrados até a data de corte.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="idade",
        origem="boletins_periodo",
        tipo="int",
        descricao="Idade do estudante no ano letivo de referência.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.INICIO_PERIODO,
        sensibilidade=SensibilidadeVariavel.MODERADA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="taxa_entrega_atividades",
        origem="entregas_atividade",
        tipo="float",
        descricao="Percentual de atividades entregues sobre o total de entregas esperadas até o corte.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="entregas_atrasadas",
        origem="entregas_atividade",
        tipo="int",
        descricao="Quantidade de entregas realizadas após a data limite até o corte.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="nao_entregas_apos_prazo",
        origem="entregas_atividade",
        tipo="int",
        descricao="Quantidade de atividades vencidas ainda não entregues até a data de corte.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="taxa_acerto_avaliacoes",
        origem="respostas_avaliacao",
        tipo="float",
        descricao="Percentual de acertos em avaliações aplicadas até a data de corte.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
    VariavelPreditivaContrato(
        nome="respostas_em_branco",
        origem="respostas_avaliacao",
        tipo="int",
        descricao="Contagem de questões deixadas em branco em avaliações até a data de corte.",
        disponibilidade_temporal=DisponibilidadeTemporalVariavel.ATE_DATA_CORTE,
        sensibilidade=SensibilidadeVariavel.BAIXA_ANONIMIZADA,
        elegivel_predicao=True,
    ),
)

# Contrato documentado da variável-alvo futura (NUNCA elegível como entrada de predição)
CONTRATO_ALVO_SUPERVISIONADO_SITUACAO_FINAL = VariavelPreditivaContrato(
    nome="situacao_final",
    origem="boletins_periodo",
    tipo="enum(Aprovado|Reprovado|Evadido)",
    descricao=(
        "Variável-alvo exclusiva para rotulagem histórica em futuro treinamento supervisionado; "
        "proibida como entrada para gerar previsões."
    ),
    disponibilidade_temporal=DisponibilidadeTemporalVariavel.POS_DESFECHO,
    sensibilidade=SensibilidadeVariavel.SENSIVEL_RESTRITA,
    elegivel_predicao=False,
    uso_exclusivo_alvo_supervisionado=True,
)


# ==============================================================================
# LISTA EXPLÍCITA E EXTENSÍVEL DE VARIÁVEIS PROIBIDAS (LEAKAGE & PII)
# ==============================================================================
CAMPOS_DESFECHO_E_LEAKAGE: dict[str, str] = {
    "situacao_final": "Variável-alvo exclusiva de treinamento futuro; uso como entrada causa data leakage.",
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
    "nome_estudante": "Dado pessoal identificável (LGPD).",
    "nome_aluno": "Dado pessoal identificável (LGPD).",
    "nome_mae": "Dado pessoal identificável (LGPD).",
    "nome_pai": "Dado pessoal identificável (LGPD).",
    "nome_responsavel": "Dado pessoal identificável (LGPD).",
    "cpf": "Dado pessoal identificável (LGPD).",
    "rg": "Dado pessoal identificável (LGPD).",
    "email": "Dado de contato pessoal identificável (LGPD).",
    "telefone": "Dado de contato pessoal identificável (LGPD).",
    "celular": "Dado de contato pessoal identificável (LGPD).",
    "endereco": "Dado residencial identificável (LGPD).",
    "data_nascimento": "Dado pessoal sensível identificável (LGPD).",
}

CAMPOS_PROIBIDOS_PREDICAO: dict[str, str] = {
    **CAMPOS_DESFECHO_E_LEAKAGE,
    **CAMPOS_PII_PROIBIDOS_PREDICAO,
}

# Agrupadores neutros aceitos quando um dicionário aninha explicitamente features
CHAVES_AGRUPADORAS_VARIAVEIS: frozenset[str] = frozenset(
    {
        "features",
        "variaveis",
        "variaveis_entrada",
        "entradas",
        "atributos",
    }
)


class ResultadoValidacaoLeakage(BaseModel):
    """Resultado estruturado da inspeção rigorosa contra vazamento de dados."""

    valido: bool
    variaveis_analisadas: list[str] = Field(default_factory=list)
    variaveis_permitidas_reconhecidas: list[str] = Field(default_factory=list)
    variaveis_proibidas_detectadas: dict[str, str] = Field(default_factory=dict)
    variaveis_desconhecidas_rejeitadas: dict[str, str] = Field(default_factory=dict)
    variaveis_nao_elegiveis_rejeitadas: dict[str, str] = Field(default_factory=dict)
    aviso_politica: str = (
        "Apenas variáveis com contrato formal válido, disponibilidade anterior/até a data de corte "
        "e elegibilidade explícita são aceitas como entrada. `situacao_final`, campos pós-desfecho, PII "
        "e variáveis desconhecidas sem contrato são rejeitados."
    )


def _motivo_proibicao_por_nome(
    chave_norm: str,
    mapa_proibidos: Mapping[str, str],
) -> Optional[str]:
    if not chave_norm:
        return None
    if chave_norm in mapa_proibidos:
        return mapa_proibidos[chave_norm]
    tokens = chave_norm.split("_")
    for termo_proibido, motivo in mapa_proibidos.items():
        if termo_proibido == chave_norm:
            return motivo
        if termo_proibido in tokens:
            return motivo
        if (
            len(termo_proibido) >= 5
            and (
                chave_norm.startswith(f"{termo_proibido}_")
                or chave_norm.endswith(f"_{termo_proibido}")
                or f"_{termo_proibido}_" in chave_norm
            )
        ):
            return motivo
    return None


def _contrato_e_elegivel(contrato: VariavelPreditivaContrato) -> tuple[bool, Optional[str]]:
    if not contrato.elegivel_predicao:
        return False, "Contrato declara explicitamente `elegivel_predicao=False`."
    if contrato.uso_exclusivo_alvo_supervisionado:
        return (
            False,
            "Variável marcada exclusivamente como alvo supervisionado futuro.",
        )
    if contrato.disponibilidade_temporal == DisponibilidadeTemporalVariavel.POS_DESFECHO:
        return (
            False,
            "Variável indisponível no momento da predição (`pos_desfecho`).",
        )
    if contrato.sensibilidade == SensibilidadeVariavel.PII_PROIBIDA:
        return False, "Variável classificada como PII proibida (LGPD)."
    return True, None


def _coletar_candidatos_variaveis(
    entrada: Any,
    caminho: str = "",
) -> list[tuple[str, str]]:
    """
    Retorna lista de pares `(nome_exibicao, nome_folha_para_contrato)`:
    - Para listas de strings: cada string é uma variável folha.
    - Para dicionários: inspeciona recursivamente todas as chaves e valores;
      chaves que apontam para sub-dicionários só atuam como container se forem
      chaves agrupadoras explícitas (`features`, `variaveis`, etc.), mas ainda
      têm seus nomes inspecionados contra a lista de bloqueio!
    """
    itens: list[tuple[str, str]] = []

    if isinstance(entrada, Mapping):
        for k, v in entrada.items():
            k_raw = str(k)
            caminho_atual = f"{caminho}.{k_raw}" if caminho else k_raw
            if isinstance(v, Mapping):
                itens.append((caminho_atual, k_raw))
                itens.extend(_coletar_candidatos_variaveis(v, caminho_atual))
            elif isinstance(v, (list, tuple)):
                itens.append((caminho_atual, k_raw))
                itens.extend(_coletar_candidatos_variaveis(v, caminho_atual))
            else:
                itens.append((caminho_atual, k_raw))
    elif isinstance(entrada, (list, tuple)):
        for elem in entrada:
            if isinstance(elem, (Mapping, list, tuple)):
                itens.extend(_coletar_candidatos_variaveis(elem, caminho))
            else:
                texto = str(elem)
                exib = f"{caminho}[{texto}]" if caminho else texto
                itens.append((exib, texto))
    elif isinstance(entrada, Iterable) and not isinstance(entrada, (str, bytes)):
        for elem in entrada:
            itens.extend(_coletar_candidatos_variaveis(elem, caminho))
    else:
        texto = str(entrada)
        itens.append((texto, texto))

    return itens


def validar_variaveis_contra_leakage(
    entrada: Mapping[str, Any] | Iterable[str],
    *,
    campos_proibidos_extras: Mapping[str, str] | Iterable[str] | None = None,
    catalogo_extensao: Iterable[VariavelPreditivaContrato | Mapping[str, Any]] | None = None,
    lancar_excecao: bool = True,
) -> ResultadoValidacaoLeakage:
    """
    Valida rigorosamente as variáveis preditivas de entrada:
    1) Bloqueia `situacao_final`, derivados pós-desfecho, PII e lista extensível.
    2) Exige contrato completo, temporalidade válida (`!= pos_desfecho`) e `elegivel_predicao=True`.
    3) Rejeita TODA variável desconhecida que não conste no catálogo oficial nem em
       `catalogo_extensao` com contrato válido.
    """
    mapa_proibidos = dict(CAMPOS_PROIBIDOS_PREDICAO)
    if isinstance(campos_proibidos_extras, Mapping):
        for k, motivo in campos_proibidos_extras.items():
            norm = normalizar_chave_politica(str(k))
            if norm:
                mapa_proibidos[norm] = str(motivo)
    elif campos_proibidos_extras is not None:
        for k in campos_proibidos_extras:
            norm = normalizar_chave_politica(str(k))
            if norm:
                mapa_proibidos[norm] = (
                    "Variável bloqueada pela política adicional de prevenção de leakage."
                )

    mapa_contratos: dict[str, VariavelPreditivaContrato] = {
        normalizar_chave_politica(c.nome): c for c in CATALOGO_VARIAVEIS_PREDITIVAS
    }
    mapa_contratos[
        normalizar_chave_politica(CONTRATO_ALVO_SUPERVISIONADO_SITUACAO_FINAL.nome)
    ] = CONTRATO_ALVO_SUPERVISIONADO_SITUACAO_FINAL

    contratos_invalidos_extensao: dict[str, str] = {}
    if catalogo_extensao is not None:
        for raw_contrato in catalogo_extensao:
            try:
                contrato = (
                    raw_contrato
                    if isinstance(raw_contrato, VariavelPreditivaContrato)
                    else VariavelPreditivaContrato.model_validate(raw_contrato)
                )
            except Exception as exc:  # noqa: BLE001
                nome_bad = (
                    str(raw_contrato.get("nome"))
                    if isinstance(raw_contrato, Mapping) and raw_contrato.get("nome")
                    else "contrato_incompleto"
                )
                contratos_invalidos_extensao[nome_bad] = (
                    f"Contrato de extensão incompleto ou inválido: {exc}"
                )
                continue
            norm_c = normalizar_chave_politica(contrato.nome)
            motivo_proib = _motivo_proibicao_por_nome(norm_c, mapa_proibidos)
            if motivo_proib is not None:
                contratos_invalidos_extensao[contrato.nome] = (
                    f"Extensão negada: nome `{contrato.nome}` colide com política proibida ({motivo_proib})."
                )
                continue
            mapa_contratos[norm_c] = contrato

    # Coleta estrutura mantendo distinção entre nó container e variável folha
    analisadas: list[str] = []
    reconhecidas: list[str] = []
    proibidas_detectadas: dict[str, str] = {}
    desconhecidas_rejeitadas: dict[str, str] = {}
    nao_elegiveis_rejeitadas: dict[str, str] = dict(contratos_invalidos_extensao)

    def _inspecionar(obj: Any, caminho: str = "") -> None:
        if isinstance(obj, Mapping):
            for k, v in obj.items():
                k_raw = str(k)
                k_norm = normalizar_chave_politica(k_raw)
                caminho_atual = f"{caminho}.{k_raw}" if caminho else k_raw
                analisadas.append(caminho_atual)

                motivo_proib = _motivo_proibicao_por_nome(k_norm, mapa_proibidos)
                if motivo_proib is not None:
                    proibidas_detectadas[caminho_atual] = motivo_proib

                if isinstance(v, (Mapping, list, tuple)):
                    # Se não for uma chave agrupadora conhecida nem estiver proibida/catalogada,
                    # rejeita também chave container desconhecida quando for folha/dict aninhado suspeito
                    if (
                        motivo_proib is None
                        and k_norm not in CHAVES_AGRUPADORAS_VARIAVEIS
                        and k_norm not in mapa_contratos
                    ):
                        desconhecidas_rejeitadas[caminho_atual] = (
                            f"Estrutura aninhada `{k_raw}` não reconhecida no catálogo de variáveis elegíveis."
                        )
                    _inspecionar(v, caminho_atual)
                else:
                    if motivo_proib is None:
                        _avaliar_variavel(caminho_atual, k_norm)
        elif isinstance(obj, (list, tuple)):
            for idx, item in enumerate(obj):
                if isinstance(item, (Mapping, list, tuple)):
                    _inspecionar(item, f"{caminho}[{idx}]" if caminho else f"[{idx}]")
                else:
                    nome_var = str(item)
                    norm_var = normalizar_chave_politica(nome_var)
                    exib = f"{caminho}.{nome_var}" if caminho else nome_var
                    analisadas.append(exib)
                    motivo_proib = _motivo_proibicao_por_nome(norm_var, mapa_proibidos)
                    if motivo_proib is not None:
                        proibidas_detectadas[exib] = motivo_proib
                    else:
                        _avaliar_variavel(exib, norm_var)

    def _avaliar_variavel(nome_exib: str, norm_var: str) -> None:
        if not norm_var:
            desconhecidas_rejeitadas[nome_exib] = "Nome de variável vazio ou inválido."
            return
        contrato = mapa_contratos.get(norm_var)
        if contrato is None:
            desconhecidas_rejeitadas[nome_exib] = (
                "Variável desconhecida sem contrato formal de elegibilidade no catálogo."
            )
            return
        ok, motivo_nao_elegivel = _contrato_e_elegivel(contrato)
        if not ok:
            nao_elegiveis_rejeitadas[nome_exib] = motivo_nao_elegivel or "Variável não elegível."
            return
        reconhecidas.append(nome_exib)

    if isinstance(entrada, Mapping) or isinstance(entrada, (list, tuple)):
        _inspecionar(entrada)
    else:
        _inspecionar(list(entrada))

    valido = (
        len(proibidas_detectadas) == 0
        and len(desconhecidas_rejeitadas) == 0
        and len(nao_elegiveis_rejeitadas) == 0
    )

    resultado = ResultadoValidacaoLeakage(
        valido=valido,
        variaveis_analisadas=analisadas,
        variaveis_permitidas_reconhecidas=reconhecidas,
        variaveis_proibidas_detectadas=proibidas_detectadas,
        variaveis_desconhecidas_rejeitadas=desconhecidas_rejeitadas,
        variaveis_nao_elegiveis_rejeitadas=nao_elegiveis_rejeitadas,
    )

    if not resultado.valido and lancar_excecao:
        partes_erro: list[str] = []
        if proibidas_detectadas:
            nomes_proib = ", ".join(sorted(proibidas_detectadas.keys()))
            partes_erro.append(
                f"variável(is) proibida(s) (data leakage / LGPD): {nomes_proib}"
            )
        if nao_elegiveis_rejeitadas:
            nomes_ne = ", ".join(sorted(nao_elegiveis_rejeitadas.keys()))
            partes_erro.append(f"variável(is) não elegível(is): {nomes_ne}")
        if desconhecidas_rejeitadas:
            nomes_desc = ", ".join(sorted(desconhecidas_rejeitadas.keys()))
            partes_erro.append(
                f"variável(is) desconhecida(s) sem contrato válido: {nomes_desc}"
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Violação da política de elegibilidade/data leakage na entrada preditiva: "
                + "; ".join(partes_erro)
                + "."
            ),
        )

    return resultado


# ==============================================================================
# CONTRATO ESTRITO DE METADADOS TÉCNICOS OPERACIONAIS
# ==============================================================================
class TipoMetadadoTecnico(str, Enum):
    """Tipos escalares/estruturais permitidos para metadados técnicos operacionais."""

    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIMIARES_DICT = "limiares_dict"


class MetadadoTecnicoContrato(BaseModel):
    """Descritor formal de um campo operacional permitido em `metadados_tecnicos`."""

    nome: str = Field(..., min_length=2, max_length=80)
    tipo: TipoMetadadoTecnico
    descricao: str = Field(..., min_length=5, max_length=250)
    max_length: int = Field(default=120, ge=1, le=200)
    expor_na_api: bool = True


CATALOGO_METADADOS_TECNICOS_PERMITIDOS: tuple[MetadadoTecnicoContrato, ...] = (
    MetadadoTecnicoContrato(
        nome="pipeline_execucao_id",
        tipo=TipoMetadadoTecnico.STR,
        descricao="Identificador técnico da execução externa no pipeline de ML.",
        max_length=120,
    ),
    MetadadoTecnicoContrato(
        nome="framework_ml",
        tipo=TipoMetadadoTecnico.STR,
        descricao="Biblioteca ou runtime técnico do modelo (ex.: xgboost, lightgbm, scikit-learn).",
        max_length=60,
    ),
    MetadadoTecnicoContrato(
        nome="origem_pipeline",
        tipo=TipoMetadadoTecnico.STR,
        descricao="Identificador técnico do job/orquestrador sem dados pedagógicos.",
        max_length=80,
    ),
    MetadadoTecnicoContrato(
        nome="data_corte_extracao",
        tipo=TipoMetadadoTecnico.STR,
        descricao="Timestamp ou data ISO de corte temporal dos dados usados na execução.",
        max_length=40,
    ),
    MetadadoTecnicoContrato(
        nome="janela_corte_dias",
        tipo=TipoMetadadoTecnico.INT,
        descricao="Janela temporal em dias considerada na extração das features.",
    ),
    MetadadoTecnicoContrato(
        nome="limiar_decisao",
        tipo=TipoMetadadoTecnico.FLOAT,
        descricao="Threshold numérico principal aplicado pelo pipeline [0.0..1.0].",
    ),
    MetadadoTecnicoContrato(
        nome="calibracao_aplicada",
        tipo=TipoMetadadoTecnico.BOOL,
        descricao="Indica se a probabilidade passou por etapa de calibração.",
    ),
    MetadadoTecnicoContrato(
        nome="tempo_inferencia_ms",
        tipo=TipoMetadadoTecnico.FLOAT,
        descricao="Tempo técnico de inferência em milissegundos.",
    ),
    MetadadoTecnicoContrato(
        nome="hash_artefato_modelo",
        tipo=TipoMetadadoTecnico.STR,
        descricao="Resumo SHA-256 ou identificador imutável do artefato serializado.",
        max_length=128,
    ),
    MetadadoTecnicoContrato(
        nome="politica_limiares",
        tipo=TipoMetadadoTecnico.LIMIARES_DICT,
        descricao="Limiares numéricos operacionais de conversão de pontuação em faixas.",
    ),
)

CHAVES_LIMIARES_PERMITIDAS: frozenset[str] = frozenset(
    {"baixo_max", "moderado_max", "alto_max", "critico_min"}
)

CHAVES_SEGREDOS_E_CONTEUDO_BLOQUEADO_METADADOS: frozenset[str] = frozenset(
    {
        *CAMPOS_PROIBIDOS_PREDICAO.keys(),
        "token",
        "access_token",
        "refresh_token",
        "service_token",
        "x_service_token",
        "authorization",
        "auth",
        "jwt",
        "bearer",
        "senha",
        "password",
        "secret",
        "chave_secreta",
        "api_key",
        "apikey",
        "prompt",
        "mensagens",
        "conversa",
        "observacao_pedagogica",
        "relato_pedagogico",
        "features",
        "variaveis",
        "variaveis_entrada",
        "variaveis_utilizadas",
        "payload_bruto",
    }
)

_PADROES_VALOR_SENSIVEL: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bBearer\s+[A-Za-z0-9\-_\.]+", re.IGNORECASE), "token Bearer"),
    (re.compile(r"\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"), "token JWT"),
    (re.compile(r"\bvtx_ml_[A-Za-z0-9\-_]+"), "credencial técnica de serviço"),
    (
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "endereço de e-mail pessoal (LGPD)",
    ),
    (
        re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
        "possível número de CPF (LGPD)",
    ),
    (
        re.compile(
            r"\b(password|senha|secret|api_key|access_token)\b\s*[:=]",
            re.IGNORECASE,
        ),
        "referência a segredo ou credencial",
    ),
)


class ResultadoValidacaoMetadados(BaseModel):
    """Resultado estruturado da inspeção do contrato de `metadados_tecnicos`."""

    valido: bool
    metadados_aprovados: dict[str, Any] = Field(default_factory=dict)
    campos_rejeitados: dict[str, str] = Field(default_factory=dict)


def _valor_contem_conteudo_inseguro(valor: Any) -> Optional[str]:
    if isinstance(valor, str):
        for padrao, desc in _PADROES_VALOR_SENSIVEL:
            if padrao.search(valor):
                return f"Valor contém padrão proibido ({desc})."
    elif isinstance(valor, Mapping):
        for k, v in valor.items():
            motivo = _valor_contem_conteudo_inseguro(v)
            if motivo:
                return motivo
            norm_k = normalizar_chave_politica(str(k))
            if norm_k in CHAVES_SEGREDOS_E_CONTEUDO_BLOQUEADO_METADADOS:
                return f"Chave interna `{k}` proibida nos metadados técnicos."
    elif isinstance(valor, (list, tuple)):
        for elem in valor:
            motivo = _valor_contem_conteudo_inseguro(elem)
            if motivo:
                return motivo
    return None


def _validar_valor_contrato_metadado(
    contrato: MetadadoTecnicoContrato,
    valor: Any,
) -> tuple[bool, Any, Optional[str]]:
    if valor is None:
        return True, None, None

    motivo_seg = _valor_contem_conteudo_inseguro(valor)
    if motivo_seg:
        return False, None, motivo_seg

    if contrato.tipo == TipoMetadadoTecnico.STR:
        if not isinstance(valor, str):
            return False, None, "Esperado valor textual (`str`)."
        s = valor.strip()
        if len(s) > contrato.max_length:
            return (
                False,
                None,
                f"Texto excede limite máximo permitido ({contrato.max_length} caracteres).",
            )
        return True, s, None

    if contrato.tipo == TipoMetadadoTecnico.INT:
        if isinstance(valor, bool) or not isinstance(valor, int):
            return False, None, "Esperado número inteiro (`int`)."
        return True, int(valor), None

    if contrato.tipo == TipoMetadadoTecnico.FLOAT:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return False, None, "Esperado número real (`float`)."
        f = float(valor)
        if math.isnan(f) or math.isinf(f):
            return False, None, "Valor numérico inválido (NaN/Inf)."
        return True, f, None

    if contrato.tipo == TipoMetadadoTecnico.BOOL:
        if not isinstance(valor, bool):
            return False, None, "Esperado valor booleano (`bool`)."
        return True, valor, None

    if contrato.tipo == TipoMetadadoTecnico.LIMIARES_DICT:
        if not isinstance(valor, Mapping):
            return False, None, "Esperado objeto mapeado com limiares operacionais."
        aprovado_sub: dict[str, float] = {}
        for sk, sv in valor.items():
            sk_norm = normalizar_chave_politica(str(sk))
            if sk_norm in CHAVES_SEGREDOS_E_CONTEUDO_BLOQUEADO_METADADOS:
                return False, None, f"Chave proibida `{sk}` dentro de `{contrato.nome}`."
            if sk_norm not in CHAVES_LIMIARES_PERMITIDAS:
                return (
                    False,
                    None,
                    f"Subcampo desconhecido `{sk}` em `{contrato.nome}`. Permitidos: {sorted(CHAVES_LIMIARES_PERMITIDAS)}.",
                )
            if isinstance(sv, bool) or not isinstance(sv, (int, float)):
                return False, None, f"Limiar `{sk}` deve ser numérico."
            fv = float(sv)
            if math.isnan(fv) or math.isinf(fv) or fv < 0.0 or fv > 1.0:
                return False, None, f"Limiar `{sk}` deve estar entre 0.0 e 1.0."
            aprovado_sub[sk_norm] = fv
        return True, aprovado_sub, None

    return False, None, "Tipo de contrato de metadado não suportado."


def validar_metadados_tecnicos(
    metadados: Optional[Mapping[str, Any]],
    *,
    catalogo_extensao: Iterable[MetadadoTecnicoContrato] | None = None,
    lancar_excecao: bool = True,
) -> ResultadoValidacaoMetadados:
    """
    Valida `metadados_tecnicos` contra contrato fechado de rastreabilidade operacional.
    Rejeita chaves desconhecidas, estruturas arbitrárias, tokens/segredos, PII,
    informações de leakage e contrabando de variáveis preditivas.
    """
    if metadados is None:
        return ResultadoValidacaoMetadados(valido=True, metadados_aprovados={})

    if not isinstance(metadados, Mapping):
        if lancar_excecao:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="`metadados_tecnicos` deve ser um objeto JSON chave-valor compatível com o contrato.",
            )
        return ResultadoValidacaoMetadados(
            valido=False,
            campos_rejeitados={"metadados_tecnicos": "Formato inválido (esperado dicionário)."},
        )

    mapa_contratos: dict[str, MetadadoTecnicoContrato] = {
        normalizar_chave_politica(c.nome): c
        for c in CATALOGO_METADADOS_TECNICOS_PERMITIDOS
    }
    if catalogo_extensao is not None:
        for ext in catalogo_extensao:
            norm_ext = normalizar_chave_politica(ext.nome)
            if (
                norm_ext not in CHAVES_SEGREDOS_E_CONTEUDO_BLOQUEADO_METADADOS
                and _motivo_proibicao_por_nome(norm_ext, CAMPOS_PROIBIDOS_PREDICAO) is None
            ):
                mapa_contratos[norm_ext] = ext

    aprovados: dict[str, Any] = {}
    rejeitados: dict[str, str] = {}

    for k_raw, valor in metadados.items():
        k_str = str(k_raw)
        k_norm = normalizar_chave_politica(k_str)

        if (
            k_norm in CHAVES_SEGREDOS_E_CONTEUDO_BLOQUEADO_METADADOS
            or _motivo_proibicao_por_nome(k_norm, CAMPOS_PROIBIDOS_PREDICAO) is not None
        ):
            rejeitados[k_str] = (
                "Campo proibido por política anti-leakage, LGPD ou proteção de segredos."
            )
            continue

        contrato = mapa_contratos.get(k_norm)
        if contrato is None:
            rejeitados[k_str] = (
                "Campo de metadado desconhecido ou sem contrato operacional aprovado."
            )
            continue

        ok, valor_limpo, motivo_val = _validar_valor_contrato_metadado(contrato, valor)
        if not ok:
            rejeitados[k_str] = motivo_val or "Valor incompatível com o contrato técnico."
            continue

        # Caso valor contenha objetos aninhados em futuros extensíveis, ainda verifica recursivamente leakage
        if isinstance(valor, (Mapping, list, tuple)):
            motivo_aninhado = _valor_contem_conteudo_inseguro(valor)
            if motivo_aninhado:
                rejeitados[k_str] = motivo_aninhado
                continue

        aprovados[contrato.nome] = valor_limpo

    res = ResultadoValidacaoMetadados(
        valido=len(rejeitados) == 0,
        metadados_aprovados=aprovados,
        campos_rejeitados=rejeitados,
    )
    if not res.valido and lancar_excecao:
        campos_bad = "; ".join(
            f"{k}: {rejeitados[k]}" for k in sorted(rejeitados.keys())
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Contrato de `metadados_tecnicos` violado: {campos_bad}",
        )
    return res


def sanitizar_metadados_tecnicos_resposta(
    metadados: Optional[Mapping[str, Any]],
) -> Optional[dict[str, Any]]:
    """
    Garante que respostas da API exponham exclusivamente metadados técnicos
    aprovados no contrato oficial (`expor_na_api=True`), filtrando qualquer campo
    desconhecido ou inseguro eventualmente presente em registros antigos.
    """
    if not metadados:
        return None
    contratos_expostos = {
        normalizar_chave_politica(c.nome): c
        for c in CATALOGO_METADADOS_TECNICOS_PERMITIDOS
        if c.expor_na_api
    }
    seguros: dict[str, Any] = {}
    for k_raw, valor in metadados.items():
        k_norm = normalizar_chave_politica(str(k_raw))
        contrato = contratos_expostos.get(k_norm)
        if contrato is None:
            continue
        ok, valor_limpo, _ = _validar_valor_contrato_metadado(contrato, valor)
        if ok:
            seguros[contrato.nome] = valor_limpo
    return seguros or None
