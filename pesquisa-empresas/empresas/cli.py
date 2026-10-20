"""Linha de comando: empresas <comando> ...  (use 'empresas -h' para ajuda)."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from empresas import config


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except AttributeError:
            pass


def cmd_pesquisar(a):
    from empresas import entradas, exportar, lote

    if a.texto:
        config.ENTRADAS_DIR.mkdir(exist_ok=True)
        arquivo = config.ENTRADAS_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}_{lote._slug(a.nome or 'lista')}.txt"
        arquivo.write_text(a.texto.replace("\\n", "\n"), encoding="utf-8")
    elif a.arquivo:
        arquivo = Path(a.arquivo)
    else:
        raise SystemExit("Informe o arquivo da lista ou --texto.")
    if not arquivo.exists():
        raise SystemExit(f"Arquivo não encontrado: {arquivo}")
    lista = entradas.ler(arquivo)
    if not lista:
        raise SystemExit("Nenhuma empresa reconhecida na lista.")
    pasta = lote.criar(arquivo, a.nome)
    print(f"Lote: {pasta}")
    print(f"{len(lista)} empresas | {a.workers} em paralelo | busca: "
          f"{'SearXNG local + ddgs' if _searxng() else 'ddgs (SearXNG local desligado)'}")
    try:
        lote.executar(pasta, a.workers)
    except lote.LoteEmUso as e:
        raise SystemExit(str(e)) from None
    _resumo(pasta, exportar.exportar(pasta))


def cmd_retomar(a):
    from empresas import exportar, lote

    pasta = lote.resolver_pasta(a.lote)
    print(f"Lote: {pasta}")
    try:
        lote.executar(pasta, a.workers)
    except lote.LoteEmUso as e:
        raise SystemExit(str(e)) from None
    _resumo(pasta, exportar.exportar(pasta))


def _searxng():
    from empresas import web
    return web.searxng_disponivel()


def _resumo(pasta, arquivos):
    from collections import Counter

    from empresas.lote import ler_registros
    regs = ler_registros(pasta).values()
    st = Counter(r["status"] for r in regs)
    cf = Counter(r["confianca"] for r in regs)
    print("\nResumo: " + ", ".join(f"{k}={v}" for k, v in st.most_common()))
    print("Confiança: " + ", ".join(f"{k}={v}" for k, v in cf.most_common()))
    revisar = sum(1 for r in regs if _precisa_revisao(r))
    if revisar:
        print(f"{revisar} registro(s) precisam de revisão: empresas revisar \"{pasta.name}\"")
    for k, p in arquivos.items():
        print(f"{k}: {p}")


_CAMPOS_IMPORTANTES = {"cnpj", "site", "instagram", "telefones", "whatsapp", "emails", "endereco"}


def _precisa_revisao(r) -> bool:
    return (r["status"] != "identificada" or r["confianca"] == "baixa" or bool(r["divergencias"])
            or bool(_CAMPOS_IMPORTANTES & set(r.get("nao_confirmados", []))))


def cmd_status(a):
    from empresas import lote

    pasta = lote.resolver_pasta(a.lote)
    prog = pasta / "progresso.json"
    print(prog.read_text(encoding="utf-8") if prog.exists() else "Sem progresso registrado.")


def cmd_parar(a):
    from empresas import lote

    pasta = lote.resolver_pasta(a.lote)
    lote.pedir_parada(pasta)
    print(f"Parada pedida para {pasta.name}: as empresas em andamento terminam e o restante fica para 'retomar'.")


def cmd_lotes(a):
    from empresas import lote

    if not config.RESULTADOS_DIR.exists():
        print("Nenhum lote.")
        return
    for p in sorted(config.RESULTADOS_DIR.iterdir()):
        if p.is_dir():
            regs = lote.ler_registros(p)
            ident = sum(1 for r in regs.values() if r["status"] == "identificada")
            print(f"{p.name}  ({len(regs)} registros, {ident} identificadas)")


def cmd_revisar(a):
    """Lista compacta (JSON) do que precisa de revisão, para o Claude investigar."""
    from empresas import lote
    from empresas.exportar import linha_planilha

    pasta = lote.resolver_pasta(a.lote)
    saida = []
    for _, r in sorted(lote.ler_registros(pasta).items()):
        if not a.todos and not _precisa_revisao(r):
            continue
        l = linha_planilha(r)
        saida.append({
            "linha": r["linha"], "entrada": r["entrada"], "pistas": r.get("pistas"), "status": r["status"],
            "confianca": r["confianca"],
            "encontrado": {k: l[k] for k in ("nome_comercial", "categoria", "razao_social", "cnpj", "cidade", "uf",
                                             "site", "instagram", "seguidores_instagram", "telefones", "whatsapp",
                                             "emails", "horario_funcionamento") if l.get(k)},
            "nao_confirmados": r.get("nao_confirmados", []),
            "nao_encontrados": r["nao_encontrados"], "divergencias": r["divergencias"],
            "observacoes": r["observacoes"],
            "candidatos_cnpj": [{k: c.get(k, "") for k in ("cnpj", "escolhido", "razao_social", "nome_fantasia", "cidade",
                                                            "situacao", "pontuacao", "motivos")}
                                for c in r.get("candidatos_cnpj", [])[:4]],
            "alternativas": r.get("alternativas", []),
        })
    print(json.dumps({"lote": pasta.name, "itens": saida}, ensure_ascii=False, indent=1))


def cmd_corrigir(a):
    """Registra uma correção com fonte, atualiza o registro e reexporta."""
    from urllib.parse import quote

    from empresas import cadastro, exportar, lote
    from empresas import cnpj as cnpjlib
    from empresas.pesquisa import CAMPOS, Registro, _finalizar, aplicar_cadastro

    pasta = lote.resolver_pasta(a.lote)
    regs = lote.ler_registros(pasta)
    if a.linha not in regs:
        raise SystemExit(f"Linha {a.linha} não existe no lote.")
    r = Registro.de_dict(regs[a.linha])
    campos = r.d["campos"]
    confirmado = not a.nao_confirmado

    def limpar_cadastro():
        """Remove o CNPJ e tudo que veio do cadastro dele (CNPJ errado ou trocado)."""
        for c in list(campos):
            campos[c] = [i for i in campos[c] if i["origem"] != "cadastro" and c not in ("cnpj", "google_maps")]
            if not campos[c]:
                del campos[c]
        r.d["divergencias"] = [d for d in r.d["divergencias"] if not d.startswith(("Situação cadastral", "cnpj:"))]
        r.d["pontuacao_cnpj"] = None

    if a.campo == "cnpj" and not a.remover:
        valor = a.valor or (r.valor("cnpj") if a.confirmar else "")
        if not valor:
            raise SystemExit("Informe --valor com o CNPJ.")
        try:
            cad = cadastro.consultar(valor)
        except cadastro.CnpjInexistente as x:
            raise SystemExit(str(x))
        if not cad:
            raise SystemExit("Bases de CNPJ indisponíveis agora; tente de novo.")
        limpar_cadastro()
        r.add("cnpj", cnpjlib.formatar(cad["cnpj"]), a.fonte or "", "revisao", confirmado)
        aplicar_cadastro(r, cad, confirmado=confirmado)
        r.d["pontuacao_cnpj"] = 100 if confirmado else 40
        marca = "sim (revisão)" if confirmado else "provável (revisão)"
        for c in r.d.get("candidatos_cnpj", []):
            c["escolhido"] = marca if c["cnpj"] == cnpjlib.formatar(cad["cnpj"]) else ""
        end = ", ".join(x for x in (r.valor("endereco"), r.valor("bairro"), r.valor("cidade"), r.valor("uf"), r.valor("cep")) if x)
        if end:
            r.add("google_maps", f"https://www.google.com/maps/search/?api=1&query={quote((r.valor('nome_comercial') or '') + ', ' + end)}",
                  "", "gerado", confirmado)
    elif a.campo == "cnpj" and a.remover:
        limpar_cadastro()
    elif a.campo in ("status", "confianca"):
        r.d[a.campo] = a.valor
    elif a.campo in CAMPOS:
        if a.remover:
            campos[a.campo] = [i for i in campos.get(a.campo, []) if a.valor and i["valor"] != a.valor]
            if not campos[a.campo]:
                del campos[a.campo]
        elif a.confirmar:
            # Confirma valores já encontrados (todos do campo, ou só o --valor), registrando a fonte da confirmação.
            if not a.fonte:
                raise SystemExit("Informe --fonte com a URL que comprova o valor.")
            alvos = {i["valor"] for i in campos.get(a.campo, []) if not a.valor or i["valor"] == a.valor}
            if not alvos:
                raise SystemExit(f"Nada a confirmar em {a.campo}" + (f" com valor {a.valor}" if a.valor else ""))
            for v in alvos:
                r.add(a.campo, v, a.fonte, "revisao", True)
        else:
            if not a.fonte:
                raise SystemExit("Informe --fonte com a URL que comprova o valor.")
            if a.substituir:
                campos.pop(a.campo, None)
            r.add(a.campo, a.valor, a.fonte, "revisao", confirmado)
    else:
        raise SystemExit(f"Campo desconhecido: {a.campo}. Use um de: {', '.join(CAMPOS + ['status', 'confianca'])}")

    if a.campo not in ("status", "confianca"):
        _finalizar(r)  # recalcula status, confiança e campos não confirmados
        if a.campo == "cnpj" and not a.remover:
            r.d["confianca"] = a.confianca or ("media" if confirmado else "baixa")
    if a.confianca and a.campo != "cnpj":
        r.d["confianca"] = a.confianca
    if a.status:
        r.d["status"] = a.status
    if a.nota:
        r.obs(f"Revisão: {a.nota}")
    r.d["revisado_em"] = datetime.now().isoformat(timespec="seconds")
    regs[a.linha] = r.d
    lote.regravar_registros(pasta, regs)
    with open(pasta / "correcoes.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({k: v for k, v in vars(a).items() if k != "func"} | {"em": r.d["revisado_em"]}, ensure_ascii=False) + "\n")
    arqs = exportar.exportar(pasta)
    print(f"Linha {a.linha} atualizada: status={r.d['status']} confiança={r.d['confianca']} cnpj={r.valor('cnpj') or '-'}")
    print(f"xlsx: {arqs['xlsx']}")


def cmd_exportar(a):
    from empresas import exportar, lote

    pasta = lote.resolver_pasta(a.lote)
    for k, p in exportar.exportar(pasta).items():
        print(f"{k}: {p}")


def cmd_verificar(a):
    """Testa cada componente externo e informa o que está funcionando."""
    import httpx

    from empresas import cadastro, web
    fontes_cnpj_ok = 0
    print(f"SearXNG local ({config.SEARXNG_URL}): ", end="")
    if web.searxng_disponivel():
        try:
            n = len(web._buscar_searxng("Banco do Brasil CNPJ", 5))
            print(f"OK ({n} resultados)")
        except Exception as e:
            print(f"FALHOU ({e})")
    else:
        print("desligado (opcional: 'docker compose up -d' na pasta do projeto)")
    print("ddgs (contingência): ", end="")
    n = len(web._buscar_ddgs("Banco do Brasil CNPJ", 5))
    print(f"OK ({n} resultados)" if n else "sem resultados agora (pode ser bloqueio temporário)")
    for nome, modelo, _ in cadastro.FONTES:
        try:
            r = httpx.get(modelo.format(c="00000000000191"), timeout=15, headers={"User-Agent": config.USER_AGENT})
            print(f"CNPJ {nome}: HTTP {r.status_code}")
            fontes_cnpj_ok += r.status_code == 200
        except httpx.HTTPError as e:
            print(f"CNPJ {nome}: FALHOU ({type(e).__name__})")
    busca_ok = web.searxng_disponivel() or n > 0
    print("\nPronto para uso." if fontes_cnpj_ok and busca_ok else "\nATENÇÃO: algum componente essencial não respondeu.")
    return 0 if fontes_cnpj_ok and busca_ok else 1


def main(argv=None):
    _utf8()
    p = argparse.ArgumentParser(prog="empresas", description="Pesquisa e enriquecimento de dados públicos de empresas brasileiras.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("pesquisar", help="pesquisa uma lista (txt, csv ou xlsx) e gera as planilhas")
    s.add_argument("arquivo", nargs="?")
    s.add_argument("--texto", help="lista direto na linha de comando (itens separados por quebra de linha)")
    s.add_argument("--nome", help="nome do lote (vai no nome da pasta)")
    s.add_argument("--workers", type=int, default=config.WORKERS_PADRAO)
    s.set_defaults(func=cmd_pesquisar)

    s = sub.add_parser("retomar", help="continua um lote interrompido e refaz as que deram erro")
    s.add_argument("lote", nargs="?", default="ultimo")
    s.add_argument("--workers", type=int, default=config.WORKERS_PADRAO)
    s.set_defaults(func=cmd_retomar)

    for nome, func, ajuda in (("status", cmd_status, "andamento de um lote"),
                              ("parar", cmd_parar, "para um lote com segurança (retome depois)"),
                              ("exportar", cmd_exportar, "regenera xlsx/csv"),
                              ("revisar", cmd_revisar, "lista (JSON) os registros que precisam de revisão")):
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument("lote", nargs="?", default="ultimo")
        if nome == "revisar":
            s.add_argument("--todos", action="store_true")
        s.set_defaults(func=func)

    s = sub.add_parser("corrigir", help="registra correção/complemento com fonte em um registro")
    s.add_argument("lote", nargs="?", default="ultimo")
    s.add_argument("--linha", type=int, required=True)
    s.add_argument("--campo", required=True)
    s.add_argument("--valor", default="")
    s.add_argument("--fonte", default="", help="URL que comprova o valor")
    s.add_argument("--nota", default="")
    s.add_argument("--confianca", choices=["alta", "media", "baixa"])
    s.add_argument("--status", choices=["identificada", "provavel", "parcial", "nao_encontrada"])
    s.add_argument("--substituir", action="store_true", help="apaga os valores anteriores do campo")
    s.add_argument("--remover", action="store_true", help="remove o valor informado (ou todos, se --valor vazio)")
    s.add_argument("--confirmar", action="store_true",
                   help="marca como confirmado(s) o(s) valor(es) já encontrado(s) do campo (exige --fonte)")
    s.add_argument("--nao-confirmado", action="store_true", help="registra o valor como NÃO confirmado")
    s.set_defaults(func=cmd_corrigir)

    sub.add_parser("lotes", help="lista os lotes").set_defaults(func=cmd_lotes)
    sub.add_parser("verificar", help="testa buscadores e APIs").set_defaults(func=cmd_verificar)

    a = p.parse_args(argv)
    return a.func(a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
