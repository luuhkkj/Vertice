"""Dados de exemplo. Quando o backend existir, só este arquivo será trocado."""
import random

import pandas as pd

# Visão geral
PERIODO_ATUAL = "Período: 2026 • Ensino Médio • Todas as turmas"

# Cada KPI: (valor, rótulo, rodapé)
KPIS_VISAO_GERAL = [
    ("1.248", "Total de estudantes", "+2,5% em relação ao período anterior"),
    ("82,1%", "Frequência média", "Abaixo da meta de 85%"),
    ("200", "Estudantes em atenção", "Abaixo da meta de 85%"),
    ("248", "Alto risco identificado", "3 novos alertas nessa semana"),
]

MESES = ["Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set"]

FREQUENCIA_POR_SERIE = pd.DataFrame({
    "Mês": MESES * 3,
    "Série": ["1º ano"] * 8 + ["2º ano"] * 8 + ["3º ano"] * 8,
    "Frequência (%)": [
        88, 86, 85, 83, 80, 82, 81, 84,
        84, 82, 79, 80, 77, 78, 80, 79,
        79, 80, 82, 78, 75, 74, 77, 76,
    ],
})

DISTRIBUICAO_RISCO = pd.DataFrame({
    "Nível de risco": ["Baixo", "Atenção", "Alto"],
    "Estudantes": [800, 200, 248],
})

ALTO_RISCO_POR_SERIE = pd.DataFrame({
    "Série": ["1º ano", "2º ano", "3º ano"],
    "Estudantes em alto risco": [110, 85, 53],
})


def _gerar_notas_e_frequencia(quantidade=80):
    """Gera pontos de exemplo: quanto maior a frequência, maior a nota."""
    sorteio = random.Random(42)  # semente fixa: o gráfico não muda a cada recarga
    frequencias = [sorteio.uniform(45, 100) for _ in range(quantidade)]
    notas = [max(0, min(10, f / 12 + sorteio.uniform(-1.5, 1.5))) for f in frequencias]
    return pd.DataFrame({"Frequência (%)": frequencias, "Média geral": notas})


NOTAS_X_FREQUENCIA = _gerar_notas_e_frequencia()

ESTUDANTES_EM_ATENCAO = pd.DataFrame({
    "ID anonimizado": ["A00400120655", "A00400120712", "A00400120834", "A00400121003", "A00400121198"],
    "Série/Turma": ["Ensino Médio - A", "Ensino Médio - B", "Ensino Médio - A", "Ensino Médio - C", "Ensino Médio - B"],
    "Frequência": ["77,5%", "72,0%", "68,3%", "61,4%", "58,9%"],
    "Média geral": ["6,9", "6,1", "5,8", "4,8", "4,5"],
    "Nível de risco": ["Atenção", "Atenção", "Atenção", "Alto", "Alto"],
})



# Estudantes
SERIES = ["1º ano", "2º ano", "3º ano"]
TURMAS = ["A", "B", "C"]
TURNOS = ["Matutino", "Vespertino"]
NIVEIS_RISCO = ["Baixo", "Atenção", "Alto"]
STATUS_POR_RISCO = {"Baixo": "Estável", "Atenção": "Atenção", "Alto": "Risco"}

# (quantidade, faixa de frequência, faixa de média) de cada nível de risco.
# As quantidades somam os 1.248 estudantes da Visão geral.
_PERFIL_POR_RISCO = {
    "Baixo": (800, (82, 100), (6.5, 9.5)),
        "Atenção": (200, (70, 85), (5.0, 7.0)),
    "Alto": (248, (45, 70), (2.5, 5.5)),
}


def _gerar_estudantes():
    """Cria a lista de estudantes de exemplo (sempre a mesma, por causa da semente)."""
    sorteio = random.Random(7)
    linhas = []
    for risco, (quantidade, faixa_freq, faixa_media) in _PERFIL_POR_RISCO.items():
        for _ in range(quantidade):
            linhas.append({
                "Série": sorteio.choice(SERIES),
                "Turma": sorteio.choice(TURMAS),
                "Turno": sorteio.choice(TURNOS),
                "Frequência": round(sorteio.uniform(*faixa_freq), 1),
                "Média geral": round(sorteio.uniform(*faixa_media), 1),
                "Risco": risco,
                "Status": STATUS_POR_RISCO[risco],
            })
    sorteio.shuffle(linhas)
    estudantes = pd.DataFrame(linhas)
    estudantes.insert(0, "Identificador", [f"EST-{numero:04d}" for numero in range(1, len(estudantes) + 1)])
    return estudantes


ESTUDANTES = _gerar_estudantes()


# Calculado a partir da lista de Estudantes, para o gráfico da Visão geral bater com a tela Estudantes.
ALTO_RISCO_POR_SERIE = (
    ESTUDANTES[ESTUDANTES["Risco"] == "Alto"]
    .groupby("Série").size()
    .reindex(SERIES)
    .rename("Estudantes em alto risco")
    .reset_index()
)



# Assistente IA
MENSAGEM_BOAS_VINDAS = "Olá, Professor! No que você está pensando?"
RESPOSTA_SIMULADA = (
    "Esta é uma resposta de exemplo. Quando o assistente estiver conectado, "
    "a resposta aparecerá aqui."
)



# Mapa de Acertos
# Opções dos filtros. Por enquanto os dados abaixo são os mesmos para qualquer escolha.
AVALIACOES = ["Avaliação 1", "Avaliação 2", "Avaliação 3"]
DISCIPLINAS = ["Matemática", "Português", "Ciências", "História"]
TURMAS_AVALIACAO = ["2º B", "2º A", "3º A", "3º B"]
TIPOS_QUESTAO = ["Objetivas", "Discursivas"]

MEDIA_AVALIACAO = "7,0"
TOTAL_RESPONDENTES = 40


def _classificar_dificuldade(percentual_acerto):
    """Fácil >= 80%, Adequada >= 60%, Atenção >= 40%, Difícil abaixo disso."""
    if percentual_acerto >= 80:
        return "Fácil"
    if percentual_acerto >= 60:
        return "Adequada"
    if percentual_acerto >= 40:
        return "Atenção"
    return "Difícil"

# Respostas de cada questão: alternativa correta e quantos estudantes escolheram cada alternativa.
# Quem não aparece na soma deixou a questão em branco (o total é TOTAL_RESPONDENTES).
RESPOSTAS_POR_QUESTAO = [
    {"correta": "A", "respostas": {"A": 35, "B": 2, "C": 3, "D": 0}},
    {"correta": "C", "respostas": {"A": 3, "B": 2, "C": 30, "D": 2}},
    {"correta": "B", "respostas": {"A": 4, "B": 25, "C": 3, "D": 3}},
    {"correta": "D", "respostas": {"A": 7, "B": 6, "C": 4, "D": 20}},
    {"correta": "A", "respostas": {"A": 15, "B": 8, "C": 7, "D": 5}},
    {"correta": "B", "respostas": {"A": 12, "B": 10, "C": 9, "D": 8}},
    {"correta": "C", "respostas": {"A": 2, "B": 3, "C": 32, "D": 1}},
    {"correta": "D", "respostas": {"A": 4, "B": 3, "C": 3, "D": 28}},
    {"correta": "A", "respostas": {"A": 18, "B": 9, "C": 6, "D": 4}},
    {"correta": "B", "respostas": {"A": 6, "B": 22, "C": 5, "D": 4}},
]

# Texto do painel de detalhes. {correta} e {errada_mais_escolhida} são trocados pela letra.
INTERPRETACAO_POR_DIFICULDADE = {
    "Fácil": (
        "A alternativa {correta} foi escolhida pela maioria dos estudantes e é a alternativa correta. "
        "Isso pode indicar que não há dificuldades na interpretação dos estudantes."
    ),
    "Adequada": (
        "A maioria dos estudantes acertou a questão (alternativa {correta}). "
        "O nível de dificuldade parece adequado para a turma."
    ),
    "Atenção": (
        "Cerca de metade dos estudantes não acertou a questão. "
        "A alternativa errada mais escolhida foi a {errada_mais_escolhida}."
    ),
    "Difícil": (
        "A maioria dos estudantes não acertou a questão. A alternativa errada mais escolhida foi a "
        "{errada_mais_escolhida}, o que pode indicar uma dificuldade com este conteúdo."
    ),
}


def _montar_desempenho_questoes():
    """Calcula acertos, erros, em branco, percentual e dificuldade a partir das respostas."""
    linhas = []
    for numero, questao in enumerate(RESPOSTAS_POR_QUESTAO, start=1):
        acertos = questao["respostas"][questao["correta"]]
        erros = sum(questao["respostas"].values()) - acertos
        em_branco = TOTAL_RESPONDENTES - acertos - erros
        percentual = acertos / TOTAL_RESPONDENTES * 100
        dificuldade = _classificar_dificuldade(percentual)
        linhas.append({
            "Questão": f"Questão {numero}",
            "Dificuldade": dificuldade,
            "Acertos": acertos,
            "Erros": erros,
            "Em branco": em_branco,
            "Ação sugerida": "Nenhuma" if dificuldade in ("Fácil", "Adequada") else "Ação sugerida",
            "Acerto (%)": percentual,
        })
    return pd.DataFrame(linhas)


DESEMPENHO_QUESTOES = _montar_desempenho_questoes()



# Participação
# Opções dos filtros. Por enquanto os dados abaixo são os mesmos para qualquer escolha.
ATIVIDADES = ["Atividade 1", "Atividade 2", "Atividade 3", "Atividade 4"]
TURMAS_PARTICIPACAO = ["1º A", "2º A", "2º B", "3º A", "3º B"]
PERIODOS = ["Último mês", "Último bimestre", "Ano letivo"]

# Indicadores da atividade escolhida
ENTREGARAM = 80
TOTAL_ALUNOS_ATIVIDADE = 100
VARIACAO_TAXA_ENTREGA = "+5% no período"
MEDIA_ATIVIDADE = "6,8"

TOTAL_ATIVIDADES_POR_ALUNO = 4


def _classificar_entrega(percentual):
    """Ótima >= 90%, Boa >= 70%, Atenção >= 50%, Crítica abaixo disso."""
    if percentual >= 90:
        return "Ótima"
    if percentual >= 70:
        return "Boa"
    if percentual >= 50:
        return "Atenção"
    return "Crítica"


def _classificar_status_entrega(percentual):
    """Estável >= 75%, Atenção >= 50%, Risco abaixo disso."""
    if percentual >= 75:
        return "Estável"
    if percentual >= 50:
        return "Atenção"
    return "Risco"


_PERCENTUAL_ENTREGA_POR_TURMA = {"1º A": 92, "2º A": 84, "2º B": 71, "3º A": 60, "3º B": 30}

ENTREGA_POR_TURMA = pd.DataFrame({
    "Turma": list(_PERCENTUAL_ENTREGA_POR_TURMA),
    "Entrega (%)": list(_PERCENTUAL_ENTREGA_POR_TURMA.values()),
    "Situação": [_classificar_entrega(p) for p in _PERCENTUAL_ENTREGA_POR_TURMA.values()],
})

EVOLUCAO_PARTICIPACAO = pd.DataFrame({
    "Atividade": ATIVIDADES,
    "Participação (%)": [72, 78, 80, 74],
})


def _gerar_detalhe_alunos(quantidade=100):
    """Entregas de exemplo para os primeiros estudantes da lista de Estudantes.

    Usa os mesmos identificadores e turnos da tela Estudantes, para os dados baterem.
    """
    sorteio = random.Random(11)
    base = ESTUDANTES.head(quantidade)
    entregas = sorteio.choices(range(TOTAL_ATIVIDADES_POR_ALUNO + 1), weights=[1, 2, 3, 5, 6], k=len(base))
    percentuais = [e / TOTAL_ATIVIDADES_POR_ALUNO * 100 for e in entregas]
    return pd.DataFrame({
        "Estudante": base["Identificador"].values,
        "Turno": base["Turno"].values,
        "Entregas": entregas,
        "Porcentagem de entregas": percentuais,
        "Status": [_classificar_status_entrega(p) for p in percentuais],
    })


DETALHE_ALUNOS = _gerar_detalhe_alunos()



# Atribuição
PROFESSORES = ["Ana Souza", "Carlos Lima", "Marina Alves", "Paulo Ribeiro", "Fernanda Costa"]
TURMAS_ATRIBUICAO = TURMAS_PARTICIPACAO  # as mesmas turmas da escola

# Atribuições iniciais usadas enquanto os dados ainda não vêm do servidor.
ATRIBUICOES_INICIAIS = [
    {"Professor": "Ana Souza", "Disciplina": "Matemática", "Turma": "2º A"},
    {"Professor": "Ana Souza", "Disciplina": "Matemática", "Turma": "2º B"},
    {"Professor": "Carlos Lima", "Disciplina": "Português", "Turma": "3º A"},
    {"Professor": "Marina Alves", "Disciplina": "Ciências", "Turma": "1º A"},
]