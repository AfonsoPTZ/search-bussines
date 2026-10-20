"""Caminhos e parâmetros da plataforma, ajustáveis por variável de ambiente.

As pastas de resultados continuam sendo as de cada automação (lidas na hora, para respeitar as variáveis
EMPRESAS_RESULTADOS e PROSPECCAO_RESULTADOS de cada uma). A plataforma só acrescenta o banco de consulta.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
DADOS_DIR = Path(os.environ.get("PLATAFORMA_DADOS", ROOT / "dados"))
CLAUDE_DIR = DADOS_DIR / "claude"   # execuções da revisão pelo Claude Code
PORTA = int(os.environ.get("PLATAFORMA_PORTA", 8770))
PYTHON = sys.executable              # mesmo ambiente: as automações rodam com `python -m empresas|prospeccao`

DIAS_DESATUALIZADA = int(os.environ.get("PLATAFORMA_DIAS_DESATUALIZADA", 90))  # empresa "desatualizada"
DIAS_REPESQUISA = int(os.environ.get("PLATAFORMA_DIAS_REPESQUISA", 30))        # não repete pesquisa mais nova que isso
SEM_BATIMENTO_EMPRESAS_S = 10 * 60   # lote "executando" sem atualização há mais que isso: o processo parou
INTERVALO_SINCRONIA_S = 4            # leitura do estado das execuções
INTERVALO_DADOS_EM_ANDAMENTO_S = 30  # releitura dos dados de execuções em andamento
MAX_LINHAS_LOTE = 1000


def db_arquivo() -> Path:
    return DADOS_DIR / "plataforma.sqlite"


def resultados_instagram() -> Path:
    from prospeccao import config as c
    return c.RESULTADOS_DIR


def resultados_empresas() -> Path:
    from empresas import config as c
    return c.RESULTADOS_DIR


def entradas_empresas() -> Path:
    from empresas import config as c
    return c.ENTRADAS_DIR
