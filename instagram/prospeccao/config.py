"""Caminhos, ritmo das requisições e limites, ajustáveis por variável de ambiente."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTADOS_DIR = Path(os.environ.get("PROSPECCAO_RESULTADOS", ROOT / "resultados"))

# A sessão do Instagram fica FORA do projeto, no perfil do usuário do Windows, criptografada com DPAPI.
DADOS_USUARIO_DIR = Path(os.environ.get("PROSPECCAO_DADOS", Path(os.environ.get("LOCALAPPDATA", Path.home())) / "prospeccao-instagram"))
SESSAO_ARQ = DADOS_USUARIO_DIR / "sessao.bin"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
# Identificador público do aplicativo web do Instagram (o mesmo que o site envia em toda requisição).
IG_APP_ID = "936619743392459"
HTTP_TIMEOUT = 20.0


def _f(nome: str, padrao: float) -> float:
    try:
        return float(os.environ.get(nome, padrao))
    except ValueError:
        return padrao


# Ritmo conservador, parecido com uma pessoa rolando a lista (segundos; recebe variação aleatória de até +50%).
INTERVALO_PAGINA = _f("PROSPECCAO_INTERVALO_PAGINA", 4.0)   # entre páginas da lista de seguidores
INTERVALO_PERFIL = _f("PROSPECCAO_INTERVALO_PERFIL", 5.0)   # entre leituras de perfil (bio/categoria)
PAUSA_A_CADA = int(_f("PROSPECCAO_PAUSA_A_CADA", 60))       # requisições até uma pausa longa
PAUSA_LONGA = _f("PROSPECCAO_PAUSA_LONGA", 60.0)
# Ao receber "limite de requisições" (HTTP 429 / "Please wait a few minutes"): espera e tenta de novo.
ESPERAS_LIMITE = [60, 180, 600]  # depois da última, a execução é pausada e pode ser retomada mais tarde
# Modo noite (execução prolongada): depois das esperas acima, aguarda mais e retoma sozinho, poucas vezes.
# Verificação de segurança/checkpoint/sessão inválida NUNCA é aguardada: a execução para e pede ação humana.
ESPERAS_NOITE_LIMITE = [900, 1800, 3600, 3600]   # "Please wait a few minutes"/429 persistente
ESPERAS_NOITE_REDE = [120, 300, 600, 900, 1800]  # internet caiu / Instagram fora do ar
TENTATIVAS_REDE = 3
TAMANHO_PAGINA = 25  # seguidores pedidos por página (o Instagram pode devolver menos)
