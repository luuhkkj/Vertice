"""Formatação de números no padrão brasileiro (1.248 / 82,1 / 77%)."""


def numero_br(valor):
    """1248 -> '1.248'."""
    return f"{valor:,}".replace(",", ".")


def decimal_br(valor, casas=1):
    """7.8 -> '7,8'."""
    return f"{valor:.{casas}f}".replace(".", ",")


def percentual_br(valor, casas=0):
    """92.4 -> '92%'."""
    return f"{decimal_br(valor, casas)}%"