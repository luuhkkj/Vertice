"""Estruturas vazias aguardando os dados do backend."""
import pandas as pd

SERIES = []
TURMAS = []
TURNOS = ["Matutino", "Vespertino"]
NIVEIS_RISCO = ["Baixo", "Atenção", "Alto"]
STATUS_POR_RISCO = {"Baixo": "Estável", "Atenção": "Atenção", "Alto": "Risco"}
DISCIPLINAS = []
TURMAS_AVALIACAO = []
TURMAS_ATRIBUICAO = []
TURMAS_PARTICIPACAO = []
PROFESSORES = []
EMAILS_PROFESSORES = {}
ATRIBUICOES_INICIAIS = []
TIPOS_QUESTAO = ["Objetivas", "Discursivas"]
ATIVIDADES = []
PERIODOS = []
ESTUDANTES = pd.DataFrame(columns=["Identificador", "Série", "Turma", "Turno", "Frequência", "Média geral", "Risco", "Status"])
DETALHE_ALUNOS = pd.DataFrame(columns=["Estudante", "Turno", "Entregas", "Porcentagem de entregas", "Status"])
DESEMPENHO_QUESTOES = pd.DataFrame(columns=["Questão", "Dificuldade", "Acertos", "Erros", "Em branco", "Ação sugerida", "Acerto (%)"])
RESPOSTAS_POR_QUESTAO = []
TOTAL_RESPONDENTES = 0
TOTAL_ATIVIDADES_POR_ALUNO = 0
INTERPRETACAO_POR_DIFICULDADE = {
    "Fácil": "O percentual de acertos foi elevado.",
    "Adequada": "O percentual de acertos foi satisfatório.",
    "Atenção": "Esta questão requer acompanhamento.",
    "Difícil": "Esta questão indica maior dificuldade.",
}

def _classificar_entrega(percentual):
    if percentual >= 90: return "Ótima"
    if percentual >= 70: return "Boa"
    if percentual >= 50: return "Atenção"
    return "Crítica"

def _classificar_status_entrega(percentual):
    if percentual >= 75: return "Estável"
    if percentual >= 50: return "Atenção"
    return "Risco"
