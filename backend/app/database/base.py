"""
Módulo base declarativo para modelos ORM com SQLAlchemy 2.
"""

from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """
    Classe base para todos os modelos ORM da aplicação Vértice.
    Modelos futuros herdam desta classe.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Gera automaticamente o nome da tabela a partir do nome da classe."""
        return cls.__name__.lower()

