"""Linha de comando: plataforma <comando>  (use 'plataforma -h')."""

import argparse
import json
import sys


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except AttributeError:
            pass


def cmd_painel(a):
    from plataforma import servidor
    servidor.servir(a.porta, abrir=not a.sem_navegador)


def cmd_sincronizar(a):
    import time

    from plataforma import config, sincronizar
    t = time.time()
    r = sincronizar.sincronizar(forcar=a.completa)
    print(f"Banco: {config.db_arquivo()}")
    print(f"Sincronização em {time.time() - t:.1f}s: {json.dumps(r, ensure_ascii=False)}")


def cmd_resumo(a):
    from plataforma import consultas, sincronizar
    sincronizar.sincronizar()
    print(json.dumps(consultas.visao_geral(), ensure_ascii=False, indent=1, default=str))


def cmd_fila(a):
    """Fila de pesquisa: perfis identificados no Instagram esperando os dados da empresa."""
    from plataforma import acoes, fila, sincronizar
    sincronizar.sincronizar()
    segs = [s for s in (a.segmentos or "").replace(";", ",").split(",") if s.strip()]

    if a.acao == "resumo":
        print(json.dumps(fila.resumo(), ensure_ascii=False, indent=1))
        return 0

    if a.acao == "listar":
        itens = fila.listar(a.estado, segs, a.execucao or "", a.limite)
        if a.json:
            print(json.dumps(itens, ensure_ascii=False, indent=1, default=str))
            return 0
        if not itens:
            print(f"Nenhum perfil na fila com estado '{a.estado}'.")
            return 0
        print(f"{len(itens)} perfil(is) — estado '{a.estado}', mais antigos primeiro:\n")
        for i in itens:
            print(f"  {i['linha']}" + (f"   [{','.join(i['segmentos'])}]" if i["segmentos"] else "")
                  + (f"   analise {i['analise']}" if i.get("analise") else ""))
        return 0

    if a.acao == "pesquisar":
        try:
            eid = acoes.pesquisar_fila(a.limite, segs or None, a.incluir_pesquisadas)
        except acoes.AcaoInvalida as e:
            print(f"Nada a fazer: {e}")
            return 0
        print(f"Pesquisa de empresas iniciada: {eid}")
        print("Acompanhe com:  plataforma fila resumo   |   na interface: http://127.0.0.1:8770/#/execucoes")
        return 0

    if a.acao == "dispensar":
        if not a.usuarios:
            print("Informe ao menos um @ (ex.: plataforma fila dispensar @fulano --motivo 'não é empresa').")
            return 1
        n = fila.marcar(a.usuarios, "dispensado", motivo=a.motivo or "dispensado pela linha de comando")
        print(f"{n} perfil(is) dispensado(s) da fila.")
        return 0

    if a.acao == "reabrir":
        n = fila.marcar(a.usuarios or [], "pendente")
        print(f"{n} perfil(is) devolvido(s) à fila.")
        return 0
    return 1


def cmd_claude_executar(a):
    """Usado pela plataforma: roda uma revisão pelo Claude Code já preparada (pasta em dados/claude)."""
    from pathlib import Path

    from plataforma import claude
    return claude.executar(Path(a.pasta))


def main(argv=None):
    _utf8()
    p = argparse.ArgumentParser(prog="plataforma", description="Plataforma local de prospecção (Instagram + empresas).")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("painel", help="abre a interface (http://127.0.0.1:8770)")
    from plataforma import config
    s.add_argument("--porta", type=int, default=config.PORTA)
    s.add_argument("--sem-navegador", action="store_true")
    s.set_defaults(func=cmd_painel)
    s = sub.add_parser("sincronizar", help="lê as pastas de resultados e atualiza o banco de consulta")
    s.add_argument("--completa", action="store_true", help="reimporta tudo, mesmo o que não mudou")
    s.set_defaults(func=cmd_sincronizar)
    sub.add_parser("resumo", help="visão geral em JSON").set_defaults(func=cmd_resumo)
    s = sub.add_parser("fila", help="fila de pesquisa: perfis do Instagram esperando os dados da empresa")
    s.add_argument("acao", choices=["listar", "resumo", "pesquisar", "dispensar", "reabrir"], nargs="?", default="listar")
    s.add_argument("usuarios", nargs="*", help="@ dos perfis (para dispensar/reabrir)")
    s.add_argument("--estado", default="pendente", help="pendente (padrão) | pesquisando | concluido | dispensado | todos")
    s.add_argument("--segmentos", default="", help="filtrar por segmentos A–M, separados por vírgula")
    s.add_argument("--execucao", default="", help="só os de uma análise do Instagram")
    s.add_argument("--limite", type=int, default=None, help="quantos itens no máximo")
    s.add_argument("--incluir-pesquisadas", action="store_true", help="não pular quem já foi pesquisado há pouco")
    s.add_argument("--motivo", default="", help="por que está dispensando")
    s.add_argument("--json", action="store_true", help="saída em JSON (para o Claude Code)")
    s.set_defaults(func=cmd_fila)
    s = sub.add_parser("claude-executar", help=argparse.SUPPRESS)
    s.add_argument("pasta")
    s.set_defaults(func=cmd_claude_executar)
    a = p.parse_args(argv)
    return a.func(a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
