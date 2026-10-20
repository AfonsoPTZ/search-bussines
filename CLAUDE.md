# Prospecção (RIP Memorial): plataforma unificada

Três pacotes Python 3.14 num só ambiente (`.venv` na raiz, editáveis, instalados por `instalar.cmd`):

- `instagram/`: pacote `prospeccao`. Análise de seguidores de um @ nos 13 segmentos A–M. Ver `instagram/CLAUDE.md`.
- `pesquisa-empresas/`: pacote `empresas`. Pesquisa de empresas BR com fonte e confirmação por valor. Ver
  `pesquisa-empresas/CLAUDE.md`.
- `plataforma/`: interface única (`python -m plataforma painel`, 127.0.0.1:8770), **fila de pesquisa** e banco de
  consulta SQLite que indexa as pastas de resultados das duas. Uso e arquitetura em `plataforma/README.md`; testes em
  `plataforma/TESTES.md`. Visão geral do projeto para o usuário: `README.md` na raiz.

Ordem de instalação (há dependência real): `instagram` → `pesquisa-empresas` → `plataforma`.

## O fluxo

```
Instagram (quem interessa: @, nome, segmento)  ->  FILA  ->  Empresas (CNPJ, contato, endereço)
```

A **fila** (`plataforma/fila.py`, tabela `fila_pesquisa`) é a ligação entre as duas metades. Todo perfil
`identificado` de execução não arquivada e sem empresa confirmada entra nela; sai quando ganha vínculo confirmado.
É derivada e se mantém sozinha a cada sincronização — **exceto** o estado `dispensado`, que é decisão do usuário e
nunca é desfeito automaticamente.

Esvaziar a fila: aba **Fila de pesquisa** na interface, `plataforma fila pesquisar`, ou o comando
`/executar-tarefa` do Claude Code (`.claude/skills/executar-tarefa/SKILL.md`), que também revisa os incertos.

## Segmentos A–M: uma definição só

As 13 categorias e as regras de classificação são definidas **uma única vez**, em
`instagram/prospeccao/categorias.py`. `prospeccao.classificar.segmentos_de_texto` é a função compartilhada que
infere segmento a partir de texto solto — usada pela plataforma e pela pesquisa de empresas; não duplique essa
montagem.

`pesquisa-empresas/empresas/categorias.py` só **traduz** para A–M o CNAE da Receita, o tipo schema.org do site e,
por último, o nome. O campo `categoria` do registro guarda o rótulo (`"F · Crematórios e funerárias humanas"`).
Empresa fora dos 13 segmentos fica **sem segmento** — é o esperado. Não existem mais categorias comerciais
genéricas (padaria, restaurante, mercearia) em lugar nenhum: foram removidas em 20/10/2026.

## Regras

- As pastas `*/resultados/` são a fonte da verdade (JSONL com checkpoint) e contêm dados reais de terceiros: não
  publicar, não apagar, não gravar nelas em testes. Testes usam tmp/scratchpad (veja `plataforma/tests/conftest.py`)
  ou as variáveis `PROSPECCAO_RESULTADOS`, `EMPRESAS_RESULTADOS`, `EMPRESAS_ENTRADAS` e `PLATAFORMA_DADOS`.
- `plataforma/dados/plataforma.sqlite` guarda decisões do usuário (uniões, separações, vínculos manuais,
  arquivamentos, dispensas da fila). Nunca apagar. O restante é derivado (`plataforma sincronizar --completa`).
- Nunca unir empresas só por nome. Nunca apresentar dado não confirmado ou inferido como confirmado.
- Nada de dados reais vai para o git (veja `.gitignore`).
- Testes: `..\.venv\Scripts\python -m pytest -q` em cada pasta (instagram 163, pesquisa-empresas 31, plataforma 69).

## Histórico

- `_backup/codigo_antes_plataforma_2026-10-20.tar.gz`: código anterior à plataforma.
- `_backup/dados_antes_unificacao_2026-10-20_*.tar.gz` e `_backup/dados_antigos_2026-10-20/`: as análises, pesquisas
  e o banco anteriores à unificação de 20/10/2026 (apagados da árvore a pedido do usuário, para começar limpo).
- Removidos em 20/10/2026 por estarem obsoletos e duplicados entre si, substituídos pela plataforma:
  `prospeccao/painel.py` (8766) e `empresas/painel.py` (8765), com os subcomandos `painel` das duas CLIs.

### Duplicação ainda existente (não resolvida)

Entre `prospeccao` e `empresas` ainda há infraestrutura repetida quase palavra por palavra. Se for mexer nela,
considere extrair para um módulo comum antes:

| Bloco | `prospeccao` | `empresas` |
|---|---|---|
| `pid_vivo` + trava de processo único | `execucao.py:74-121` | `lote.py:107-154` |
| Troca atômica de JSON (retry no Windows) | `execucao.py:61-71` | `lote.py:56-66` |
| `_slug` + nome de pasta datada | `execucao.py:57,184` | `lote.py:25,31` |
| `resolver_pasta` / "o mais recente" | `execucao.py:732-753` | `lote.py:77-98` |
| `USER_AGENT` e molde do `config.py` | `config.py:13-16` | `config.py:17-20` |

Atenção: `prospeccao.perfis.normalizar_texto` e `empresas.util.normalizar` **não** são equivalentes (NFKC e `&`), e
os dois `dominio()` têm contratos diferentes. Não unifique sem rever os testes.
