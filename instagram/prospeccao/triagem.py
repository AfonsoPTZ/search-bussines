"""Triagem em etapas: decide, só com o @ e o nome da lista de seguidores, quem merece leitura do perfil e em que ordem.

Prioridades (menor = lido primeiro):
    0 segmento      termo de algum dos 13 segmentos no @ ou no nome (ex.: "funerariax", "Pax Santa Clara")
    1 comercial     nome com cara de empresa/instituição (ex.: "Grupo Xyz", "Complexo Salvatore", "HMS inox")
    2 profissional  nome de pessoa com cargo/serviço (ex.: "Guilherme | Consultor Comercial", "Dra. Ana")
    3 indefinido    não parece nome de pessoa nem de empresa (ex.: "@ossel.compreagora", "FADEDSFYA")
    4 pessoa        parece nome de pessoa (ex.: "João Pereira", "maria_silva_89") — NÃO é descartado
    9 privado       conta privada (o Instagram não permite conta comercial privada)

Quanto ler em cada modo (ajustável em triagem.json, veja README):
    candidatos  prioridades 0 a 3 (padrão)     todos  0 a 4     nenhum  só classifica pelo @ e nome
"""

import json
import os
import re
from pathlib import Path

from prospeccao import config
from prospeccao.perfis import Perfil, normalizar_texto

SEGMENTO, COMERCIAL, PROFISSIONAL, INDEFINIDO, PESSOA, PRIVADO = 0, 1, 2, 3, 4, 9
ROTULOS = {SEGMENTO: "segmento", COMERCIAL: "comercial", PROFISSIONAL: "profissional", INDEFINIDO: "indefinido",
           PESSOA: "pessoa", PRIVADO: "privado"}

# Prenomes frequentes (Brasil, América Latina e inglês). Servem só para ORDENAR a leitura; nunca para descartar.
PRENOMES = set("""
adriana adriano agatha alan alana alessandra alex alexandre alice aline allan amanda ana anderson andre andrea andreia
andressa angela angelica anna antonio aparecida ariane arthur augusto aurora barbara beatriz benedito benjamin bernardo
beto bia bianca bruna bruno caio camila camille carla carlos carlo carmem carol carolina caroline cassia catarina cecilia
celia celso cesar charles cicero cintia clara claudia claudio cleber cleide cristian cristiane cristina daiane daniel
daniela daniele danielle danilo dario davi david debora denise diana diego diogo douglas duda edson eduarda eduardo
elaine elias eliane elis elisa elisangela eliza ellen emanuel emanuelly emerson emilia emily enzo erica erick erika
estela ester esther evelyn everton fabiana fabiano fabio fabricio fatima felipe fernanda fernando flavia flavio
francisca francisco gabriel gabriela gabriele gabrielle geovana geraldo gilberto gilmar giovana giovanna giovanni gisele
glaucia gloria graziela guilherme gustavo heitor helena helio henrique heloisa hugo iara igor ingrid iris isaac isabel
isabela isabella isabelle isadora ivan ivone jaqueline jessica joana joao joaquim joel jonas jonatas jorge jose josiane
joyce juan julia juliana juliano julio jussara karen karina karla katia kauan kaue kelly kevin laila lais lara larissa
laura leandro leila leonardo leticia lidia lilian liliane livia lorena lorenzo luan luana lucas lucia luciana luciano
lucio luis luisa luiz luiza luna maite manoel manuel manuela marcela marcelo marcia marcio marco marcos margarida maria
mariana marina mario marisa marlene marta mateus matheus mauricio mauro mayara melissa michael michele michelle miguel
milena miriam mirian monica murilo natalia natalie nathalia nelson nicolas nicole nilton noah otavio pamela patricia
paula paulo pedro priscila rafael rafaela raimundo raquel raul rebeca regina reginaldo renan renata renato ricardo
rita roberta roberto robson rodrigo rogerio ronaldo rosa rosana rosangela rose rosimeire rubens ruth sabrina samara samuel
sandra sara sarah sebastiao sergio silvana silvia simone sofia solange sonia sophia stefany sueli suelen tais talita
tatiana tatiane thais thiago tiago valeria vanessa vania vera veronica vicente victor vinicius vitor vitoria viviane
wagner walter wanderson wellington wesley william willian yasmin yuri zeca zilda
alejandro alberto alfonso andres camilo carmen consuelo diego emilio esteban facundo federico florencia gonzalo ignacio
javier jesus jimena joaquin lucia martina martin matias mercedes nahuel pablo ramon rocio santiago sebastian sergio
valentina valentin ximena
anthony brian chris christopher david emma george jack james jennifer john joseph kate katie linda mark mary matt
michael paul peter richard robert sam sarah steve thomas tom
""".split())

_COMERCIAL = re.compile(
    r"\b(?:ltda|eireli|cia|comercio|servicos|grupo|centro|clinica|instituto|associacao|loja|lojas|studio|atelie|oficial|"
    r"empresa|agencia|consultoria|assistencia|assistencial|memorial|memorias|parque|plano|planos|saude|cuidar|cuidados|vida|paz|"
    r"eterno|eterna|saudade|descanso|homenagem|homenagens|jardim|bosque|campo|santa|santo|sao|nossa senhora|capela|comunidade|"
    r"rede|projeto|distribuidora|industria|fabrica|artes?|pedras?|brasil|complexo|equipamentos|produtos|solucoes|sistemas|"
    r"tecnologia|tech|store|shop|home|company|inc|llc|group|corp|imports?|express|log|delivery|digital|"
    r"official|marketing|cursos?|treinamentos?|eventos|cerimonial|personalizados?|presentes|decor|design|moveis|inox|bronze|"
    r"marmores?|granitos?|fundicao|metalurgica|transportes?|translados?|prev|pax|santuario|recanto|lar|casa)\b")
_CARGO = re.compile(
    r"\b(?:dra?|doutor[a]?|psi|psicolog[oa]|psicoterapeuta|terapeuta|\w*terapeuta|vet|veterinari[oa]|corretor[a]?|consultor[a]?|"
    r"agente|tanatopraxista|florista|celebrante|cerimonialista|advogad[oa]|adv|enfermeir[oa]|medic[oa]|pastor[a]?|padre|"
    r"designer|fotografo|arquitet[oa]|contador[a]?|ceo|fundador[a]?|empresari[oa]|gestor[a]?|tecnic[oa]|especialista|"
    r"terapias?|servicos|servicios|atendimento|consultoria|cursos?|professor[a]?)\b")

PADRAO = {
    "ler_ate_prioridade": {"candidatos": INDEFINIDO, "todos": PESSOA, "nenhum": -1},
    "ler_privados": False,             # contas privadas não podem ser comerciais; ler só se quiser revisar pessoas
    "palavras_comerciais_extras": [],  # ex.: ["velorio", "assist"] (sem acento, minúsculas)
    "prenomes_extras": [],             # nomes de pessoa que devem ir para o fim da fila
    "excluir_usuarios_regex": "",      # @ que nunca devem ser lidos (ex.: "^fanclub|fake")
    "publicacoes": {
        # Quem passa pela etapa de publicações (em ordem): duvidoso, conta_comercial, sinais_comerciais, bio_vazia
        "motivos": ["duvidoso", "conta_comercial", "sinais_comerciais", "bio_vazia"],
        "bio_vazia_ate_prioridade": COMERCIAL,  # bio vazia só se o @/nome tiver cara de segmento ou de empresa
        "quantidade": 12,                       # últimas publicações lidas (as fixadas vêm primeiro)
        "destaques": "duvidosos",               # títulos dos destaques: duvidosos | se_inconclusivo | sempre | nunca
    },
}


def carregar_config() -> dict:
    """Critérios padrão + instagram/triagem.json (ou PROSPECCAO_TRIAGEM=caminho), se existir."""
    cfg = json.loads(json.dumps(PADRAO))
    caminho = Path(os.environ.get("PROSPECCAO_TRIAGEM", config.ROOT / "triagem.json"))
    if caminho.exists():
        try:
            extra = json.loads(caminho.read_text(encoding="utf-8"))
        except ValueError as e:
            raise ValueError(f"triagem.json inválido: {e}") from e
        for k, v in extra.items():
            if k in ("ler_ate_prioridade", "publicacoes") and isinstance(v, dict):
                cfg[k].update(v)
            elif k in cfg:
                cfg[k] = v
    return cfg


def _tokens(texto: str) -> list[str]:
    return [t for t in normalizar_texto(texto).split() if t]


def parece_pessoa(usuario: str, nome: str, extras: set | None = None) -> bool:
    """Nome de pessoa física? ("Maria Silva", "joao.pereira_89", "Lucas"). Heurística para ordenar, não para descartar."""
    nomes = PRENOMES | (extras or set())
    toks = _tokens(nome)
    if toks:
        primeiro = next((t for t in toks if not t.isdigit()), "")
        return primeiro in nomes and len(toks) <= 4
    partes = [p for p in re.split(r"[._\d]+", usuario.lower()) if p]
    if partes and partes[0] in nomes:
        return True
    # @ colado: "anapaulasilva", "joaosantos" (prenome de 4+ letras no início)
    return any(usuario.lower().startswith(n) and len(n) >= 4 and len(usuario) - len(n) >= 3 for n in nomes)


def avaliar(p: Perfil, cfg: dict | None = None) -> tuple[int, str]:
    """Prioridade de leitura e o motivo, usando só o @ e o nome (dados da lista de seguidores)."""
    from prospeccao.classificar import indicios_segmento

    cfg = cfg or carregar_config()
    if cfg.get("excluir_usuarios_regex") and re.search(cfg["excluir_usuarios_regex"], p.usuario):
        return PRIVADO, "excluído pelo critério excluir_usuarios_regex"
    if p.privado and not cfg.get("ler_privados"):
        return PRIVADO, "perfil privado"
    ind = indicios_segmento(p.usuario, p.nome)
    if ind:
        return SEGMENTO, "indício de segmento no @/nome: " + ", ".join(ind[:3])
    texto = " ".join(_tokens(p.usuario.replace(".", " ").replace("_", " ")) + _tokens(p.nome))
    extras_com = [re.escape(normalizar_texto(w)) for w in cfg.get("palavras_comerciais_extras", []) if w]
    m = _COMERCIAL.search(texto) or (re.search(r"\b(?:" + "|".join(extras_com) + r")\b", texto) if extras_com else None)
    if m or "&" in (p.nome or "") or "|" in (p.nome or "") and not parece_pessoa(p.usuario, p.nome.split("|")[0]):
        return COMERCIAL, f"nome com cara de empresa ('{m.group(0)}')" if m else "nome com cara de empresa"
    pessoa = parece_pessoa(p.usuario, p.nome, {normalizar_texto(n) for n in cfg.get("prenomes_extras", [])})
    if pessoa:
        cargo = _CARGO.search(normalizar_texto((p.nome or "") + " " + p.usuario.replace(".", " ").replace("_", " ")))
        if cargo:
            return PROFISSIONAL, f"nome de pessoa com cargo/serviço ('{cargo.group(0)}')"
        return PESSOA, "parece nome de pessoa"
    return INDEFINIDO, "nem nome de pessoa nem de empresa: precisa ler o perfil"


def deve_ler(prioridade: int, modo: str, cfg: dict | None = None) -> bool:
    cfg = cfg or carregar_config()
    limite = cfg["ler_ate_prioridade"].get(modo, PADRAO["ler_ate_prioridade"].get(modo, INDEFINIDO))
    return prioridade != PRIVADO and prioridade <= limite
