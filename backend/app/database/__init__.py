"""
Módulo de banco de dados. Exporta o Base ORM, modelos registrados e o gerenciador de sessões.
"""

from app.database.base import Base
from app.database.connection import (
    SessionLocal,
    check_database_connection,
    engine,
    get_db,
)

# Importa todos os modelos ORM para registro nos metadados do SQLAlchemy / Alembic
from app.modules.acompanhamento.models import (
    AcompanhamentoPedagogico,
    OrigemAcompanhamento,
)
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.avaliacoes.models import (
    Avaliacao,
    FaixaDificuldadeQuestao,
    QuestaoAvaliacao,
    RespostaAvaliacao,
    StatusAvaliacao,
    TipoQuestao,
)
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
    NotaDisciplina,
    SituacaoFinalPeriodo,
)
from app.modules.importacao.models import (
    LoteImportacao,
    StatusLoteImportacao,
    TipoImportacao,
)
from app.modules.participacao.models import (
    Atividade,
    EntregaAtividade,
    StatusAtividade,
    StatusEntregaAtividade,
)
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario

__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "get_db",
    "check_database_connection",
    "Usuario",
    "PapelUsuario",
    "Escola",
    "Turma",
    "Disciplina",
    "ProfessorTurma",
    "Estudante",
    "BoletimPeriodo",
    "NotaDisciplina",
    "SituacaoFinalPeriodo",
    "LoteImportacao",
    "StatusLoteImportacao",
    "TipoImportacao",
    "Avaliacao",
    "QuestaoAvaliacao",
    "RespostaAvaliacao",
    "StatusAvaliacao",
    "TipoQuestao",
    "FaixaDificuldadeQuestao",
    "Atividade",
    "EntregaAtividade",
    "StatusAtividade",
    "StatusEntregaAtividade",
    "AcompanhamentoPedagogico",
    "OrigemAcompanhamento",
]
