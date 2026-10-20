"""Banco de consulta (SQLite) da plataforma.

Duas naturezas de dado convivem aqui:
  * DERIVADO das pastas de resultados (execucoes, perfis, perfil_execucao, pesquisas e os campos de exibição de
    empresas): é refeito pela sincronização e nunca é a fonte da verdade. As pastas continuam sendo.
  * PRÓPRIO da plataforma (empresas.id e a atribuição pesquisa → empresa, empresa_chaves, vinculos manuais ou
    rejeitados, duplicidades decididas, execucao_meta e historico): decisões suas, preservadas entre sincronizações.

Migrações: PRAGMA user_version. Cada versão nova acrescenta um passo em _MIGRACOES (nunca altera um passo antigo).
"""

import sqlite3
import threading
from contextlib import contextmanager

from plataforma import config

_MIGRACOES = [
    # 1: estrutura inicial
    """
    CREATE TABLE execucoes(
        id TEXT PRIMARY KEY, tipo TEXT NOT NULL, pasta TEXT NOT NULL, nome TEXT, referencia TEXT,
        estado TEXT, status_original TEXT, completa INTEGER DEFAULT 0, pode_retomar INTEGER DEFAULT 0,
        em_andamento INTEGER DEFAULT 0, criado TEXT, iniciado TEXT, atualizado TEXT, finalizado TEXT,
        total INTEGER, processados INTEGER, falhas INTEGER, pendentes INTEGER,
        ultima_etapa TEXT, mensagem TEXT, origem_execucao TEXT, resumo TEXT,
        assinatura_estado TEXT, assinatura_dados TEXT, dados_lidos_em REAL
    );
    CREATE TABLE execucao_meta(
        execucao_id TEXT PRIMARY KEY, arquivada INTEGER DEFAULT 0, nota TEXT
    );
    CREATE TABLE perfis(
        usuario TEXT PRIMARY KEY, nome TEXT, bio TEXT, categoria_ig TEXT, conta_comercial INTEGER, privado INTEGER,
        link_externo TEXT, dominio TEXT, seguidores INTEGER, cidade TEXT, telefone TEXT, email TEXT,
        situacao TEXT, tipo_perfil TEXT, estado_analise TEXT, segmentos TEXT, confianca TEXT, revisado INTEGER,
        classificacao TEXT, perfil TEXT, execucao_id TEXT, em TEXT, busca TEXT
    );
    CREATE TABLE perfil_execucao(
        execucao_id TEXT, usuario TEXT, situacao TEXT, segmentos TEXT, confianca TEXT, revisado INTEGER, em TEXT,
        PRIMARY KEY(execucao_id, usuario)
    );
    CREATE INDEX ix_pe_usuario ON perfil_execucao(usuario);
    CREATE TABLE pesquisas(
        id TEXT PRIMARY KEY, execucao_id TEXT NOT NULL, linha INTEGER, entrada TEXT, tipo_entrada TEXT,
        status TEXT, confianca TEXT, data TEXT, revisado_em TEXT, nome TEXT,
        cnpj TEXT, cnpj_confirmado INTEGER, handles TEXT, handles_fortes TEXT, dominio TEXT, dominio_confirmado INTEGER,
        cidade TEXT, uf TEXT, registro TEXT, empresa_id INTEGER, separada INTEGER DEFAULT 0
    );
    CREATE INDEX ix_pesq_empresa ON pesquisas(empresa_id);
    CREATE INDEX ix_pesq_exec ON pesquisas(execucao_id);
    CREATE TABLE empresas(
        id INTEGER PRIMARY KEY AUTOINCREMENT, criado TEXT, visivel INTEGER DEFAULT 1, pesquisa_atual TEXT,
        nome TEXT, razao_social TEXT, categoria TEXT, cnpj TEXT, cnpj_confirmado INTEGER, cidade TEXT, cidade_chave TEXT,
        uf TEXT, site TEXT, dominio TEXT, instagram TEXT, telefone TEXT, whatsapp TEXT, email TEXT,
        status TEXT, confianca TEXT, completude INTEGER, n_nao_confirmados INTEGER, nao_confirmados TEXT,
        nao_encontrados TEXT, divergencias INTEGER, precisa_revisao INTEGER, revisada INTEGER,
        segmentos_perfil TEXT, segmentos_inferidos TEXT, ultima_pesquisa TEXT, n_pesquisas INTEGER,
        execucoes TEXT, busca TEXT, atualizado TEXT
    );
    CREATE INDEX ix_emp_uf ON empresas(uf);
    CREATE TABLE empresa_chaves(chave TEXT PRIMARY KEY, empresa_id INTEGER NOT NULL);
    CREATE INDEX ix_chaves_emp ON empresa_chaves(empresa_id);
    CREATE TABLE vinculos(
        usuario TEXT, empresa_id INTEGER, estado TEXT, origem TEXT, evidencia TEXT, fonte TEXT,
        manual INTEGER DEFAULT 0, em TEXT, PRIMARY KEY(usuario, empresa_id)
    );
    CREATE INDEX ix_vinc_emp ON vinculos(empresa_id);
    CREATE TABLE duplicidades(
        a INTEGER, b INTEGER, motivo TEXT, estado TEXT DEFAULT 'pendente', em TEXT, PRIMARY KEY(a, b)
    );
    CREATE TABLE historico(
        id INTEGER PRIMARY KEY AUTOINCREMENT, em TEXT, tipo TEXT, descricao TEXT, dados TEXT
    );
    """,
    # 2: fila de pesquisa (perfis identificados no Instagram esperando os dados da empresa)
    """
    CREATE TABLE fila_pesquisa(
        usuario TEXT PRIMARY KEY,
        execucao_id TEXT,              -- análise do Instagram de onde o perfil veio
        nome TEXT, cidade TEXT, segmentos TEXT,
        estado TEXT NOT NULL DEFAULT 'pendente',   -- pendente | pesquisando | concluido | dispensado
        empresa_id INTEGER,            -- empresa encontrada (quando concluído)
        lote_id TEXT,                  -- pesquisa de empresas que atendeu este perfil
        motivo TEXT DEFAULT '',        -- por que foi dispensado, ou o que faltou
        tentativas INTEGER DEFAULT 0,
        criado TEXT, atualizado TEXT
    );
    CREATE INDEX ix_fila_estado ON fila_pesquisa(estado);
    """,
]

_local = threading.local()
_escrita = threading.RLock()


def _conectar() -> sqlite3.Connection:
    config.DADOS_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.db_arquivo(), timeout=30, isolation_level=None, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=OFF")
    con.execute("PRAGMA busy_timeout=30000")
    return con


def migrar(con: sqlite3.Connection) -> int:
    versao = con.execute("PRAGMA user_version").fetchone()[0]
    for n, sql in enumerate(_MIGRACOES[versao:], versao + 1):
        with _escrita:
            con.executescript("BEGIN;" + sql + f"; PRAGMA user_version={n}; COMMIT;")
    return len(_MIGRACOES)


def conexao() -> sqlite3.Connection:
    """Uma conexão por thread (o servidor atende em várias threads)."""
    con = getattr(_local, "con", None)
    caminho = str(config.db_arquivo())
    if con is None or getattr(_local, "caminho", None) != caminho:
        con = _conectar()
        migrar(con)
        _local.con, _local.caminho = con, caminho
    return con


def fechar():
    con = getattr(_local, "con", None)
    if con is not None:
        con.close()
        _local.con = None


@contextmanager
def transacao():
    """Escrita atômica e serializada entre threads."""
    con = conexao()
    with _escrita:
        con.execute("BEGIN IMMEDIATE")
        try:
            yield con
        except BaseException:
            con.execute("ROLLBACK")
            raise
        else:
            con.execute("COMMIT")
