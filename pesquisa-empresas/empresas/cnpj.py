"""Validação, formatação e localização de CNPJs em texto (numérico e alfanumérico, IN RFB 2.229/2024)."""

import re

_PESOS1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS2 = [6] + _PESOS1

# Formatado (aceita letras nas 12 primeiras posições) ou 14 dígitos corridos.
_RE_FORMATADO = re.compile(
    r"(?<![0-9A-Za-z])([0-9A-Z]{2})\.?([0-9A-Z]{3})\.?([0-9A-Z]{3})\s?/\s?([0-9A-Z]{4})\s?-\s?(\d{2})(?![0-9A-Za-z])"
)
_RE_CORRIDO = re.compile(r"(?<![0-9])(\d{14})(?![0-9])")


def limpar(valor: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", (valor or "").upper())


def _dv(base: str, pesos: list[int]) -> int:
    soma = sum((ord(c) - 48) * p for c, p in zip(base, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def valido(valor: str) -> bool:
    c = limpar(valor)
    if not re.fullmatch(r"[0-9A-Z]{12}\d{2}", c) or len(set(c)) == 1:
        return False
    d1 = _dv(c[:12], _PESOS1)
    d2 = _dv(c[:12] + str(d1), _PESOS2)
    return c[12:] == f"{d1}{d2}"


def formatar(valor: str) -> str:
    c = limpar(valor)
    if len(c) != 14:
        return valor
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def e_matriz(valor: str) -> bool:
    return limpar(valor)[8:12] == "0001"


def matriz_de(valor: str) -> str:
    """CNPJ da matriz (ordem 0001) com a mesma raiz."""
    base = limpar(valor)[:8] + "0001"
    d1 = _dv(base, _PESOS1)
    return base + str(d1) + str(_dv(base + str(d1), _PESOS2))


def encontrar(texto: str) -> list[str]:
    """Retorna CNPJs válidos (só caracteres, sem máscara) na ordem em que aparecem."""
    if not texto:
        return []
    # A forma formatada exige "/" e "-"; sem máscara, só aceitamos 14 dígitos (evita códigos aleatórios).
    achados = ["".join(m.groups()) for m in _RE_FORMATADO.finditer(texto)]
    achados += _RE_CORRIDO.findall(texto)
    saida = []
    for c in achados:
        if valido(c) and c not in saida:
            saida.append(c)
    return saida
