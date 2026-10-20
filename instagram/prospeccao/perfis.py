"""Normalização dos perfis: transforma as respostas do Instagram num formato único e tolerante a campos ausentes."""

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse

from prospeccao.arrobas import link


@dataclass
class Perfil:
    usuario: str
    pk: str = ""
    nome: str = ""
    bio: str = ""
    categoria_ig: str = ""            # categoria profissional exibida no perfil (quando a conta é comercial)
    conta_comercial: bool | None = None
    privado: bool | None = None
    verificado: bool | None = None
    link_externo: str = ""
    seguidores: int | None = None
    detalhes: str = "lista"           # lista (só @ e nome) | perfil (bio e categoria lidas) | indisponivel
    erro_detalhes: str = ""
    extras: dict = field(default_factory=dict)
    posts: list = field(default_factory=list)       # [{"texto","hashtags","fixado","local","data","codigo"}]
    destaques: list = field(default_factory=list)   # títulos dos destaques dos Stories
    etapas: list = field(default_factory=list)      # etapas executadas: lista, perfil, publicacoes, destaques
    erro_publicacoes: str = ""
    triagem: dict = field(default_factory=dict)     # {"prioridade": int, "motivo": str}

    @property
    def link(self) -> str:
        return link(self.usuario)

    def para_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def de_dict(cls, d: dict) -> "Perfil":
        campos = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in campos})


def _txt(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def _bool(v) -> bool | None:
    return v if isinstance(v, bool) else None


def de_lista(item: dict) -> Perfil | None:
    """Item da lista de seguidores (friendships/followers). Retorna None se não tiver @."""
    usuario = _txt(item.get("username")).lower()
    if not usuario:
        return None
    return Perfil(
        usuario=usuario,
        pk=str(item.get("pk") or item.get("pk_id") or item.get("id") or ""),
        nome=_txt(item.get("full_name")),
        privado=_bool(item.get("is_private")),
        verificado=_bool(item.get("is_verified")),
        etapas=["lista"],
    )


def completar(p: Perfil, u: dict) -> Perfil:
    """Junta os dados do perfil completo (GraphQL, web_profile_info ou users/info) ao perfil da lista."""
    p.nome = _txt(u.get("full_name")) or p.nome
    p.bio = _txt(u.get("biography"))
    p.categoria_ig = (_txt(u.get("category_name")) or _txt(u.get("category")) or _txt(u.get("business_category_name"))
                      or _txt(u.get("overall_category_name")))
    comercial = _bool(u.get("is_business_account"))
    if comercial is None:
        comercial = _bool(u.get("is_business"))
    if comercial is None and isinstance(u.get("account_type"), int):
        comercial = u["account_type"] == 2  # 1 pessoal, 2 comercial, 3 criador
    profissional = _bool(u.get("is_professional_account"))
    p.conta_comercial = comercial if comercial is not None else profissional
    p.privado = _bool(u.get("is_private")) if _bool(u.get("is_private")) is not None else p.privado
    p.verificado = _bool(u.get("is_verified")) if _bool(u.get("is_verified")) is not None else p.verificado
    p.link_externo = _txt(u.get("external_url"))
    if not p.link_externo:
        for b in u.get("bio_links") or []:
            if isinstance(b, dict) and _txt(b.get("url")):
                p.link_externo = _txt(b.get("url"))
                break
    seg = u.get("follower_count")
    if seg is None:
        seg = (u.get("edge_followed_by") or {}).get("count")
    p.seguidores = seg if isinstance(seg, int) else p.seguidores
    p.pk = str(u.get("pk") or u.get("id") or p.pk or "")
    extras = {}
    for k in ("public_phone_number", "contact_phone_number", "business_phone_number", "public_email", "business_email",
              "city_name", "address_street", "business_contact_method"):
        if _txt(u.get(k)):
            extras[k] = _txt(u.get(k))
    p.extras = extras
    p.detalhes = "perfil"
    p.erro_detalhes = ""
    if "perfil" not in p.etapas:
        p.etapas.append("perfil")
    return p


# ---------- texto


def normalizar_texto(t: str | None) -> str:
    """Minúsculas, sem acentos, letras "estilizadas" (𝐅𝐮𝐧𝐞𝐫á𝐫𝐢𝐚) convertidas, pontuação vira espaço."""
    if not t:
        return ""
    t = unicodedata.normalize("NFKC", t)
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).lower()
    t = t.replace("&", " e ")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def compactar(t: str | None) -> str:
    return normalizar_texto(t).replace(" ", "")


def dominio(url: str) -> str:
    if not url:
        return ""
    host = urlparse(url if "://" in url else "https://" + url).hostname or ""
    host = host.removeprefix("www.")
    if host in {"linktr.ee", "wa.me", "api.whatsapp.com", "bit.ly", "linkme.bio", "beacons.ai", "instagram.com",
                "facebook.com", "linkbio.co", "taplink.cc", "lnk.bio", "abre.ai", "whatsapp.com", "youtube.com"}:
        return ""
    return host
