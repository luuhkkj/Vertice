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
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
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
]
