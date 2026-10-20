"""Pacote de revisão: separa a coleta automática da revisão inteligente (Claude Code pela assinatura, ou uma pessoa).

    revisao/pacote.json      itens que o código não decidiu com segurança, com tudo que foi obtido de cada perfil
    revisao/pacote.md        o mesmo, legível (para ler no chat ou no VS Code)
    revisao/decisoes.json    modelo para preencher as decisões e aplicar com: prospeccao aplicar-revisao ANALISE

Nenhuma decisão é aplicada automaticamente: só o que for registrado (corrigir / aplicar-revisao) muda o resultado,
e cada decisão fica em correcoes.jsonl com nota e revisor. A classificação automática original é preservada.
"""

import json
from pathlib import Path

from prospeccao import categorias as cats
from prospeccao.execucao import _gravar_json, agora, corrigir, ler_config, ler_correcoes, resultados

MOTIVOS = {
    "revisar": "classificação duvidosa (evidência fraca, pessoa física ou perfil privado)",
    "ressalva": "identificado, mas com ressalva (fornecedor do setor, só publicações, bio não lida...)",
    "comercial_sem_categoria": "conta comercial/sinais comerciais sem nenhuma categoria identificada",
}


def _comercial_sem_categoria(r: dict) -> bool:
    p, c = r["perfil"], r["classificacao"]
    return (c["situacao"] == "sem_correspondencia" and p.get("detalhes") == "perfil" and not p.get("privado")
            and c["tipo_perfil"] != "pessoal" and (p.get("conta_comercial") or p.get("categoria_ig")
                                                   or c["tipo_perfil"] in ("empresa", "instituicao", "profissional")))


def _item(r: dict, motivo: str, correcao: dict | None) -> dict:
    p, c = r["perfil"], r["classificacao"]
    contra = [x["limitacao"] for x in c["categorias"] if x.get("limitacao")]
    contra += [s for s in c.get("sinais", []) if s.startswith(("sinal de pessoa", "perfil privado", "menciona", "atua para"))]
    return {
        "usuario": p["usuario"], "link": c["link"], "nome": p.get("nome", ""), "bio": p.get("bio", ""),
        "categoria_instagram": p.get("categoria_ig", ""),
        "comercial": {"conta_comercial": p.get("conta_comercial"), "link_externo": p.get("link_externo", ""),
                      **(p.get("extras") or {})},
        "publicacoes": [{"fixado": x.get("fixado"), "texto": (x.get("texto") or "")[:280], "hashtags": x.get("hashtags", [])[:15],
                         "local": x.get("local", "")} for x in (p.get("posts") or [])],
        "destaques": p.get("destaques", []),
        "erro_publicacoes": p.get("erro_publicacoes", ""),
        "etapas_executadas": c.get("etapas") or p.get("etapas") or [],
        "fontes_usadas": c.get("fontes", []),
        "tipo_perfil": c["tipo_perfil"], "estado_analise": c["estado_analise"],
        "situacao_automatica": (r.get("classificacao_automatica") or c)["situacao"],
        "categorias_consideradas": [{k: x.get(k) for k in ("codigo", "nome", "confianca", "pontuacao", "evidencias", "limitacao")
                                     if x.get(k) not in (None, "")} for x in (r.get("classificacao_automatica") or c)["categorias"]],
        "motivo_da_duvida": MOTIVOS[motivo], "evidencias_contra": contra,
        "estado_revisao": "revisado" if correcao else "pendente",
        **({"decisao": {"descartar": correcao["descartar"], "categorias": correcao["categorias"], "nota": correcao.get("nota", ""),
                        "revisor": correcao.get("revisor", "")}} if correcao else {}),
    }


def montar(pasta: Path, incluir: list[str] | None = None) -> list[dict]:
    incluir = incluir or list(MOTIVOS)
    corr = ler_correcoes(pasta)
    itens = []
    for r in resultados(pasta):
        auto = r.get("classificacao_automatica") or r["classificacao"]
        if auto["situacao"] == "revisar":
            motivo = "revisar"
        elif auto["situacao"] == "identificado" and any(x.get("limitacao") for x in auto["categorias"]
                                                        if x["confianca"] != "baixa"):
            motivo = "ressalva"
        elif _comercial_sem_categoria(dict(r, classificacao=auto)):
            motivo = "comercial_sem_categoria"
        else:
            continue
        if motivo in incluir:
            itens.append(_item(dict(r, classificacao=auto), motivo, corr.get(r["perfil"]["usuario"])))
    ordem = {k: i for i, k in enumerate(MOTIVOS)}
    inv = {v: k for k, v in MOTIVOS.items()}
    itens.sort(key=lambda i: (i["estado_revisao"] != "pendente", ordem[inv[i["motivo_da_duvida"]]], i["usuario"]))
    return itens


def _md(pasta: Path, itens: list[dict]) -> str:
    cfg = ler_config(pasta)
    pend = sum(1 for i in itens if i["estado_revisao"] == "pendente")
    linhas = [f"# Pacote de revisão — @{cfg.get('origem') or '(lista)'}", "",
              f"Gerado em {agora()} · {len(itens)} itens · {pend} pendentes.", "",
              "Categorias: " + "; ".join(f"{c.codigo}={c.nome}" for c in cats.CATEGORIAS), "",
              "Para registrar decisões: preencha `revisao/decisoes.json` e rode `prospeccao aplicar-revisao`, "
              "ou use `prospeccao corrigir -u @X -c F,G --nota \"...\"` / `--descartar`.", ""]
    atual = None
    for i in itens:
        if i["motivo_da_duvida"] != atual:
            atual = i["motivo_da_duvida"]
            linhas += [f"## {atual[0].upper() + atual[1:]}", ""]
        cats_txt = "; ".join(f"{c['codigo']} {c.get('confianca', '')}: {', '.join(c.get('evidencias', [])[:3])}"
                             + (f" [{c['limitacao']}]" if c.get("limitacao") else "") for c in i["categorias_consideradas"]) or "nenhuma"
        linhas.append(f"### @{i['usuario']} — {i['nome'] or '(sem nome)'}  ·  {i['estado_revisao']}")
        linhas.append(f"- Link: {i['link']}")
        linhas.append(f"- Bio: {(i['bio'] or '(vazia)').replace(chr(10), ' / ')}")
        if i["categoria_instagram"]:
            linhas.append(f"- Categoria do Instagram: {i['categoria_instagram']}")
        com = {k: v for k, v in i["comercial"].items() if v not in (None, "", False)}
        if com:
            linhas.append(f"- Comercial: {json.dumps(com, ensure_ascii=False)}")
        linhas.append(f"- Tipo: {i['tipo_perfil']} · análise: {i['estado_analise']} · etapas: {', '.join(i['etapas_executadas'])}")
        linhas.append(f"- Categorias consideradas: {cats_txt}")
        if i["evidencias_contra"]:
            linhas.append(f"- Contra/ressalvas: {'; '.join(i['evidencias_contra'])}")
        for x in i["publicacoes"][:6]:
            tags = (" #" + " #".join(x["hashtags"][:6])) if x["hashtags"] else ""
            local = f" @ {x['local']}" if x["local"] else ""
            linhas.append(f"  - {'📌 ' if x['fixado'] else ''}{(x['texto'] or '(sem legenda)')[:160].replace(chr(10), ' ')}{tags}{local}")
        if i["destaques"]:
            linhas.append(f"- Destaques: {', '.join(i['destaques'][:12])}")
        if i.get("decisao"):
            d = i["decisao"]
            linhas.append(f"- **Decisão**: {'descartar' if d['descartar'] else ', '.join(d['categorias'])} — {d['nota']} ({d['revisor']})")
        linhas.append("")
    return "\n".join(linhas)


def gerar(pasta: Path, incluir: list[str] | None = None) -> dict[str, Path]:
    itens = montar(pasta, incluir)
    d = pasta / "revisao"
    d.mkdir(exist_ok=True)
    _gravar_json(d / "pacote.json", {"analise": pasta.name, "gerado_em": agora(), "categorias": {c.codigo: c.nome for c in cats.CATEGORIAS},
                                     "itens": itens})
    (d / "pacote.md").write_text(_md(pasta, itens), encoding="utf-8")
    modelo = d / "decisoes.json"
    if not modelo.exists():  # nunca sobrescreve decisões já preenchidas
        _gravar_json(modelo, {"instrucoes": "decisao: confirmar | corrigir | descartar | pular. categorias: códigos A-M "
                                            "(obrigatório em confirmar/corrigir). nota: motivo curto.",
                              "revisor": "claude",
                              "decisoes": [{"usuario": i["usuario"], "decisao": "pular", "categorias": [], "nota": ""}
                                           for i in itens if i["estado_revisao"] == "pendente"]})
    return {"json": d / "pacote.json", "md": d / "pacote.md", "decisoes": modelo}


def aplicar(pasta: Path, arquivo: Path | None = None) -> dict:
    """Aplica decisoes.json (ou outro arquivo no mesmo formato). Devolve contagens; erros por item não param o lote."""
    arquivo = arquivo or pasta / "revisao" / "decisoes.json"
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    revisor = dados.get("revisor", "manual")
    cont = {"aplicadas": 0, "puladas": 0, "erros": []}
    for d in dados.get("decisoes", []):
        dec = (d.get("decisao") or "pular").lower()
        try:
            if dec == "pular":
                cont["puladas"] += 1
                continue
            if dec == "descartar":
                corrigir(pasta, d["usuario"], None, d.get("nota", ""), descartar=True, revisor=revisor)
            elif dec in ("confirmar", "corrigir"):
                if not d.get("categorias"):
                    raise ValueError("informe as categorias")
                corrigir(pasta, d["usuario"], d["categorias"], d.get("nota", ""), revisor=revisor)
            else:
                raise ValueError(f"decisão desconhecida: {dec}")
            cont["aplicadas"] += 1
        except (ValueError, KeyError) as e:
            cont["erros"].append(f"@{d.get('usuario', '?')}: {e}")
    return cont


def divergencias(pasta: Path) -> list[dict]:
    """Onde a revisão discordou da classificação automática: material para novos testes e ajuste de regras."""
    saida = []
    for r in resultados(pasta):
        if not r["classificacao"].get("revisado"):
            continue
        auto = r["classificacao_automatica"]
        fortes = sorted(c["codigo"] for c in auto["categorias"] if c["confianca"] != "baixa")
        final = sorted(c["codigo"] for c in r["classificacao"]["categorias"])
        if fortes != final:
            saida.append({"usuario": r["perfil"]["usuario"], "automatico": fortes or ["nenhuma"], "revisado": final or ["descartado"],
                          "situacao_automatica": auto["situacao"], "nota": r["classificacao"].get("revisao", ""),
                          "bio": r["perfil"].get("bio", "")[:200], "categoria_ig": r["perfil"].get("categoria_ig", "")})
    return saida
