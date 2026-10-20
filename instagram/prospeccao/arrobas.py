"""Validação e normalização de identificadores (@) do Instagram."""

import re
from urllib.parse import urlparse

# Regras do Instagram: 1 a 30 caracteres, letras, números, ponto e sublinhado;
# não começa nem termina com ponto e não tem dois pontos seguidos.
_VALIDO = re.compile(r"^(?!\.)(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$")

# Caminhos do site que não são perfis.
_RESERVADOS = {
    "p", "reel", "reels", "tv", "stories", "explore", "accounts", "direct", "about", "legal", "developer",
    "web", "api", "graphql", "challenge", "emails", "session", "login", "privacy", "terms",
}


class ArrobaInvalida(ValueError):
    pass


def normalizar(entrada: str | None) -> str:
    """'@Fulano', 'fulano ', 'instagram.com/fulano/?hl=pt' -> 'fulano'. Lança ArrobaInvalida se não servir."""
    t = (entrada or "").strip().strip("\"'").strip()
    if not t:
        raise ArrobaInvalida("Informe o @ do perfil.")
    if "instagram.com" in t.lower() or t.lower().startswith(("http://", "https://", "www.")):
        url = t if "://" in t else "https://" + t
        partes = [p for p in urlparse(url).path.split("/") if p]
        if not partes:
            raise ArrobaInvalida(f"Link sem perfil: {entrada}")
        t = partes[0]
    t = t.lstrip("@").strip().lower()
    if not _VALIDO.match(t):
        raise ArrobaInvalida(f"@ inválido: {entrada!r} (use 1 a 30 letras, números, '.' ou '_')")
    if t in _RESERVADOS:
        raise ArrobaInvalida(f"'{t}' é uma página do Instagram, não um perfil.")
    return t


def valida(entrada: str | None) -> bool:
    try:
        normalizar(entrada)
        return True
    except ArrobaInvalida:
        return False


def link(usuario: str) -> str:
    return f"https://www.instagram.com/{usuario}/"
