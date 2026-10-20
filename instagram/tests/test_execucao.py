"""Execução em fases (lista → perfis por prioridade → publicações), retomada, modo noite, exportação e revisão.

Cliente FALSO, sem rede, com DADOS DE TESTE FICTÍCIOS (sufixo/prefixo 'teste').
"""

import csv
import io
import json

import pytest

from prospeccao import config, execucao, exportar, revisao
from prospeccao.coleta import ErroColeta, ErroDesafio, ErroIndisponivel, ErroLimite, Pagina
from prospeccao.perfis import Perfil

# 3 páginas; o Instagram às vezes repete perfis entre páginas (teste_petshopamigo).
PAGINAS = [
    [("grupoxyz_teste", "Grupo XYZ"), ("maria.souza.teste", "Maria Souza"), ("teste_funerariacentral", "Funerária Central")],
    [("teste_petshopamigo", "Pet Shop Amigo"), ("teste_floricultura_bela", "Floricultura Bela"), ("joao.pereira.teste", "João Pereira")],
    [("teste_petshopamigo", "Pet Shop Amigo"), ("teste_cemiteriopet_paz", "Cemitério Pet Paz"), ("teste_igreja_vida", "Igreja Vida")],
]
UNICOS = 8
BIOS = {
    "teste_funerariacentral": ("Serviços funerários 24h e plano funerário", "Funeral Service & Cemetery", True),
    "teste_petshopamigo": ("Banho e tosa", "Pet Store", True),
    "teste_floricultura_bela": ("Coroas de flores", "Florist", True),
    "teste_cemiteriopet_paz": ("Cemitério para animais", "", True),
    "teste_igreja_vida": ("Cultos aos domingos", "Church", True),
    # nome genérico, bio sem o segmento: só as publicações dizem o que é
    "grupoxyz_teste": ("Atendimento 24h · fale conosco", "Produto/serviço", True),
}
POSTS = {
    "grupoxyz_teste": [
        {"texto": "Conheça nosso plano funerário familiar #planofunerario", "hashtags": ["planofunerario"], "fixado": True, "local": "", "data": 1, "codigo": "a"},
        {"texto": "Plano funerário a partir de R$ 30", "hashtags": [], "fixado": False, "local": "", "data": 2, "codigo": "b"},
    ],
}


class ClienteFalso:
    def __init__(self, falhar_detalhe_em=None, erro=ErroLimite, limitada=False, seguidores=9, falhas=1,
                 falhar_pagina=None, falhar_publicacoes=False):
        self.detalhes_chamados, self.paginas_pedidas, self.publicacoes_chamadas, self.destaques_chamados = [], [], [], []
        self.falhar_detalhe_em, self.erro, self.limitada, self.seguidores = falhar_detalhe_em, erro, limitada, seguidores
        self.falhas, self.falhar_pagina, self.falhar_publicacoes = falhas, falhar_pagina, falhar_publicacoes
        self.avisar = lambda m: None
        self.ritmo = type("R", (), {"avisar": None})()

    def perfil_origem(self, usuario):
        return {"usuario": usuario, "pk": "1", "nome": "Teste Origem", "seguidores": self.seguidores, "privado": False, "sigo": False}

    def pagina_seguidores(self, pk, usuario, cursor):
        i = int(cursor or 0)
        if self.falhar_pagina == i and self.falhas:
            self.falhas -= 1
            raise self.erro("falha simulada na lista (teste)")
        self.paginas_pedidas.append(i)
        prox = str(i + 1) if i + 1 < len(PAGINAS) else None
        return Pagina(perfis=[Perfil(usuario=u, nome=n, pk=str(10 * i + k), privado=False) for k, (u, n) in enumerate(PAGINAS[i])],
                      proximo=prox, limitada=self.limitada and prox is None)

    def detalhes(self, p):
        if self.falhar_detalhe_em == p.usuario and self.falhas:
            self.falhas -= 1
            raise self.erro("falha simulada (teste)")
        self.detalhes_chamados.append(p.usuario)
        bio, cat, com = BIOS.get(p.usuario, ("", "", False))
        p.bio, p.categoria_ig, p.conta_comercial, p.detalhes = bio, cat, com, "perfil"
        p.etapas.append("perfil")
        return p

    def publicacoes(self, usuario, quantidade=12):
        self.publicacoes_chamadas.append(usuario)
        if self.falhar_publicacoes:
            raise ErroColeta("publicações indisponíveis (teste)")
        return list(POSTS.get(usuario, []))

    def destaques(self, pk):
        self.destaques_chamados.append(pk)
        return []

    def fechar(self):
        pass


def _usuarios(pasta):
    return [r["perfil"]["usuario"] for r in execucao.iterar_registros(pasta) if r.get("fase", "perfis") == "perfis"]


def _rodar(pasta, cliente, **kw):
    return execucao.executar(pasta, cliente, saida=lambda m: None, dormir=kw.get("dormir", lambda s: None))


def _ident(pasta):
    rs = execucao.resumo(pasta)
    return {cod: [r["perfil"]["usuario"] for r, _ in g["identificados"]] for cod, g in rs["por_categoria"].items()}


# ---------- fluxo completo

def test_fases_completas_prioridade_e_duplicidade():
    pasta = execucao.criar("@teste_origem", "todas", None, "candidatos")
    c = ClienteFalso()
    est = _rodar(pasta, c)
    assert est["status"] == "concluido" and est["fim_lista"] and est["fase"] == "fim"
    us = _usuarios(pasta)
    assert len(us) == len(set(us)) == UNICOS and est["duplicados"] == 1 and est["paginas"] == 3 and est["obtidos"] == UNICOS
    # nomes de pessoa ficam no fim da fila e, no modo candidatos, não são lidos (mas são registrados)
    assert "maria.souza.teste" not in c.detalhes_chamados and "joao.pereira.teste" not in c.detalhes_chamados
    assert "maria.souza.teste" in us and est["nao_lidos"] == 2
    # prioridade: quem tem indício de segmento é lido antes do nome comercial genérico, mesmo vindo depois na lista
    assert c.detalhes_chamados.index("teste_igreja_vida") < c.detalhes_chamados.index("grupoxyz_teste")
    seg = [json.loads(l) for l in (pasta / "seguidores.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(seg) == UNICOS and {s["usuario"]: s["triagem"]["prioridade"] for s in seg}["maria.souza.teste"] == 4
    ident = _ident(pasta)
    assert ident["F"] == ["teste_funerariacentral"] and ident["I"] == ["teste_petshopamigo"]
    assert ident["D"] == ["teste_floricultura_bela"] and ident["B"] == ["teste_cemiteriopet_paz"] and ident["J"] == ["teste_igreja_vida"]


def test_empresa_com_informacao_so_nas_publicacoes():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    c = ClienteFalso()
    est = _rodar(pasta, c)
    assert c.publicacoes_chamadas == ["grupoxyz_teste"]  # só quem ficou sem categoria com sinais comerciais
    assert est["publicacoes"]["lidas"] == 1 and est["publicacoes"].get("mudaram") == 1
    assert "grupoxyz_teste" in _ident(pasta)["G"]
    reg = execucao.ultimos_registros(pasta)["grupoxyz_teste"]
    assert reg["fase"] == "publicacoes" and reg["situacao_antes"] == "sem_correspondencia"
    assert "publicacoes" in reg["perfil"]["etapas"] and any("publicações" in f for f in reg["classificacao"]["fontes"])
    g = next(x for x in reg["classificacao"]["categorias"] if x["codigo"] == "G")
    assert any(e.startswith("publicação") for e in g["evidencias"]) and g["limitacao"] == "evidência só nas publicações"
    assert c.destaques_chamados == []  # publicações resolveram: destaques não lidos (economia de requisição)


def test_publicacoes_inacessiveis_nao_param_nem_repetem():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    c = ClienteFalso(falhar_publicacoes=True)
    est = _rodar(pasta, c)
    assert est["status"] == "concluido" and est["publicacoes"]["falhas"] == 1
    reg = execucao.ultimos_registros(pasta)["grupoxyz_teste"]
    assert reg["perfil"]["erro_publicacoes"] and reg["classificacao"]["situacao"] == "sem_correspondencia"
    c2 = ClienteFalso()
    _rodar(pasta, c2)
    assert c2.publicacoes_chamadas == [] and c2.detalhes_chamados == []  # nada é refeito na retomada


def test_sem_publicacoes_quando_desligado():
    pasta = execucao.criar("teste_origem", None, None, "candidatos", publicacoes="nenhuma")
    c = ClienteFalso()
    _rodar(pasta, c)
    assert c.publicacoes_chamadas == []


def test_modo_todos_le_tambem_nomes_de_pessoa():
    pasta = execucao.criar("teste_origem", None, None, "todos")
    c = ClienteFalso()
    _rodar(pasta, c)
    assert {"maria.souza.teste", "joao.pereira.teste"} <= set(c.detalhes_chamados)


# ---------- limite, interrupção e retomada

def test_limite_e_retomada_com_limite_maior():
    pasta = execucao.criar("teste_origem", None, 4, "candidatos")
    est = _rodar(pasta, ClienteFalso())
    assert est["status"] == "limite_atingido" and est["obtidos"] == 4 and len(_usuarios(pasta)) == 4
    cfg = execucao.ler_config(pasta)
    cfg["limite"] = None
    execucao._gravar_json(pasta / "config.json", cfg)
    c2 = ClienteFalso()
    est = _rodar(pasta, c2)
    us = _usuarios(pasta)
    assert est["status"] == "concluido" and len(us) == len(set(us)) == UNICOS
    assert c2.paginas_pedidas[0] == 1  # continuou da página em que o limite cortou


def test_pausa_por_limite_na_fase_de_perfis_e_retomada_sem_repetir():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    est = _rodar(pasta, ClienteFalso(falhar_detalhe_em="teste_floricultura_bela"))
    assert est["status"] == "pausado_limite_instagram" and est["fase"] == "perfis"
    assert any(e["tipo"] == "temporario" for e in est["eventos"])
    antes = set(_usuarios(pasta))
    assert len((pasta / "seguidores.jsonl").read_text(encoding="utf-8").splitlines()) == UNICOS  # lista inteira preservada
    assert antes and "teste_floricultura_bela" not in antes
    c2 = ClienteFalso()
    est = _rodar(pasta, c2)
    us = _usuarios(pasta)
    assert est["status"] == "concluido" and len(us) == len(set(us)) == UNICOS
    assert c2.paginas_pedidas == [] and not (antes & set(c2.detalhes_chamados))  # não relê lista nem perfis já feitos


def test_pausa_na_fase_de_lista_e_retomada_da_pagina():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    est = _rodar(pasta, ClienteFalso(falhar_pagina=1, erro=ErroIndisponivel))
    assert est["status"] == "erro_rede" and est["fase"] == "lista" and est["obtidos"] == 3
    c2 = ClienteFalso()
    est = _rodar(pasta, c2)
    assert est["status"] == "concluido" and c2.paginas_pedidas == [1, 2] and len(set(_usuarios(pasta))) == UNICOS


def test_modo_noite_espera_e_continua_sozinho(monkeypatch):
    monkeypatch.setattr(config, "ESPERAS_NOITE_LIMITE", [7])
    pasta = execucao.criar("teste_origem", None, None, "candidatos", noite=True)
    dormiu = []
    est = _rodar(pasta, ClienteFalso(falhar_detalhe_em="teste_floricultura_bela"), dormir=dormiu.append)
    assert est["status"] == "concluido" and len(set(_usuarios(pasta))) == UNICOS
    assert sum(dormiu) >= 7 and any("aguardando" in e["mensagem"] for e in est["eventos"] if e["tipo"] == "temporario")


def test_modo_noite_esgota_esperas_e_pausa(monkeypatch):
    monkeypatch.setattr(config, "ESPERAS_NOITE_LIMITE", [1, 1])
    pasta = execucao.criar("teste_origem", None, None, "candidatos", noite=True)
    est = _rodar(pasta, ClienteFalso(falhar_detalhe_em="teste_floricultura_bela", falhas=99))
    assert est["status"] == "pausado_limite_instagram"
    assert sum(1 for e in est["eventos"] if "aguardando" in e["mensagem"]) == 2


def test_desafio_nunca_e_aguardado_nem_no_modo_noite(monkeypatch):
    monkeypatch.setattr(config, "ESPERAS_NOITE_LIMITE", [1])
    pasta = execucao.criar("teste_origem", None, None, "candidatos", noite=True)
    dormiu = []
    est = _rodar(pasta, ClienteFalso(falhar_detalhe_em="teste_petshopamigo", erro=ErroDesafio), dormir=dormiu.append)
    assert est["status"] == "erro_desafio" and dormiu == []
    assert est["eventos"][-1]["tipo"] == "intervencao"


def test_falha_de_leitura_de_um_perfil_nao_para_a_execucao():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    est = _rodar(pasta, ClienteFalso(falhar_detalhe_em="teste_petshopamigo", erro=ErroColeta))
    assert est["status"] == "concluido" and est["detalhes_falhos"] == 1
    reg = execucao.ultimos_registros(pasta)["teste_petshopamigo"]
    assert reg["perfil"]["detalhes"] == "indisponivel" and reg["classificacao"]["estado_analise"] == "detalhes_indisponiveis"


def test_pedido_de_parada_durante_perfis():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    c = ClienteFalso()
    original = c.detalhes

    def detalhe_e_pede_parada(p):
        (pasta / "parar").touch()  # usuário clicou "Parar com segurança"
        return original(p)

    c.detalhes = detalhe_e_pede_parada
    est = _rodar(pasta, c)
    assert est["status"] == "interrompido" and not (pasta / "parar").exists() and len(_usuarios(pasta)) == 1
    est = _rodar(pasta, ClienteFalso())
    assert est["status"] == "concluido" and len(set(_usuarios(pasta))) == UNICOS


def test_linhas_truncadas_sao_isoladas_e_retomada_funciona():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    _rodar(pasta, ClienteFalso(falhar_detalhe_em="teste_floricultura_bela"))
    for arq in ("perfis.jsonl", "seguidores.jsonl"):
        with (pasta / arq).open("a", encoding="utf-8") as f:
            f.write('{"usuario": "teste_trunc')  # processo morto no meio da escrita
    est = _rodar(pasta, ClienteFalso())
    assert est["status"] == "concluido" and len(set(_usuarios(pasta))) == UNICOS
    assert "teste_trunc" not in _usuarios(pasta)


def test_lista_limitada_pelo_instagram_e_informada():
    pasta = execucao.criar("teste_origem", None, None, "nenhum")
    est = _rodar(pasta, ClienteFalso(limitada=True))
    assert est["lista_limitada"] and any("parte da lista" in e["mensagem"] for e in est["eventos"])
    assert execucao.resumo(pasta)["percentual"] == 100.0


def test_sem_sessao_nao_inventa_dados():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    est = execucao.executar(pasta, None, saida=lambda m: None)
    assert est["status"] == "sem_sessao" and _usuarios(pasta) == []
    assert est["eventos"][-1]["tipo"] == "intervencao"


def test_analise_antiga_sem_seguidores_jsonl_e_migrada():
    """Análises feitas antes das fases (só perfis.jsonl) continuam e passam pela etapa de publicações."""
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    _rodar(pasta, ClienteFalso(), )
    (pasta / "seguidores.jsonl").unlink()
    linhas = [json.loads(l) for l in (pasta / "perfis.jsonl").read_text(encoding="utf-8").splitlines()]
    antigas = [dict(r, perfil={k: v for k, v in r["perfil"].items() if k not in ("posts", "etapas", "triagem", "destaques")})
               for r in linhas if r.get("fase") == "perfis"]
    (pasta / "perfis.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in antigas) + "\n", encoding="utf-8")
    c = ClienteFalso()
    est = _rodar(pasta, c)
    assert est["status"] == "concluido" and c.detalhes_chamados == [] and c.paginas_pedidas == []
    assert (pasta / "seguidores.jsonl").exists() and c.publicacoes_chamadas == ["grupoxyz_teste"]
    assert any("reconstruída" in e["mensagem"] for e in est["eventos"])


def test_modo_arquivo_offline(tmp_path):
    lista = tmp_path / "lista.txt"
    lista.write_text("@teste_funerariaboa\n@teste_pessoa\n@teste_funerariaboa\n", encoding="utf-8")
    pasta = execucao.criar("", "F", None, "nenhum", arquivo_lista=lista)
    est = execucao.executar(pasta, None, saida=lambda m: None)
    assert est["status"] == "concluido" and _usuarios(pasta) == ["teste_funerariaboa", "teste_pessoa"]
    assert [r["perfil"]["usuario"] for r, _ in execucao.resumo(pasta)["por_categoria"]["F"]["identificados"]] == ["teste_funerariaboa"]


def test_categorias_selecionadas_filtram_resultado():
    pasta = execucao.criar("teste_origem", "D,J", None, "candidatos")
    _rodar(pasta, ClienteFalso())
    rs = execucao.resumo(pasta)
    assert set(rs["por_categoria"]) == {"D", "J"} and rs["identificados"] == 2


def test_resumo_conta_etapas_e_sem_informacao():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    _rodar(pasta, ClienteFalso())
    rs = execucao.resumo(pasta)
    assert rs["com_publicacoes"] == 1 and rs["sem_informacao"] == 2 and rs["percentual"] == 100.0
    assert rs["estado"]["duracao_s"] >= 0 and rs["estado"]["ultima_etapa"]


def test_validacoes_ao_criar():
    for args, kw in ((("teste origem invalida", None), {}), (("teste_ok", None, 0), {}), (("teste_ok", "X"), {}),
                     (("teste_ok", None, None, "rapido"), {}), (("teste_ok",), {"publicacoes": "todas"})):
        with pytest.raises(ValueError):
            execucao.criar(*args, **kw)


# ---------- exportação, revisão e correções

def test_exportacao_csv_e_markdown():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    _rodar(pasta, ClienteFalso())
    arqs = exportar.exportar(pasta)
    bruto = arqs["csv"].read_bytes()
    assert bruto.startswith(b"\xef\xbb\xbf")  # BOM: Excel abre com acentos corretos
    linhas = list(csv.DictReader(io.StringIO(bruto.decode("utf-8-sig")), delimiter=";"))
    assert {"Código", "Categoria", "Instagram", "Link", "Confiança", "Evidências", "Situação", "Etapas", "Fontes"} <= set(linhas[0])
    funeraria = [l for l in linhas if l["Instagram"] == "@teste_funerariacentral"]
    assert {l["Código"] for l in funeraria} >= {"F", "G"}  # um perfil, uma linha por categoria
    assert all(l["Link"].startswith("https://www.instagram.com/") for l in linhas)
    assert not any(l["Instagram"] == "@maria.souza.teste" for l in linhas)
    xyz = next(l for l in linhas if l["Instagram"] == "@grupoxyz_teste")
    assert "publicacoes" in xyz["Etapas"]
    md = arqs["md"].read_text(encoding="utf-8")
    assert "## Floriculturas" in md and "`@teste_floricultura_bela`" in md


def test_pacote_de_revisao_decisoes_e_divergencias():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    _rodar(pasta, ClienteFalso())
    arqs = revisao.gerar(pasta)
    pacote = json.loads(arqs["json"].read_text(encoding="utf-8"))
    itens = {i["usuario"]: i for i in pacote["itens"]}
    xyz = itens["grupoxyz_teste"]  # identificado só pelas publicações: vai com ressalva
    assert xyz["estado_revisao"] == "pendente" and "ressalva" in xyz["motivo_da_duvida"]
    assert xyz["publicacoes"][0]["fixado"] and xyz["link"].endswith("/grupoxyz_teste/")
    assert {"bio", "categoria_instagram", "comercial", "categorias_consideradas", "evidencias_contra", "etapas_executadas"} <= set(xyz)
    assert "@grupoxyz_teste" in arqs["md"].read_text(encoding="utf-8")
    decisoes = json.loads(arqs["decisoes"].read_text(encoding="utf-8"))
    assert any(d["usuario"] == "grupoxyz_teste" for d in decisoes["decisoes"])
    # decisões (como o Claude faria no chat)
    arq = pasta / "revisao" / "minhas.json"
    arq.write_text(json.dumps({"revisor": "claude", "decisoes": [
        {"usuario": "grupoxyz_teste", "decisao": "corrigir", "categorias": ["G", "F"], "nota": "teste: vende plano e faz funeral"},
        {"usuario": "teste_igreja_vida", "decisao": "descartar", "nota": "teste: fora do público"},
        {"usuario": "teste_inexistente", "decisao": "confirmar", "categorias": ["A"]},
        {"usuario": "teste_floricultura_bela", "decisao": "pular"}]}), encoding="utf-8")
    r = revisao.aplicar(pasta, arq)
    assert r["aplicadas"] == 2 and r["puladas"] == 1 and len(r["erros"]) == 1
    fin = {x["perfil"]["usuario"]: x["classificacao"] for x in execucao.resultados(pasta)}
    assert [c["codigo"] for c in fin["grupoxyz_teste"]["categorias"]] == ["F", "G"] and fin["teste_igreja_vida"]["situacao"] == "descartado"
    auto = execucao.ultimos_registros(pasta)["grupoxyz_teste"]["classificacao"]
    assert [c["codigo"] for c in auto["categorias"]] == ["G"]  # a classificação automática original é preservada
    div = {d["usuario"]: d for d in revisao.divergencias(pasta)}
    assert div["grupoxyz_teste"]["revisado"] == ["F", "G"] and div["teste_igreja_vida"]["revisado"] == ["descartado"]
    novo = json.loads(revisao.gerar(pasta)["json"].read_text(encoding="utf-8"))
    assert {i["usuario"]: i for i in novo["itens"]}["grupoxyz_teste"]["estado_revisao"] == "revisado"


def test_correcao_e_descarte():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    _rodar(pasta, ClienteFalso())
    execucao.corrigir(pasta, "@teste_igreja_vida", None, "teste: não é parceiro", descartar=True)
    execucao.corrigir(pasta, "teste_petshopamigo", ["I", "H"], "teste: também tem clínica")
    rs = {r["perfil"]["usuario"]: r["classificacao"] for r in execucao.resultados(pasta)}
    assert rs["teste_igreja_vida"]["situacao"] == "descartado"
    assert [c["codigo"] for c in rs["teste_petshopamigo"]["categorias"]] == ["H", "I"]
    with pytest.raises(ValueError):
        execucao.corrigir(pasta, "teste_inexistente", ["A"])


def test_reclassificar_offline_preserva_perfis():
    pasta = execucao.criar("teste_origem", None, None, "candidatos")
    _rodar(pasta, ClienteFalso())
    antes = execucao.ultimos_registros(pasta)
    linhas = (pasta / "perfis.jsonl").read_text(encoding="utf-8").splitlines()
    alterado = json.loads(linhas[0])
    alterado["classificacao"]["categorias"] = []  # simula classificação antiga/defasada
    (pasta / "perfis.jsonl").write_text("\n".join([json.dumps(alterado)] + linhas[1:]) + "\n", encoding="utf-8")
    assert execucao.reclassificar(pasta) == len(antes)
    depois = execucao.ultimos_registros(pasta)
    assert set(depois) == set(antes)
    assert [c["codigo"] for c in depois[alterado["perfil"]["usuario"]]["classificacao"]["categorias"]] == \
           [c["codigo"] for c in antes[alterado["perfil"]["usuario"]]["classificacao"]["categorias"]]


def test_um_so_processo_por_analise(tmp_path, monkeypatch):
    import os
    from prospeccao import config as cfg
    from prospeccao import execucao as ex
    monkeypatch.setattr(cfg, "RESULTADOS_DIR", tmp_path)
    lista = tmp_path / "lista.txt"
    lista.write_text("teste_a\nteste_b\n", encoding="utf-8")
    pasta = ex.criar("", None, None, "nenhum", lista, "teste-trava", "nenhuma")
    (pasta / "executando.lock").write_text(str(os.getpid()), encoding="utf-8")
    import pytest
    with pytest.raises(ex.AnaliseEmUso):
        ex.executar(pasta, saida=lambda m: None)
    (pasta / "executando.lock").write_text("999999", encoding="utf-8")  # trava órfã
    assert ex.executar(pasta, saida=lambda m: None)["status"] == "concluido"
    assert not (pasta / "executando.lock").exists()
