"""Revisão pelo Claude Code (a mesma revisão das skills pesquisa-empresas e prospeccao-instagram).

Duas formas, à sua escolha na interface:
  * "Copiar pedido": texto pronto para colar no chat do Claude Code (nada roda sem você ver);
  * "Revisar em segundo plano": roda o Claude Code sem interação (`claude -p`), com a sua assinatura, permitindo SÓ
    o executável da ferramenta (e busca na web, para empresas). Qualquer outra ferramenta é negada automaticamente
    (--permission-mode dontAsk). A saída fica em dados/claude/<execução>/ e o andamento aparece em Execuções.

O Claude registra as decisões pelos comandos `corrigir` das ferramentas, com fonte e nota; a plataforma só lê.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from plataforma import config

TEMPO_MAXIMO_S = 60 * 60  # uma revisão não fica rodando indefinidamente
MAX_ITENS_PADRAO = {"empresas": 15, "instagram": 40}


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def localizar() -> Path | None:
    """claude.exe: variável PLATAFORMA_CLAUDE, o PATH ou a versão mais nova da extensão do VS Code."""
    if os.environ.get("PLATAFORMA_CLAUDE"):
        p = Path(os.environ["PLATAFORMA_CLAUDE"])
        return p if p.is_file() else None
    achado = shutil.which("claude")
    if achado:
        return Path(achado)
    exts = Path.home() / ".vscode" / "extensions"
    candidatos = []
    for d in exts.glob("anthropic.claude-code-*"):
        exe = d / "resources" / "native-binary" / ("claude.exe" if os.name == "nt" else "claude")
        m = re.search(r"claude-code-(\d+)\.(\d+)\.(\d+)", d.name)
        if exe.is_file() and m:
            candidatos.append((tuple(int(x) for x in m.groups()), exe))
    return max(candidatos)[1] if candidatos else None


def _raiz(tipo: str) -> Path:
    """Pasta da ferramenta (o Claude roda nela: lê o CLAUDE.md dela e usa caminhos relativos)."""
    if tipo == "empresas":
        from empresas import config as c
    else:
        from prospeccao import config as c
    return c.ROOT


def _comando(tipo: str) -> tuple[str, list[str]]:
    """Comando da ferramenta e as permissões do Bash. Com caminho relativo simples (sem espaço nem parêntese), as
    permissões são por PREFIXO exato (só revisar, corrigir e exportar); senão, cai para o nome do executável."""
    nome = "empresas" if tipo == "empresas" else "prospeccao"
    exe = Path(sys.executable).parent / (nome + (".exe" if os.name == "nt" else ""))
    try:
        rel = os.path.relpath(exe, _raiz(tipo)).replace("\\", "/")
    except ValueError:  # outra unidade de disco
        rel = ""
    if rel and not any(c in rel for c in ' ()"\'&;|'):
        return rel, [f"Bash({rel} {sub}:*)" for sub in ("revisar", "corrigir", "exportar")]
    absoluto = str(exe).replace("\\", "/")
    return f'"{absoluto}"', [f"Bash(*{nome}.exe*)"]


def _alvo(alvo: str) -> tuple[str, Path, str]:
    from plataforma import sincronizar
    achado = sincronizar.pasta_da_execucao(alvo)
    if not achado or achado[0] not in ("empresas", "instagram"):
        raise ValueError("Escolha um lote de empresas ou uma análise do Instagram.")
    tipo, pasta = achado
    return tipo, pasta, pasta.name


def pedido_chat(alvo: str, max_itens: int | None = None) -> str:
    tipo, _, nome = _alvo(alvo)
    n = max_itens or MAX_ITENS_PADRAO[tipo]
    if tipo == "empresas":
        return (f'/pesquisa-empresas Revise o lote "{nome}" (etapa 3: revisar os incertos com fonte, registrar com corrigir '
                f'e exportar). Revise no máximo {n} itens, priorizando provável > parcial > confiança baixa.')
    return (f'/prospeccao-instagram Revise os casos duvidosos da análise "{nome}" (no máximo {n} itens), registre as decisões '
            f'com nota e revisor claude, aplique e exporte.')


def _prompt(tipo: str, nome: str, n: int) -> tuple[str, list[str]]:
    if tipo == "empresas":
        exe, regras = _comando("empresas")
        texto = f"""Você está revisando, sem interação com o usuário, um lote da ferramenta local de pesquisa de empresas.
Siga as regras da skill pesquisa-empresas (etapa 3 "Revisar o que ficou incerto" e "Regras").
Executável (use exatamente assim, no início do comando): {exe}
Lote (use em TODOS os comandos): "{nome}"

1. Rode: {exe} revisar "{nome}"
2. Revise no máximo {n} itens, priorizando provavel > parcial > confiança baixa.
3. Investigue com WebSearch/WebFetch (site oficial, contato, política de privacidade, perfil). Só confirme com uma URL que
   comprove. Na dúvida mantenha o dado como não confirmado; remova só o que tiver evidência de estar errado.
4. Registre cada achado com {exe} corrigir "{nome}" --linha N --campo C ... sempre com --fonte <URL> e --nota.
5. Não mexa em outros lotes, não invente dados, não colete dados pessoais, não contorne CAPTCHA/login.
6. Termine com um resumo curto (até 15 linhas): itens revisados, o que foi confirmado e o que segue incerto."""
        return texto, regras + ["WebSearch", "WebFetch", "Skill"]
    exe, regras = _comando("instagram")
    texto = f"""Você está revisando, sem interação com o usuário, os casos duvidosos de uma análise de seguidores do Instagram
(ferramenta prospeccao). Siga a skill prospeccao-instagram (seção 2 "Revisar").
Executável (use exatamente assim, no início do comando): {exe}
Análise (use em TODOS os comandos): "{nome}"

1. Rode: {exe} revisar "{nome}" --max {n}
2. Para cada item decida só com o que está no pacote (bio, categoria do Instagram, publicações, destaques), pelas 13
   categorias: A placas/lápides/fotoporcelana · B cemitérios pet · C cemitérios · D floriculturas · E crematórios/funerárias
   pet · F crematórios/funerárias humanas · G seguro de vida/planos funerários · H clínicas/hospitais vet · I pet shops/
   serviços pet · J igrejas · K hospitais/paliativos · L apoio ao luto · M psicólogos/terapeutas do luto.
3. Registre cada decisão com:
   {exe} corrigir "{nome}" -u USUARIO -c F,G --nota "motivo curto" --revisor claude
   ou {exe} corrigir "{nome}" -u USUARIO --descartar --nota "motivo" --revisor claude
   Sem informação suficiente: não registre nada (fica pendente). Fornecedor do setor: categoria mais próxima e "fornecedor" na nota.
4. Ao final rode: {exe} exportar "{nome}"
5. Termine com um resumo curto (até 15 linhas): decididos, descartados e pendentes."""
    return texto, regras + ["Skill"]


def preparar(alvo: str, max_itens: int | None = None) -> Path:
    tipo, pasta_alvo, nome = _alvo(alvo)
    if not localizar():
        raise ValueError("Claude Code não encontrado. Instale a extensão do VS Code ou defina PLATAFORMA_CLAUDE com o "
                         "caminho do claude.exe. Enquanto isso, use 'Copiar pedido' e cole no chat.")
    n = max(1, min(int(max_itens or MAX_ITENS_PADRAO[tipo]), 100))
    prompt, ferramentas = _prompt(tipo, nome, n)
    config.CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    pasta = config.CLAUDE_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}_{re.sub(r'[^a-z0-9-]+', '-', nome.lower())[:50]}"
    pasta.mkdir()
    (pasta / "config.json").write_text(json.dumps({
        "alvo": alvo, "modo": tipo, "max_itens": n, "criado": _agora(), "ferramentas": ferramentas, "prompt": prompt,
        "cwd": str(_raiz(tipo)), "descricao": f"Revisão pelo Claude de {nome} (até {n} itens)"},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "estado.json").write_text(json.dumps({"status": "criado"}), encoding="utf-8")
    return pasta


def iniciar(alvo: str, max_itens: int | None = None) -> str:
    from plataforma import acoes, db, sincronizar
    con = db.conexao()
    ativa = con.execute("SELECT id FROM execucoes WHERE tipo='revisao_claude' AND em_andamento=1 AND origem_execucao=?",
                        (alvo,)).fetchone()
    if ativa:
        raise ValueError("Já existe uma revisão pelo Claude em andamento para esta execução.")
    pasta = preparar(alvo, max_itens)
    acoes.iniciar_processo([config.PYTHON, "-m", "plataforma", "claude-executar", str(pasta)], config.ROOT, pasta / "log.txt")
    sincronizar.sincronizar_execucao(con, "revisao_claude", pasta, forcar=True)
    return "claude:" + pasta.name


# ----------------------------------------------------------------------------------------- execução (processo separado)

def _gravar(pasta: Path, est: dict):
    est["atualizado"] = _agora()
    tmp = pasta / "estado.json.tmp"
    tmp.write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(pasta / "estado.json")


def _resumir_ferramenta(bloco: dict) -> str:
    entrada = bloco.get("input") or {}
    if bloco.get("name") == "Bash":
        cmd = str(entrada.get("command", ""))
        cmd = re.sub(r'"[^"]*?(empresas|prospeccao)\.exe"', r"\1", cmd)
        return cmd[:200]
    if bloco.get("name") in ("WebSearch", "WebFetch"):
        return f"{bloco['name']}: {entrada.get('query') or entrada.get('url') or ''}"[:200]
    return str(bloco.get("name", ""))


def executar(pasta: Path, comando=None) -> int:
    """Roda o Claude Code com o pedido preparado, acompanha a saída e grava o estado. `comando` serve aos testes."""
    cfg = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    est = {"status": "executando", "iniciado": _agora(), "pid": os.getpid(), "comandos": 0, "mensagem": "iniciando"}
    _gravar(pasta, est)
    exe = localizar()
    if comando is None:
        if not exe:
            est.update(status="falhou", finalizado=_agora(), mensagem="Claude Code não encontrado")
            _gravar(pasta, est)
            return 1
        comando = [str(exe), "-p", cfg["prompt"], "--output-format", "stream-json", "--verbose",
                   "--permission-mode", "dontAsk", "--allowedTools", *cfg["ferramentas"]]
    t0 = time.time()
    lock = threading.Lock()
    fim = threading.Event()
    proc = subprocess.Popen(comando, cwd=cfg.get("cwd") or None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def vigia():  # batimento, pedido de parada e tempo máximo
        while not fim.wait(15):
            with lock:
                if (pasta / "parar").exists() or time.time() - t0 > TEMPO_MAXIMO_S:
                    est["mensagem"] = "parada pedida" if (pasta / "parar").exists() else "tempo máximo atingido"
                    proc.terminate()
                est["duracao_s"] = round(time.time() - t0)
                _gravar(pasta, est)

    threading.Thread(target=vigia, daemon=True).start()
    resultado = None
    with open(pasta / "saida.jsonl", "a", encoding="utf-8") as saida, open(pasta / "log.txt", "a", encoding="utf-8") as log:
        for linha in proc.stdout:
            saida.write(linha)
            saida.flush()
            try:
                ev = json.loads(linha)
            except ValueError:
                log.write(linha)
                continue
            with lock:
                if ev.get("type") == "assistant":
                    for b in (ev.get("message") or {}).get("content") or []:
                        if b.get("type") == "tool_use":
                            est["comandos"] += 1
                            est["ultima_acao"] = _resumir_ferramenta(b)
                            log.write(f"[{_agora()}] {est['ultima_acao']}\n")
                        elif b.get("type") == "text" and b.get("text"):
                            est["mensagem"] = b["text"].strip()[:300]
                elif ev.get("type") == "result":
                    resultado = ev
                _gravar(pasta, est)
            log.flush()
    codigo = proc.wait()
    fim.set()
    with lock:
        parou = (pasta / "parar").exists()
        (pasta / "parar").unlink(missing_ok=True)
        est["duracao_s"] = round(time.time() - t0)
        if resultado is not None:
            est["resultado"] = resultado.get("result") or ""
            est["turnos"] = resultado.get("num_turns")
            erro = resultado.get("is_error") or resultado.get("subtype") not in (None, "success")
            est["status"] = "falhou" if erro else "concluido"
            est["mensagem"] = (resultado.get("subtype") or "") if erro else "revisão concluída"
        else:
            est["status"] = "interrompido" if parou else "falhou"
            est["mensagem"] = est.get("mensagem") if parou else f"o Claude Code terminou sem resultado (código {codigo})"
        est["finalizado"] = _agora()
        _gravar(pasta, est)
    return 0 if est["status"] == "concluido" else 1
