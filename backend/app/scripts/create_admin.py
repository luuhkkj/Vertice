"""
Script CLI seguro para criação do primeiro usuário Administrador do sistema Vértice.
Recebe os dados por variáveis de ambiente (ADMIN_NOME, ADMIN_EMAIL, ADMIN_SENHA)
ou solicita de forma interativa com entrada protegida (getpass).
Não possui credenciais padrão fixas no código.
"""

import getpass
import os
import sys

# Garante que o diretório raiz do backend esteja no sys.path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.modules.usuarios.models import PapelUsuario, Usuario
from app.modules.usuarios.schemas import UsuarioCreate
from app.modules.usuarios.service import UsuarioService


def criar_administrador_inicial(
    db: Session, nome: str, email: str, senha: str
) -> Usuario:
    """
    Valida os dados e cria um usuário com papel `administrador` no banco de dados.
    """
    dados = UsuarioCreate(
        nome=nome,
        email=email,
        senha=senha,
        papel=PapelUsuario.ADMINISTRADOR,
        ativo=True,
    )
    return UsuarioService.criar_usuario(db, dados)


def main() -> int:
    print("=== Vértice: Criação de Administrador Inicial ===")

    nome = os.getenv("ADMIN_NOME", "").strip()
    email = os.getenv("ADMIN_EMAIL", "").strip()
    senha = os.getenv("ADMIN_SENHA", "")

    if not nome:
        nome = input("Nome do administrador: ").strip()
    if not email:
        email = input("E-mail do administrador: ").strip()
    if not senha:
        senha = getpass.getpass("Senha do administrador (mín. 6 caracteres): ")
        confirmacao = getpass.getpass("Confirme a senha: ")
        if senha != confirmacao:
            print("Erro: A confirmação de senha não confere.", file=sys.stderr)
            return 1

    if not nome or not email or not senha:
        print(
            "Erro: Nome, e-mail e senha são obrigatórios para criar o administrador.",
            file=sys.stderr,
        )
        return 1

    db = SessionLocal()
    try:
        admin = criar_administrador_inicial(db, nome=nome, email=email, senha=senha)
        print(
            f"Sucesso! Administrador '{admin.nome}' ({admin.email}) criado com ID: {admin.id}"
        )
        return 0
    except ValidationError as exc:
        print(f"Erro de validação nos dados informados:\n{exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        print(
            f"Erro de conexão/operação no banco de dados PostgreSQL: {exc}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        print(f"Erro ao criar administrador: {detail}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

