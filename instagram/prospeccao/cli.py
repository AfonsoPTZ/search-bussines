"""Linha de comando: prospeccao <comando> ...  (use 'prospeccao -h' para ajuda)."""

import argparse
import getpass
import json
import sys
from pathlib import Path

from prospeccao import categorias as cats
from prospeccao import config


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except AttributeError:
            pass


def _fim(pasta):
    from prospeccao import exportar, revisao
    from prospeccao.execucao import resumo

    arqs = exportar.exportar(pasta)
    arqs.update({f"revisão ({k})": v for k, v in revisao.gerar(pasta).items()})
    rs = resumo(pasta)
    est = rs["estado"]
    pub = est.get("publicacoes") or {}
    print(f"\nSituação: {est.get('status')} — {est.get('mensagem', '')}")
    print(f"Seguidores públicos da origem: {rs['origem'].get('seguidores', '?')} | obtidos da lista: {est.get('obtidos', 0)} | "
          f"analisados: {est.get('processados', 0)} | bios lidas: {est.get('detalhes_lidos', 0)} | "
          f"publicações lidas: {pub.get('lidas', 0)} (mudaram {pub.get('mudaram', 0)}) | "
          f"identificados: {rs['identificados']} | revisar: {rs['revisar']} | sem informação suficiente: {rs['sem_informacao']}")
    print(f"Tempo de execução: {est.get('duracao_s', 0) // 60} min")
    if est.get("lista_limitada"):
        print("ATENÇÃO: o Instagram exibe só parte da lista de seguidores deste perfil.")
    for e in est.get("eventos", [])[-4:]:
        if e["tipo"] != "info" or "parte da lista" in e["mensagem"]:
            print(f"{'[precisa de você] ' if e['tipo'] == 'intervencao' else ''}{e['em']}: {e['mensagem']}")
    for cod in rs["config"]["categorias"]:
        g = rs["por_categoria"][cod]
        if g["identificados"] or g["revisar"]:
            print(f"\n{cats.POR_CODIGO[cod].nome}: " + ", ".join("@" + r["perfil"]["usuario"] for r, _ in g["identificados"])
                  + (f"  (+{len(g['revisar'])} para revisar)" if g["revisar"] else ""))
    print()
    for k, p in arqs.items():
        print(f"{k}: {p}")


def cmd_analisar(a):
    from prospeccao import execucao

    try:
        pasta = execucao.criar(a.origem, a.categorias, a.limite, a.detalhes, Path(a.arquivo) if a.arquivo else None, a.nome,
                               a.publicacoes, a.noite)
    except ValueError as e:
        raise SystemExit(str(e))
    print(f"Análise: {pasta}")
    print(f"Categorias: {', '.join(execucao.ler_config(pasta)['categorias'])} | limite: {a.limite or 'sem limite'} | "
          f"leitura de perfis: {a.detalhes} | publicações: {a.publicacoes} | modo noite: {'sim' if a.noite else 'não'}")
    if a.preparar:
        print(str(pasta))
        return
    try:
        execucao.executar(pasta)
    except execucao.AnaliseEmUso as e:
        raise SystemExit(str(e)) from None
    _fim(pasta)


def cmd_executar(a):
    """Usado pelo painel: roda/retoma uma pasta já criada."""
    from prospeccao import execucao

    pasta = execucao.resolver_pasta(a.analise)
    cfg = execucao.ler_config(pasta)
    if a.limite is not None:
        cfg["limite"] = a.limite or None
    if a.noite is not None:
        cfg["noite"] = a.noite
    execucao._gravar_json(pasta / "config.json", cfg)
    print(f"Análise: {pasta}")
    try:
        execucao.executar(pasta)
    except execucao.AnaliseEmUso as e:
        raise SystemExit(str(e)) from None
    _fim(pasta)


def cmd_status(a):
    from prospeccao import execucao

    pasta = execucao.resolver_pasta(a.analise)
    print(json.dumps(execucao.ler_estado(pasta), ensure_ascii=False, indent=1))


def cmd_parar(a):
    from prospeccao import execucao

    pasta = execucao.resolver_pasta(a.analise)
    (pasta / "parar").touch()
    print("Pedido de parada registrado; a execução para após o perfil atual.")


def cmd_listar(a):
    from prospeccao import execucao

    for p in execucao.listar():
        est = execucao.ler_estado(p)
        print(f"{p.name}  ({est.get('processados', 0)} analisados, {est.get('status_exibido') or est.get('status')})")


def cmd_exportar(a):
    from prospeccao import execucao, exportar

    pasta = execucao.resolver_pasta(a.analise)
    for k, p in exportar.exportar(pasta).items():
        print(f"{k}: {p}")


def cmd_reclassificar(a):
    from prospeccao import execucao, exportar

    pasta = execucao.resolver_pasta(a.analise)
    n = execucao.reclassificar(pasta)
    exportar.exportar(pasta)
    print(f"{n} perfis reclassificados com as regras atuais (sem acessar a internet).")
    _fim(pasta)


def cmd_revisar(a):
    """JSON do pacote de revisão (pendentes; --todos inclui os já revisados), para revisão humana ou pelo Claude no chat."""
    from prospeccao import execucao, revisao

    pasta = execucao.resolver_pasta(a.analise)
    itens = revisao.montar(pasta, a.incluir.split(",") if a.incluir else None)
    if not a.todos:
        itens = [i for i in itens if i["estado_revisao"] == "pendente"]
    if a.max:
        itens = itens[:a.max]
    print(json.dumps({"analise": pasta.name, "total": len(itens), "itens": itens}, ensure_ascii=False, indent=1))


def cmd_pacote(a):
    from prospeccao import execucao, revisao

    pasta = execucao.resolver_pasta(a.analise)
    for k, p in revisao.gerar(pasta, a.incluir.split(",") if a.incluir else None).items():
        print(f"{k}: {p}")
    itens = revisao.montar(pasta)
    print(f"{len(itens)} itens ({sum(1 for i in itens if i['estado_revisao'] == 'pendente')} pendentes)")


def cmd_aplicar_revisao(a):
    from prospeccao import execucao, exportar, revisao

    pasta = execucao.resolver_pasta(a.analise)
    r = revisao.aplicar(pasta, Path(a.arquivo) if a.arquivo else None)
    exportar.exportar(pasta)
    revisao.gerar(pasta)
    print(f"Decisões aplicadas: {r['aplicadas']} | puladas: {r['puladas']} | com erro: {len(r['erros'])}")
    for e in r["erros"]:
        print("  -", e)


def cmd_divergencias(a):
    from prospeccao import execucao, revisao

    pasta = execucao.resolver_pasta(a.analise)
    print(json.dumps(revisao.divergencias(pasta), ensure_ascii=False, indent=1))


def cmd_corrigir(a):
    from prospeccao import execucao, exportar

    pasta = execucao.resolver_pasta(a.analise)
    try:
        execucao.corrigir(pasta, a.usuario, a.categorias, a.nota or "", a.descartar, a.revisor)
    except ValueError as e:
        raise SystemExit(str(e))
    exportar.exportar(pasta)
    print("Correção registrada.")


def cmd_classificar(a):
    """Testa a classificação de um perfil informado à mão (não acessa a internet)."""
    from prospeccao.classificar import classificar
    from prospeccao.perfis import Perfil

    p = Perfil(usuario=a.usuario.lstrip("@").lower(), nome=a.nome or "", bio=a.bio or "", categoria_ig=a.categoria_ig or "",
               conta_comercial=True if a.comercial else None, privado=a.privado,
               detalhes="perfil" if (a.bio or a.categoria_ig) else "lista")
    print(json.dumps(classificar(p), ensure_ascii=False, indent=1))


def cmd_sessao(a):
    from prospeccao import sessao

    if a.acao == "definir":
        print("Cole o valor do cookie 'sessionid' do instagram.com (não aparece na tela) e tecle Enter.")
        print("Como achar: no navegador logado no Instagram, F12 > Aplicativo/Armazenamento > Cookies > instagram.com > sessionid")
        valor = getpass.getpass("sessionid: ")
        try:
            sessao.salvar(sessao.de_sessionid(valor), "colada manualmente")
        except ValueError as e:
            raise SystemExit(str(e))
        print("Sessão salva (criptografada) em", config.SESSAO_ARQ)
    elif a.acao == "firefox":
        try:
            sessao.salvar(sessao.importar_firefox(), "importada do Firefox")
        except (FileNotFoundError, LookupError) as e:
            raise SystemExit(str(e))
        print("Sessão importada do Firefox e salva (criptografada) em", config.SESSAO_ARQ)
    elif a.acao == "remover":
        print("Sessão removida." if sessao.remover() else "Não havia sessão salva.")
        return
    d = sessao.descricao()
    print(json.dumps(d, ensure_ascii=False, indent=1))
    if d.get("configurada") and a.acao in ("status", "testar", "definir", "firefox"):
        from prospeccao.coleta import ClienteInstagram, ErroColeta
        c = ClienteInstagram(sessao.carregar())
        try:
            conta = c.conta_logada()
            print(f"Sessão válida: logado como @{conta['usuario']}")
        except ErroColeta as e:
            print(f"Sessão NÃO validada: {e}")
        finally:
            c.fechar()


def main(argv=None):
    _utf8()
    ap = argparse.ArgumentParser(prog="prospeccao", description="Prospecção de parceiros entre os seguidores de um perfil do Instagram")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lista_cats = "; ".join(f"{c.codigo}={c.nome}" for c in cats.CATEGORIAS)

    s = sub.add_parser("analisar", help="Analisa os seguidores de um @")
    s.add_argument("origem", nargs="?", default="", help="@ do perfil de origem (ex.: @feirafuneraria)")
    s.add_argument("--categorias", "-c", default="todas", help=f"Códigos separados por vírgula ou 'todas'. {lista_cats}")
    s.add_argument("--limite", "-l", type=int, help="Máximo de seguidores a analisar")
    s.add_argument("--detalhes", "-d", default="candidatos", choices=["candidatos", "todos", "nenhum"],
                   help="De quem ler bio/categoria: candidatos (padrão), todos ou nenhum")
    s.add_argument("--publicacoes", "-p", default="duvidosos", choices=["duvidosos", "nenhuma"],
                   help="Ler fixados/últimas publicações dos duvidosos e contas comerciais sem categoria (padrão) ou não")
    s.add_argument("--noite", action="store_true",
                   help="Execução prolongada: em limite do Instagram ou queda de rede, aguarda e retoma sozinho (poucas vezes)")
    s.add_argument("--arquivo", help="Em vez de coletar, usa uma lista de @ (.txt/.csv ou followers_*.json da Meta)")
    s.add_argument("--nome", help="Nome da pasta da análise")
    s.add_argument("--preparar", action="store_true", help=argparse.SUPPRESS)
    s.set_defaults(f=cmd_analisar)

    for nome, f, ajuda in (("retomar", cmd_executar, "Continua uma análise interrompida/pausada"),
                           ("executar", cmd_executar, argparse.SUPPRESS)):
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument("analise", nargs="?", help="Pasta ou parte do nome (padrão: a mais recente)")
        s.add_argument("--limite", "-l", type=int, help="Novo limite (0 = sem limite)")
        s.add_argument("--noite", dest="noite", action="store_true", default=None, help="Liga o modo noite")
        s.add_argument("--sem-noite", dest="noite", action="store_false", help="Desliga o modo noite")
        s.set_defaults(f=f)
    for nome, f, ajuda in (("status", cmd_status, "Andamento da análise"), ("exportar", cmd_exportar, "Regera CSV e Markdown"),
                           ("parar", cmd_parar, "Pede para a análise em andamento parar com segurança"),
                           ("reclassificar", cmd_reclassificar, "Reaplica as regras aos perfis já coletados (offline)")):
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument("analise", nargs="?")
        s.set_defaults(f=f)
    sub.add_parser("listar", help="Lista as análises").set_defaults(f=cmd_listar)

    s = sub.add_parser("revisar", help="JSON dos itens do pacote de revisão (pendentes)")
    s.add_argument("analise", nargs="?")
    s.add_argument("--todos", action="store_true", help="Inclui também os já revisados")
    s.add_argument("--incluir", help="revisar,ressalva,comercial_sem_categoria (padrão: todos)")
    s.add_argument("--max", type=int, help="No máximo N itens")
    s.set_defaults(f=cmd_revisar)
    s = sub.add_parser("pacote", help="Gera o pacote de revisão (revisao/pacote.json, pacote.md e decisoes.json)")
    s.add_argument("analise", nargs="?")
    s.add_argument("--incluir", help="revisar,ressalva,comercial_sem_categoria (padrão: todos)")
    s.set_defaults(f=cmd_pacote)
    s = sub.add_parser("aplicar-revisao", help="Aplica as decisões de revisao/decisoes.json (ou --arquivo)")
    s.add_argument("analise", nargs="?")
    s.add_argument("--arquivo")
    s.set_defaults(f=cmd_aplicar_revisao)
    s = sub.add_parser("divergencias", help="Onde a revisão discordou da classificação automática (para ajustar regras)")
    s.add_argument("analise", nargs="?")
    s.set_defaults(f=cmd_divergencias)
    s = sub.add_parser("corrigir", help="Corrige a categoria de um perfil ou o descarta")
    s.add_argument("analise", nargs="?")
    s.add_argument("--usuario", "-u", required=True)
    s.add_argument("--categorias", "-c", help="Categorias corretas (ex.: F,G)")
    s.add_argument("--descartar", action="store_true")
    s.add_argument("--nota")
    s.add_argument("--revisor", default="manual", help="Quem decidiu (ex.: claude, manual)")
    s.set_defaults(f=cmd_corrigir)

    s = sub.add_parser("classificar", help="Testa a classificação de um perfil digitado (offline)")
    s.add_argument("usuario")
    s.add_argument("--nome")
    s.add_argument("--bio")
    s.add_argument("--categoria-ig", dest="categoria_ig")
    s.add_argument("--comercial", action="store_true")
    s.add_argument("--privado", action="store_true")
    s.set_defaults(f=cmd_classificar)

    s = sub.add_parser("sessao", help="Configura a sessão do Instagram (fica fora do projeto, criptografada)")
    s.add_argument("acao", choices=["status", "definir", "firefox", "remover", "testar"])
    s.set_defaults(f=cmd_sessao)

    a = ap.parse_args(argv)
    if getattr(a, "cmd", "") == "corrigir" and not a.descartar and not a.categorias:
        ap.error("informe --categorias ou --descartar")
    a.f(a)
