"""Ambiente isolado: pastas de resultados, entradas e banco em tmp_path. Dados fictícios no formato real das ferramentas
(registros montados com empresas.pesquisa.Registro e perfis classificados com prospeccao.classificar). Sem internet."""

import json
from datetime import datetime

import pytest

from empresas import config as cfg_emp
from empresas import entradas
from empresas.pesquisa import Registro, _finalizar
from plataforma import acoes, config, db
from prospeccao import config as cfg_ig
from prospeccao.classificar import classificar
from prospeccao.perfis import Perfil


@pytest.fixture
def amb(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg_ig, "RESULTADOS_DIR", tmp_path / "ig")
    monkeypatch.setattr(cfg_emp, "RESULTADOS_DIR", tmp_path / "emp")
    monkeypatch.setattr(cfg_emp, "ENTRADAS_DIR", tmp_path / "entradas")
    monkeypatch.setattr(config, "DADOS_DIR", tmp_path / "dados")
    monkeypatch.setattr(config, "CLAUDE_DIR", tmp_path / "dados" / "claude")
    processos = []
    monkeypatch.setattr(acoes, "iniciar_processo", lambda args, cwd, log: processos.append(args))
    acoes._iniciadas.clear()
    db.fechar()
    yield Ambiente(tmp_path, processos)
    db.fechar()


class Ambiente:
    def __init__(self, raiz, processos):
        self.raiz, self.processos = raiz, processos
        self._n = 0

    # ---------------------------------------------------------------- empresas
    def lote(self, nome: str, registros: list[dict], status="concluido", progresso_extra=None, meta=None):
        pasta = cfg_emp.RESULTADOS_DIR / nome
        pasta.mkdir(parents=True)
        (pasta / "entrada.txt").write_text("\n".join(r["entrada"] for r in registros) + "\n", encoding="utf-8")
        with open(pasta / "registros.jsonl", "w", encoding="utf-8") as f:
            for r in registros:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        prog = {"total": len(registros), "concluidas": len(registros), "status": status, "iniciado": "2026-10-20T10:00:00",
                "finalizado": None if status == "executando" else "2026-10-20T10:05:00", "em_andamento": []}
        prog.update(progresso_extra or {})
        (pasta / "progresso.json").write_text(json.dumps(prog), encoding="utf-8")
        if meta:
            (pasta / "plataforma.json").write_text(json.dumps(meta), encoding="utf-8")
        return pasta

    @staticmethod
    def registro(linha: int, entrada: str, campos: dict | None = None, data="2026-10-20T10:00:00", status=None,
                 revisado_em=None) -> dict:
        """campos: {campo: [(valor, origem, confirmado, fonte)]}. Status/confiança calculados pela própria ferramenta."""
        e = entradas.de_linha(entrada, linha)
        r = Registro(e)
        if e.nome:
            r.add("nome_comercial", e.nome, "", "entrada")
        if e.instagram:
            u = f"https://www.instagram.com/{e.instagram}/"
            r.add("instagram", u, u, "entrada")
        for campo, itens in (campos or {}).items():
            for valor, origem, confirmado, *fonte in itens:
                r.add(campo, valor, fonte[0] if fonte else "https://fonte.teste/", origem, confirmado)
        if r.valor("cnpj", True):
            r.d["pontuacao_cnpj"] = 90
        _finalizar(r, e)
        if status:
            r.d["status"] = status
        r.d["data_pesquisa"] = data
        if revisado_em:
            r.d["revisado_em"] = revisado_em
        return r.d

    # ---------------------------------------------------------------- Instagram
    def analise(self, origem: str, perfis: list[Perfil], estado: dict | None = None, nome=None, correcoes=None,
                categorias=None):
        self._n += 1
        pasta = cfg_ig.RESULTADOS_DIR / (nome or f"2026-10-20_10000{self._n}_{origem}")
        pasta.mkdir(parents=True)
        (pasta / "config.json").write_text(json.dumps({
            "origem": origem, "categorias": categorias or list("ABCDEFGHIJKLM"), "limite": 100, "detalhes": "candidatos",
            "publicacoes": "duvidosos", "noite": False, "fonte": "instagram", "criado": "2026-10-20T09:00:00"}), encoding="utf-8")
        est = {"status": "concluido", "fase": "fim", "obtidos": len(perfis), "processados": len(perfis), "fim_lista": True,
               "lista_limitada": False, "atualizado": datetime.now().isoformat(timespec="seconds"), "eventos": [],
               "publicacoes": {"alvos": 0, "feitos": 0}, "iniciado": "2026-10-20T09:00:00"}
        est.update(estado or {})
        (pasta / "estado.json").write_text(json.dumps(est), encoding="utf-8")
        (pasta / "origem.json").write_text(json.dumps({"usuario": origem, "pk": "1", "seguidores": 1000}), encoding="utf-8")
        with open(pasta / "perfis.jsonl", "w", encoding="utf-8") as f:
            for i, p in enumerate(perfis):
                p.etapas = p.etapas or ["lista", "perfil"]
                f.write(json.dumps({"perfil": p.para_dict(), "classificacao": classificar(p),
                                    "em": f"2026-10-20T09:{i // 60:02d}:{i % 60:02d}", "fase": "perfis"}, ensure_ascii=False) + "\n")
        if correcoes:
            with open(pasta / "correcoes.jsonl", "w", encoding="utf-8") as f:
                for c in correcoes:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
        return pasta


def perfil(usuario, nome="", bio="", categoria_ig="", cidade="", link="", **kw) -> Perfil:
    return Perfil(usuario=usuario, nome=nome, bio=bio, categoria_ig=categoria_ig, conta_comercial=True, detalhes="perfil",
                  link_externo=link, extras={"city_name": cidade} if cidade else {}, **kw)
