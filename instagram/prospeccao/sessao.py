"""Sessão do Instagram do próprio usuário (cookies), guardada FORA do projeto e criptografada com o DPAPI do Windows.

Formas de configurar (nenhuma pede senha à ferramenta):
    prospeccao sessao definir     cola o valor do cookie "sessionid" (entrada oculta)
    prospeccao sessao firefox     importa os cookies do instagram.com do Firefox onde você já está logado
Variável de ambiente PROSPECCAO_SESSIONID também funciona (útil para testes); não é gravada em disco.

Os valores nunca são impressos, registrados em log ou enviados a outro lugar que não o instagram.com.
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from prospeccao import config

COOKIES_UTEIS = ("sessionid", "ds_user_id", "csrftoken", "mid", "ig_did", "datr", "rur", "ig_nrcb")


# ---------- DPAPI (Windows): só o mesmo usuário, no mesmo computador, consegue abrir o arquivo


def _dpapi(dados: bytes, proteger: bool) -> bytes:
    if sys.platform != "win32":
        return dados
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(dados, len(dados))
    entrada = BLOB(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    saida = BLOB()
    crypt32 = ctypes.windll.crypt32
    fn = crypt32.CryptProtectData if proteger else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(entrada), None, None, None, None, 0x1, ctypes.byref(saida))  # 0x1 = sem interface
    if not ok:
        raise OSError("DPAPI falhou ao " + ("proteger" if proteger else "abrir") + " a sessão")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def de_sessionid(valor: str) -> dict:
    v = valor.strip().strip('"').strip()
    if v.lower().startswith("sessionid="):
        v = v.split("=", 1)[1].split(";")[0]
    if len(v) < 20 or " " in v:
        raise ValueError("Isso não parece um valor de cookie 'sessionid' do Instagram.")
    ds = unquote(v).split(":", 1)[0]
    cookies = {"sessionid": v}
    if ds.isdigit():
        cookies["ds_user_id"] = ds
    return cookies


def salvar(cookies: dict, origem: str):
    cookies = {k: v for k, v in cookies.items() if k in COOKIES_UTEIS and v}
    if "sessionid" not in cookies:
        raise ValueError("Cookie 'sessionid' ausente: faça login no Instagram antes.")
    dados = json.dumps({"cookies": cookies, "origem": origem, "salvo_em": datetime.now().isoformat(timespec="seconds")})
    config.DADOS_USUARIO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = config.SESSAO_ARQ.with_suffix(".tmp")
    tmp.write_bytes(_dpapi(dados.encode("utf-8"), True))
    tmp.replace(config.SESSAO_ARQ)


def _ler_arquivo() -> dict | None:
    if not config.SESSAO_ARQ.exists():
        return None
    try:
        return json.loads(_dpapi(config.SESSAO_ARQ.read_bytes(), False).decode("utf-8"))
    except (OSError, ValueError):
        return None


def carregar() -> dict | None:
    """Cookies da sessão, ou None se não houver sessão configurada."""
    env = os.environ.get("PROSPECCAO_SESSIONID")
    if env:
        return de_sessionid(env)
    d = _ler_arquivo()
    return d["cookies"] if d else None


def descricao() -> dict:
    """Situação da sessão SEM revelar valores."""
    if os.environ.get("PROSPECCAO_SESSIONID"):
        return {"configurada": True, "origem": "variável de ambiente PROSPECCAO_SESSIONID"}
    d = _ler_arquivo()
    if not d:
        return {"configurada": False}
    return {"configurada": True, "origem": d.get("origem", ""), "salvo_em": d.get("salvo_em", ""),
            "conta_id": d["cookies"].get("ds_user_id", "?"), "arquivo": str(config.SESSAO_ARQ)}


def remover() -> bool:
    if config.SESSAO_ARQ.exists():
        config.SESSAO_ARQ.unlink()
        return True
    return False


def importar_firefox(pasta_perfis: Path | None = None) -> dict:
    """Lê os cookies do instagram.com do Firefox (todos os perfis; usa o login mais recente)."""
    base = pasta_perfis or Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
    bancos = sorted(base.glob("*/cookies.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True) if base.exists() else []
    if not bancos:
        raise FileNotFoundError(f"Nenhum perfil do Firefox encontrado em {base}")
    melhor, melhor_t = None, -1
    for banco in bancos:
        with tempfile.TemporaryDirectory() as tmp:
            copia = Path(tmp) / "c.sqlite"
            shutil.copy2(banco, copia)  # o Firefox mantém o arquivo travado enquanto aberto
            for extra in ("-wal", "-shm"):
                if banco.with_name(banco.name + extra).exists():
                    shutil.copy2(banco.with_name(banco.name + extra), copia.with_name(copia.name + extra))
            con = sqlite3.connect(copia)
            try:
                linhas = con.execute(
                    "SELECT name, value, lastAccessed FROM moz_cookies WHERE host LIKE '%instagram.com'").fetchall()
            finally:
                con.close()
        cookies = {n: v for n, v, _ in linhas if n in COOKIES_UTEIS}
        t = max((la for n, _, la in linhas if n == "sessionid"), default=-1)
        if cookies.get("sessionid") and t > melhor_t:
            melhor, melhor_t = cookies, t
    if not melhor:
        raise LookupError("O Firefox não tem login ativo no Instagram. Entre em instagram.com pelo Firefox e tente de novo.")
    return melhor
