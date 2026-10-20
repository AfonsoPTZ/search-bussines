"""Exportação: CSV (separado por ';', abre direto no Excel em português) e lista de @ por categoria em Markdown."""

import csv
from pathlib import Path

from prospeccao import categorias as cats
from prospeccao.execucao import resultados, resumo

COLUNAS = [
    ("categoria_codigo", "Código"), ("categoria", "Categoria"), ("instagram", "Instagram"), ("nome", "Nome do perfil"),
    ("link", "Link"), ("situacao", "Situação"), ("confianca", "Confiança"), ("pontuacao", "Pontuação"),
    ("evidencias", "Evidências"), ("limitacao", "Limitação"), ("tipo_perfil", "Tipo de perfil"),
    ("estado_analise", "Estado da análise"), ("categoria_instagram", "Categoria no Instagram"),
    ("conta_comercial", "Conta comercial"), ("bio", "Bio"), ("link_externo", "Link externo"),
    ("outras_categorias", "Outras categorias"), ("revisao", "Nota de revisão"), ("etapas", "Etapas"),
    ("fontes", "Fontes"), ("prioridade", "Prioridade na triagem"),
]


def linhas(pasta: Path, incluir_revisar: bool = True) -> list[dict]:
    """Uma linha por (perfil, categoria). Perfis em mais de uma categoria aparecem uma vez em cada uma."""
    saida = []
    ordem = {c: i for i, c in enumerate(cats.CODIGOS)}
    for r in resultados(pasta):
        cls, p = r["classificacao"], r["perfil"]
        if cls["situacao"] not in ("identificado", "revisar") or (cls["situacao"] == "revisar" and not incluir_revisar):
            continue
        for c in cls["categorias"]:
            sit = "identificado" if cls["situacao"] == "identificado" and c["confianca"] != "baixa" else "revisar"
            if sit == "revisar" and not incluir_revisar:
                continue
            saida.append({
                "categoria_codigo": c["codigo"], "categoria": c["nome"], "instagram": "@" + p["usuario"],
                "nome": p.get("nome", ""), "link": cls["link"], "situacao": sit, "confianca": c["confianca"],
                "pontuacao": f"{c['pontuacao']:g}", "evidencias": " | ".join(c["evidencias"]),
                "limitacao": c.get("limitacao", ""), "tipo_perfil": cls["tipo_perfil"],
                "estado_analise": cls["estado_analise"], "categoria_instagram": p.get("categoria_ig", ""),
                "conta_comercial": {True: "sim", False: "não"}.get(p.get("conta_comercial"), ""),
                "bio": (p.get("bio") or "").replace("\n", " "), "link_externo": p.get("link_externo", ""),
                "outras_categorias": ", ".join(x["codigo"] for x in cls["categorias"] if x["codigo"] != c["codigo"]),
                "revisao": cls.get("revisao", ""),
                "etapas": ", ".join(p.get("etapas") or cls.get("etapas") or []),
                "fontes": "; ".join(cls.get("fontes") or []),
                "prioridade": (p.get("triagem") or {}).get("motivo", ""),
            })
    saida.sort(key=lambda l: (ordem[l["categoria_codigo"]], l["situacao"] != "identificado", -float(l["pontuacao"]), l["instagram"]))
    return saida


def csv_texto(pasta: Path) -> str:
    import io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow([t for _, t in COLUNAS])
    for l in linhas(pasta):
        w.writerow([l[k] for k, _ in COLUNAS])
    return buf.getvalue()


def markdown(pasta: Path) -> str:
    rs = resumo(pasta)
    cfg, est = rs["config"], rs["estado"]
    titulo = f"@{cfg['origem']}" if cfg.get("origem") else f"lista {Path(cfg.get('arquivo', '')).name}"
    out = [f"# Seguidores de {titulo} por categoria", "",
           f"- Analisados: {est.get('processados', 0)} · identificados: {rs['identificados']} · para revisar: {rs['revisar']}",
           f"- Situação da execução: {est.get('status', '-')}", ""]
    for cod in cfg["categorias"]:
        grupo = rs["por_categoria"][cod]
        out.append(f"## {cats.POR_CODIGO[cod].nome}")
        out.append("")
        if not grupo["identificados"] and not grupo["revisar"]:
            out += ["_Nenhum perfil encontrado._", ""]
            continue
        for r, c in grupo["identificados"]:
            out.append(f"- `@{r['perfil']['usuario']}` — {r['perfil'].get('nome') or ''} ({c['confianca']})")
        if grupo["revisar"]:
            out.append("")
            out.append("Possíveis correspondências (revisar):")
            out.append("")
            for r, c in grupo["revisar"]:
                out.append(f"- `@{r['perfil']['usuario']}` — {r['perfil'].get('nome') or ''} ({'; '.join(c['evidencias'][:2])})")
        out.append("")
    return "\n".join(out)


def exportar(pasta: Path) -> dict[str, Path]:
    arquivos = {"csv": pasta / "resultados.csv", "md": pasta / "arrobas_por_categoria.md"}
    arquivos["csv"].write_text(csv_texto(pasta), encoding="utf-8-sig", newline="")
    arquivos["md"].write_text(markdown(pasta), encoding="utf-8")
    return arquivos
