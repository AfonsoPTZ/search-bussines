"""Coleta no Instagram com a sessão do próprio usuário, usando os mesmos endpoints que o site instagram.com usa.

Por que assim (pesquisa de 19/10/2026, detalhes no README):
- Nenhuma API oficial da Meta lista seguidores de outra conta.
- Sem login, o Instagram não entrega a lista de seguidores nem a bio de perfis comuns.
- Instaloader 4.15.4: get_followers() quebrado desde set/2026 (consulta GraphQL antiga devolve lista vazia).
- O site usa GET /api/v1/friendships/<id>/followers/ (paginado por max_id), que funciona logado.
- Perfis: a página logada embute o id (profile_id) e os tokens do site; a bio vem da consulta GraphQL
  PolarisProfilePageContentQuery, a mesma que o site faz. web_profile_info responde 429 (fica como alternativa).

Salvaguardas: ritmo lento com variação, pausa longa periódica, espera quando o Instagram pede ("Please wait a few
minutes"/429) e PARADA imediata em checkpoint, desafio, "feedback_required" ou sessão inválida. Nada é contornado.
"""

import json
import os
import random
import re
import time
from dataclasses import dataclass, field

import httpx

from prospeccao import config
from prospeccao.perfis import Perfil, completar, de_lista

# Consulta GraphQL do perfil (PolarisProfilePageContentQuery), a mesma que o Instaloader 4.15.4 usa logado.
DOC_ID_PERFIL = os.environ.get("PROSPECCAO_DOC_ID_PERFIL", "27937681195819736")
# Publicações (PolarisProfilePostsTabContentQuery_connection) e destaques: mesmas consultas do site / do Instaloader 4.15.4.
DOC_ID_POSTS = os.environ.get("PROSPECCAO_DOC_ID_POSTS", "28975909992013618")
QUERY_HASH_DESTAQUES = os.environ.get("PROSPECCAO_QUERY_HASH_DESTAQUES", "7c16654f22c819fb63d1183034a5162f")


class ErroColeta(Exception):
    tipo = "erro"


class ErroSemSessao(ErroColeta):
    tipo = "sem_sessao"


class ErroAutenticacao(ErroColeta):
    tipo = "erro_autenticacao"


class ErroDesafio(ErroColeta):
    """Checkpoint, desafio ou bloqueio de ação: exige ação humana no app/site. Nunca é contornado."""
    tipo = "erro_desafio"


class ErroLimite(ErroColeta):
    tipo = "pausado_limite_instagram"


class ErroPerfil(ErroColeta):
    tipo = "erro_perfil"


class ErroIndisponivel(ErroColeta):
    tipo = "erro_rede"


@dataclass
class Pagina:
    perfis: list[Perfil]
    proximo: str | None
    limitada: bool = False  # should_limit_list_of_followers: o Instagram só mostra parte da lista
    recebidos: int = 0


@dataclass
class Ritmo:
    """Intervalo mínimo entre requisições, com variação aleatória e pausa longa a cada N requisições."""
    dormir: callable = time.sleep
    agora: callable = time.monotonic
    pausa_a_cada: int = config.PAUSA_A_CADA
    pausa_longa: float = config.PAUSA_LONGA
    ultimo: float = 0.0
    feitas: int = 0
    avisar: callable = None

    def esperar(self, intervalo: float):
        if self.feitas and self.pausa_a_cada and self.feitas % self.pausa_a_cada == 0:
            if self.avisar:
                self.avisar(f"pausa regular de {self.pausa_longa:.0f}s após {self.feitas} requisições")
            self.dormir(self.pausa_longa)
        alvo = intervalo * (1 + random.random() * 0.5)
        falta = self.ultimo + alvo - self.agora()
        if self.ultimo and falta > 0:
            self.dormir(falta)
        self.ultimo = self.agora()
        self.feitas += 1


@dataclass
class ClienteInstagram:
    cookies: dict
    transporte: httpx.BaseTransport | None = None
    ritmo: Ritmo = field(default_factory=Ritmo)
    esperas_limite: list = field(default_factory=lambda: list(config.ESPERAS_LIMITE))
    avisar: callable = print  # mensagens de andamento (sem dados sensíveis)

    def __post_init__(self):
        if not self.cookies or not self.cookies.get("sessionid"):
            raise ErroSemSessao("Sessão do Instagram não configurada. Rode: prospeccao sessao definir (ou sessao firefox)")
        self.ritmo.avisar = self.ritmo.avisar or self.avisar
        self._c = httpx.Client(headers={"User-Agent": config.USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"},
                               cookies=dict(self.cookies), timeout=config.HTTP_TIMEOUT, follow_redirects=False,
                               transport=self.transporte)
        self._claim = "0"
        self._tokens: dict | None = None
        self._estrategias = ["graphql", "web_profile_info"]

    def fechar(self):
        self._c.close()

    def _cookie(self, nome: str) -> str:
        """O Instagram renova cookies (ex.: csrftoken) em outro domínio; vale o mais recente, sem erro de conflito."""
        valor = ""
        for ck in self._c.cookies.jar:
            if ck.name == nome and ck.value:
                valor = ck.value
        return valor

    # ---------- núcleo HTTP

    def _pedir(self, metodo: str, url: str, intervalo: float, html=False, **kw):
        """Requisição com ritmo, novas tentativas em falha de rede e espera em limite. Retorna JSON (ou texto)."""
        tentativas_rede = 0
        esperas = list(self.esperas_limite)
        extra = kw.pop("headers", None) or {}
        while True:
            self.ritmo.esperar(intervalo)
            if html:  # navegação de página, como o navegador faz
                hdrs = {"Accept": "text/html,application/xhtml+xml", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none", "Upgrade-Insecure-Requests": "1"}
            else:
                hdrs = {"Accept": "*/*", "X-IG-App-ID": config.IG_APP_ID, "X-Requested-With": "XMLHttpRequest",
                        "X-ASBD-ID": "129477", "X-IG-WWW-Claim": self._claim, "Origin": "https://www.instagram.com",
                        "Referer": "https://www.instagram.com/", "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors",
                        "Sec-Fetch-Dest": "empty"}
                csrf = self._cookie("csrftoken")
                if csrf:
                    hdrs["X-CSRFToken"] = csrf
            hdrs.update(extra)
            try:
                r = self._c.request(metodo, url, headers=hdrs, **kw)
            except (httpx.TransportError, httpx.TimeoutException) as e:
                tentativas_rede += 1
                if tentativas_rede >= config.TENTATIVAS_REDE:
                    raise ErroIndisponivel(f"Falha de rede ao acessar o Instagram: {type(e).__name__}") from e
                self.avisar(f"falha de rede ({type(e).__name__}); nova tentativa {tentativas_rede + 1}")
                self.ritmo.dormir(5 * tentativas_rede)
                continue
            claim = r.headers.get("x-ig-set-www-claim")
            if claim:
                self._claim = claim
            try:
                self._verificar(r, html)
            except ErroLimite:
                if not esperas:
                    raise
                espera = esperas.pop(0)
                self.avisar(f"o Instagram pediu para aguardar; esperando {espera}s antes de tentar de novo")
                self.ritmo.dormir(espera)
                continue
            except ErroIndisponivel:
                tentativas_rede += 1
                if tentativas_rede >= config.TENTATIVAS_REDE:
                    raise
                self.ritmo.dormir(10 * tentativas_rede)
                continue
            if html:
                return r.text
            texto = r.text.removeprefix("for (;;);")
            try:
                return json.loads(texto)
            except ValueError as e:
                raise ErroIndisponivel(f"Resposta inesperada do Instagram (HTTP {r.status_code}, não é JSON)") from e

    @staticmethod
    def _verificar(r: httpx.Response, html: bool):
        corpo = r.text[:3000] if r.content else ""
        try:
            j = json.loads(corpo.removeprefix("for (;;);")) if not html and corpo.lstrip().startswith(("{", "for")) else {}
        except ValueError:
            j = {}
        msg = str(j.get("message") or "")
        texto = (msg + " " + str(j.get("error_type") or "")).lower()
        local = r.headers.get("location", "")
        if r.status_code == 429 or "please wait a few minutes" in texto or "rate limit" in texto:
            raise ErroLimite("O Instagram limitou as requisições (HTTP %d)" % r.status_code)
        if any(k in texto for k in ("checkpoint", "challenge", "feedback_required", "consent_required")) or \
                j.get("checkpoint_url") or j.get("challenge") or "/challenge/" in local or "/checkpoint/" in local:
            raise ErroDesafio("O Instagram pediu verificação/desafio para esta conta. Abra o Instagram no navegador ou "
                              "no app, resolva manualmente e só depois retome. A ferramenta não contorna isso.")
        if "login_required" in texto or "/accounts/login" in local or r.status_code == 401:
            raise ErroAutenticacao("Sessão do Instagram inválida ou expirada. Faça login de novo e reconfigure a sessão.")
        if r.status_code == 404:
            raise ErroPerfil("Não encontrado (HTTP 404)")
        if r.status_code in (301, 302, 303, 307, 308):
            raise ErroAutenticacao(f"Redirecionamento inesperado ({r.status_code}); a sessão pode ter expirado.")
        if r.status_code >= 500:
            raise ErroIndisponivel(f"Instagram indisponível (HTTP {r.status_code})")
        if r.status_code >= 400:
            raise ErroColeta(f"HTTP {r.status_code}: {msg[:200] or corpo[:200]}")
        if j.get("status") == "fail":
            raise ErroColeta(f"Instagram recusou: {msg[:200]}")

    # ---------- página do perfil e tokens do site

    @staticmethod
    def _extrair(padrao: str, texto: str) -> str:
        m = re.search(padrao, texto)
        return m.group(1) if m else ""

    def _pagina(self, usuario: str) -> str:
        return self._pedir("GET", f"https://www.instagram.com/{usuario}/", config.INTERVALO_PERFIL, html=True)

    def _guardar_tokens(self, pagina: str):
        """Tokens que o próprio site usa nas consultas GraphQL (não são credenciais novas; vêm da página logada)."""
        if "not-logged-in" in pagina[:5000]:
            raise ErroAutenticacao("O Instagram não reconheceu a sessão (página como visitante). Reconfigure a sessão.")
        dtsg = self._extrair(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"', pagina)
        lsd = self._extrair(r'"LSD",\[\],\{"token":"([^"]+)"', pagina)
        if dtsg and lsd:
            self._tokens = {"fb_dtsg": dtsg, "lsd": lsd,
                            "av": self._extrair(r'"PolarisViewer",\[\],\{"data":\{.*?"fbid":"(\d+)"', pagina),
                            "rev": self._extrair(r'"server_revision":(\d+)', pagina) or self._extrair(r'"__spin_r":(\d+)', pagina)}

    def _garantir_tokens(self):
        if not self._tokens:
            self._guardar_tokens(self._pedir("GET", "https://www.instagram.com/", config.INTERVALO_PERFIL, html=True))
        if not self._tokens:
            raise ErroColeta("Não foi possível obter os tokens da página do Instagram para consultar perfis.")

    # ---------- operações

    def conta_logada(self) -> dict:
        """Confere a sessão. Devolve {'usuario': ..., 'pk': ...} da conta logada (sem expor cookies)."""
        ds = self.cookies.get("ds_user_id") or self._cookie("ds_user_id")
        if not ds:
            raise ErroAutenticacao("Cookie ds_user_id ausente; reconfigure a sessão.")
        u = self._usuario_por_pk(ds)
        return {"usuario": u.get("username", "?"), "pk": ds}

    def _graphql(self, doc_id: str, nome: str, variaveis: dict, referer_usuario: str = "") -> dict:
        """Consulta GraphQL no mesmo formato que o site envia (tokens fb_dtsg/lsd da página logada)."""
        self._garantir_tokens()
        t = self._tokens
        dados = {"av": t["av"], "__user": "0", "__a": "1", "__req": "1", "dpr": "1", "__ccg": "GOOD", "__rev": t["rev"],
                 "__comet_req": "7", "fb_dtsg": t["fb_dtsg"], "jazoest": "2" + str(sum(ord(ch) for ch in t["fb_dtsg"])),
                 "lsd": t["lsd"], "__spin_r": t["rev"], "__spin_b": "trunk", "fb_api_caller_class": "RelayModern",
                 "fb_api_req_friendly_name": nome, "variables": json.dumps(variaveis, separators=(",", ":")),
                 "server_timestamps": "true", "doc_id": doc_id}
        return self._pedir("POST", "https://www.instagram.com/graphql/query", config.INTERVALO_PERFIL, data=dados,
                           headers={"X-FB-LSD": t["lsd"], "X-FB-Friendly-Name": nome,
                                    "Content-Type": "application/x-www-form-urlencoded",
                                    "Referer": f"https://www.instagram.com/{referer_usuario}/" if referer_usuario else "https://www.instagram.com/"})

    def _usuario_por_pk(self, pk: str, referer_usuario: str = "") -> dict:
        variaveis = {"id": str(pk), "render_surface": "PROFILE",
                     "__relay_internal__pv__PolarisCannesGuardianExperienceEnabledrelayprovider": True,
                     "__relay_internal__pv__PolarisCASB976ProfileEnabledrelayprovider": False,
                     "__relay_internal__pv__PolarisRepostsConsumptionEnabledrelayprovider": False,
                     "__relay_internal__pv__PolarisWebSchoolsEnabledrelayprovider": False,
                     "enable_integrity_filters": True}
        j = self._graphql(DOC_ID_PERFIL, "PolarisProfilePageContentQuery", variaveis, referer_usuario)
        u = (j.get("data") or {}).get("user")
        if not u:
            erros = j.get("errors") or []
            if erros:  # consulta recusada (ex.: doc_id desatualizado): erro de formato, não de perfil
                if any((e or {}).get("requires_reauth") for e in erros):
                    self._tokens = None
                raise ErroColeta(f"Consulta GraphQL de perfil recusada: {str(erros[0].get('message', erros))[:200]}")
            raise ErroPerfil("Perfil sem dados (removido ou indisponível)")
        return u

    def _usuario_por_nome(self, usuario: str) -> dict:
        j = self._pedir("GET", "https://www.instagram.com/api/v1/users/web_profile_info/", config.INTERVALO_PERFIL,
                        params={"username": usuario})
        u = (j.get("data") or {}).get("user")
        if not u:
            raise ErroPerfil(f"Perfil @{usuario} não encontrado")
        return u

    def pk_por_pagina(self, usuario: str) -> str:
        """Id interno do perfil a partir da página logada (o site o embute como profile_id / profilePage_<id>)."""
        pagina = self._pagina(usuario)
        if '"pageID":"httpErrorPage"' in pagina:
            raise ErroPerfil(f"@{usuario} não existe ou não está disponível (o Instagram mostra página de erro).")
        self._guardar_tokens(pagina)
        pk = self._extrair(r'"profile_id":"(\d+)"', pagina) or self._extrair(r'"page_id":"profilePage_(\d+)"', pagina)
        if not pk:
            raise ErroColeta(f"Não foi possível obter o id de @{usuario} na página do perfil.")
        return pk

    def perfil_origem(self, usuario: str) -> dict:
        """Resolve o @ de origem: id interno, nome, total de seguidores e se é privado."""
        pk = self.pk_por_pagina(usuario)
        u = self._usuario_por_pk(pk, usuario)
        if (u.get("username") or usuario).lower() != usuario:
            raise ErroPerfil(f"O id encontrado não corresponde a @{usuario}.")
        p = completar(Perfil(usuario=usuario, pk=pk), u)
        amizade = u.get("friendship_status") or {}
        return {"usuario": usuario, "pk": p.pk, "nome": p.nome, "seguidores": p.seguidores, "privado": bool(p.privado),
                "sigo": bool(u.get("followed_by_viewer") or amizade.get("following")), "verificado": bool(p.verificado)}

    def pagina_seguidores(self, pk: str, usuario: str, cursor: str | None) -> Pagina:
        params = {"count": config.TAMANHO_PAGINA, "search_surface": "follow_list_page"}
        if cursor:
            params["max_id"] = cursor
        j = self._pedir("GET", f"https://www.instagram.com/api/v1/friendships/{pk}/followers/", config.INTERVALO_PAGINA,
                        params=params, headers={"Referer": f"https://www.instagram.com/{usuario}/followers/"})
        itens = j.get("users")
        if not isinstance(itens, list):
            raise ErroColeta("Resposta da lista de seguidores sem o campo 'users'.")
        perfis = [p for p in (de_lista(i) for i in itens if isinstance(i, dict)) if p]
        proximo = j.get("next_max_id")
        if j.get("has_more") is False:
            proximo = None
        return Pagina(perfis=perfis, proximo=str(proximo) if proximo else None,
                      limitada=bool(j.get("should_limit_list_of_followers")), recebidos=len(itens))

    def publicacoes(self, usuario: str, quantidade: int = 12) -> list[dict]:
        """Últimas publicações do perfil (inclui as fixadas, que o Instagram devolve primeiro).

        Cada item: {"texto", "hashtags", "fixado", "local", "data", "codigo"}. Erros parciais do GraphQL (ex.: foto do
        local) são ignorados quando os posts vêm; sem posts e com erro, lança ErroColeta."""
        variaveis = {"data": {"count": quantidade, "include_reel_media_seen_timestamp": True, "include_relationship_info": True,
                              "latest_besties_reel_media": True, "latest_reel_media": True},
                     "username": usuario,
                     "__relay_internal__pv__PolarisMultiCaptionCarouselEnabledrelayprovider": True,
                     "__relay_internal__pv__PolarisShortDramaEnabledrelayprovider": False,
                     "__relay_internal__pv__PolarisReelsRecoDebugOverlayEnabledrelayprovider": False}
        j = self._graphql(DOC_ID_POSTS, "PolarisProfilePostsQuery", variaveis, usuario)
        con = (j.get("data") or {}).get("xdt_api__v1__feed__user_timeline_graphql_connection")
        if con is None:
            erros = j.get("errors") or []
            raise ErroColeta("Consulta de publicações sem dados" + (f": {str(erros[0].get('message', ''))[:150]}" if erros else ""))
        posts = []
        for e in (con.get("edges") or [])[:quantidade]:
            n = (e or {}).get("node") or {}
            texto = ((n.get("caption") or {}).get("text") or "").strip()
            posts.append({
                "texto": texto[:600],
                "hashtags": sorted(set(re.findall(r"#(\w+)", texto)))[:30],
                "fixado": bool(n.get("timeline_pinned_user_ids")),
                "local": ((n.get("location") or {}).get("name") or "").strip(),
                "data": n.get("taken_at"),
                "codigo": n.get("code") or "",
            })
        return posts

    def destaques(self, pk: str) -> list[str]:
        """Títulos dos destaques dos Stories (consulta legada que ainda responde, testada em 19/10/2026)."""
        v = {"user_id": str(pk), "include_chaining": False, "include_reel": False, "include_suggested_users": False,
             "include_logged_out_extras": False, "include_highlight_reels": True, "include_live_status": False}
        j = self._pedir("GET", "https://www.instagram.com/graphql/query/", config.INTERVALO_PERFIL,
                        params={"query_hash": QUERY_HASH_DESTAQUES, "variables": json.dumps(v)})
        user = (j.get("data") or {}).get("user")
        if user is None:
            raise ErroColeta("Consulta de destaques sem dados")
        return [t for t in (((e or {}).get("node") or {}).get("title", "").strip()
                            for e in (user.get("edge_highlight_reels") or {}).get("edges") or []) if t][:30]

    def detalhes(self, p: Perfil) -> Perfil:
        """Lê bio, categoria, tipo de conta e link do perfil: GraphQL por id (como o site) e, se falhar, web_profile_info."""
        if not p.pk and "graphql" in self._estrategias:
            try:
                p.pk = self.pk_por_pagina(p.usuario)  # lista importada de arquivo: só temos o @
            except (ErroLimite, ErroDesafio, ErroAutenticacao):
                raise
            except ErroPerfil:
                raise
            except ErroColeta:
                pass
        ultimo_erro = None
        for est in list(self._estrategias):
            try:
                if est == "graphql":
                    if not p.pk:
                        continue
                    u = self._usuario_por_pk(p.pk, p.usuario)
                else:
                    u = self._usuario_por_nome(p.usuario)
                return completar(p, u)
            except (ErroLimite, ErroDesafio, ErroAutenticacao, ErroSemSessao):
                raise
            except ErroColeta as e:
                ultimo_erro = e
                # Erro de formato (ex.: doc_id trocado pelo Instagram) desativa a estratégia nesta execução.
                if not isinstance(e, (ErroPerfil, ErroIndisponivel)) and len(self._estrategias) > 1:
                    self._estrategias.remove(est)
                    self.avisar(f"leitura de perfil via {est} falhou ({e}); usando alternativa")
        raise ultimo_erro or ErroPerfil("Sem estratégia disponível para ler o perfil")


def ler_lista_arquivo(caminho) -> list[str]:
    """Lista de seguidores obtida por outro meio: .txt/.csv com um @ por linha ou o followers_*.json do
    "Baixar suas informações" da Meta (só vale para a sua própria conta). Devolve @s normalizados, sem repetição."""
    from pathlib import Path

    from prospeccao.arrobas import ArrobaInvalida, normalizar

    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8-sig", errors="replace")
    brutos: list[str] = []
    if caminho.suffix.lower() == ".json":
        def varrer(o):
            if isinstance(o, dict):
                for d in o.get("string_list_data") or []:
                    brutos.append(d.get("value") or d.get("href") or "")
                if o.get("title") and not o.get("string_list_data"):
                    brutos.append(o["title"])
                for v in o.values():
                    if isinstance(v, (list, dict)):
                        varrer(v)
            elif isinstance(o, list):
                for v in o:
                    varrer(v)
        varrer(json.loads(texto))
    else:
        for linha in texto.splitlines():
            primeira = re.split(r"[;,\t]", linha.strip())[0] if linha.strip() else ""
            if primeira and primeira.lower() not in ("usuario", "username", "instagram", "@"):
                brutos.append(primeira)
    vistos, saida = set(), []
    for b in brutos:
        try:
            u = normalizar(b)
        except ArrobaInvalida:
            continue
        if u not in vistos:
            vistos.add(u)
            saida.append(u)
    return saida
