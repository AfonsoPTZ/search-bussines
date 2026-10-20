"""Execução em lote: progresso com batimento/PID, parada segura, erros e retomada (pesquisa simulada, sem internet)."""

import json
import os
import threading

import pytest

from empresas import config, lote


def _reg(e, status="parcial"):
    return {"linha": e.linha, "entrada": e.original, "status": status, "confianca": "baixa", "campos": {},
            "divergencias": [], "observacoes": [], "nao_encontrados": [], "data_pesquisa": "2026-10-20T10:00:00"}


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTADOS_DIR", tmp_path / "resultados")
    lista = tmp_path / "lista.txt"
    lista.write_text("\n".join(f"Empresa Teste {i} | Curitiba/PR" for i in range(1, 7)), encoding="utf-8")
    return lote.criar(lista, "teste")


def _progresso(pasta):
    return json.loads((pasta / "progresso.json").read_text(encoding="utf-8"))


def test_concluido_grava_pid_e_batimento(pasta, monkeypatch):
    monkeypatch.setattr(lote, "pesquisar", lambda e: _reg(e))
    prog = lote.executar(pasta, workers=2, saida=lambda m: None)
    assert prog["status"] == "concluido"
    p = _progresso(pasta)
    assert p["concluidas"] == 6 and p["pid"] == os.getpid() and p["atualizado"] and p["finalizado"]
    assert len(lote.ler_registros(pasta)) == 6


def test_erros_ficam_marcados_e_retomar_refaz(pasta, monkeypatch):
    monkeypatch.setattr(lote, "pesquisar", lambda e: _reg(e, "erro" if e.linha in (2, 5) else "parcial"))
    prog = lote.executar(pasta, workers=1, saida=lambda m: None)
    assert prog["status"] == "concluido_com_erros" and prog["erros"] == 2
    refeitas = []
    monkeypatch.setattr(lote, "pesquisar", lambda e: refeitas.append(e.linha) or _reg(e))
    prog = lote.executar(pasta, workers=1, saida=lambda m: None)
    assert sorted(refeitas) == [2, 5] and prog["status"] == "concluido" and prog["erros"] == 0


def test_parada_segura_grava_as_em_andamento_e_deixa_pendentes(pasta, monkeypatch):
    liberar = threading.Event()

    def lenta(e):
        if e.linha == 1:
            lote.pedir_parada(pasta)  # pedido chega enquanto outras estão em andamento
        else:
            liberar.wait(2)
        return _reg(e)

    monkeypatch.setattr(lote, "pesquisar", lenta)
    threading.Timer(0.3, liberar.set).start()
    prog = lote.executar(pasta, workers=2, saida=lambda m: None)
    regs = lote.ler_registros(pasta)
    assert prog["status"] == "interrompido"
    assert 1 in regs and 2 in regs          # a que estava em andamento terminou e foi gravada
    assert len(regs) < 6                    # as que não começaram ficaram pendentes
    assert not (pasta / "parar").exists()
    feitas = []
    monkeypatch.setattr(lote, "pesquisar", lambda e: feitas.append(e.linha) or _reg(e))
    prog = lote.executar(pasta, workers=2, saida=lambda m: None)
    assert prog["status"] == "concluido" and set(feitas) == set(range(1, 7)) - set(regs)


def test_um_so_processo_por_lote_e_trava_orfa_e_liberada(pasta, monkeypatch):
    monkeypatch.setattr(lote, "pesquisar", lambda e: _reg(e))
    (pasta / "executando.lock").write_text(str(os.getpid()), encoding="utf-8")  # "outro" processo vivo
    with pytest.raises(lote.LoteEmUso):
        lote.executar(pasta, saida=lambda m: None)
    assert not (pasta / "registros.jsonl").exists() or not lote.ler_registros(pasta)
    (pasta / "executando.lock").write_text("999999", encoding="utf-8")  # processo que já morreu
    assert lote.executar(pasta, saida=lambda m: None)["status"] == "concluido"
    assert not (pasta / "executando.lock").exists()


def test_falha_ao_gravar_progresso_nao_perde_resultados(pasta, monkeypatch):
    monkeypatch.setattr(lote, "pesquisar", lambda e: _reg(e))
    original = lote._gravar_progresso
    falhas = {"n": 0}

    def instavel(p, d):
        falhas["n"] += 1
        if falhas["n"] % 3 == 0:
            raise PermissionError(13, "arquivo em uso")
        original(p, d)

    monkeypatch.setattr(lote, "_gravar_progresso", instavel)
    lote.executar(pasta, workers=2, saida=lambda m: None)
    assert len(lote.ler_registros(pasta)) == 6


def test_erro_inesperado_marca_erro_e_nao_conclusao(pasta, monkeypatch):
    monkeypatch.setattr(lote, "pesquisar", lambda e: _reg(e))
    original = json.dumps
    chamadas = {"n": 0}

    def quebra(obj, *a, **k):
        if isinstance(obj, dict) and obj.get("linha") == 3:
            chamadas["n"] += 1
            raise OSError("disco cheio")
        return original(obj, *a, **k)

    monkeypatch.setattr(lote.json, "dumps", quebra)
    with pytest.raises(OSError):
        lote.executar(pasta, workers=1, saida=lambda m: None)
    monkeypatch.setattr(lote.json, "dumps", original)
    prog = json.loads((pasta / "progresso.json").read_text(encoding="utf-8"))
    assert prog["status"] == "erro" and prog["concluidas"] < 6


def test_substituir_tenta_de_novo_quando_o_arquivo_esta_em_uso(tmp_path, monkeypatch):
    tmp, destino = tmp_path / "a.tmp", tmp_path / "a.json"
    tmp.write_text("novo")
    real = type(tmp).replace
    tentativas = {"n": 0}

    def ocupado(self, alvo):
        tentativas["n"] += 1
        if tentativas["n"] < 4:
            raise PermissionError(13, "em uso")
        return real(self, alvo)

    monkeypatch.setattr(type(tmp), "replace", ocupado)
    monkeypatch.setattr(lote.time, "sleep", lambda s: None)
    lote.substituir(tmp, destino)
    assert destino.read_text() == "novo" and tentativas["n"] == 4
