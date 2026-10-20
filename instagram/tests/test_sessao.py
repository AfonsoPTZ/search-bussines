"""Sessão do Instagram: criptografia (sem vazar valores) e importação do Firefox. Valores são FICTÍCIOS."""

import sqlite3
import sys

import pytest

from prospeccao import config, sessao

VALOR_TESTE = "123456%3AVALORFALSODETESTE%3A99%3Aabcdefghijkl"


def test_de_sessionid():
    c = sessao.de_sessionid(f"sessionid={VALOR_TESTE}; Path=/")
    assert c == {"sessionid": VALOR_TESTE, "ds_user_id": "123456"}
    with pytest.raises(ValueError):
        sessao.de_sessionid("curto")


def test_salvar_carregar_sem_texto_puro():
    sessao.salvar(sessao.de_sessionid(VALOR_TESTE), "teste")
    bruto = config.SESSAO_ARQ.read_bytes()
    if sys.platform == "win32":
        assert b"VALORFALSODETESTE" not in bruto  # criptografado com DPAPI
    assert sessao.carregar()["sessionid"] == VALOR_TESTE
    d = sessao.descricao()
    assert d["configurada"] and VALOR_TESTE not in str(d) and d["conta_id"] == "123456"
    assert sessao.remover() and sessao.carregar() is None


def test_importar_firefox_de_banco_ficticio(tmp_path):
    perfil = tmp_path / "Profiles" / "teste.default"
    perfil.mkdir(parents=True)
    con = sqlite3.connect(perfil / "cookies.sqlite")
    con.execute("CREATE TABLE moz_cookies (name TEXT, value TEXT, host TEXT, lastAccessed INTEGER)")
    con.executemany("INSERT INTO moz_cookies VALUES (?,?,?,?)", [
        ("sessionid", VALOR_TESTE, ".instagram.com", 5), ("csrftoken", "csrf-teste", ".instagram.com", 5),
        ("ds_user_id", "123456", ".instagram.com", 5), ("sessionid", "outro-site", ".exemplo.com", 9)])
    con.commit()
    con.close()
    c = sessao.importar_firefox(tmp_path / "Profiles")
    assert c == {"sessionid": VALOR_TESTE, "csrftoken": "csrf-teste", "ds_user_id": "123456"}
    with pytest.raises(FileNotFoundError):
        sessao.importar_firefox(tmp_path / "nao_existe")
