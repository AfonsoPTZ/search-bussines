# pesquisa-empresas

Ferramenta local de pesquisa/enriquecimento de empresas brasileiras. Uso e arquitetura: README.md. Fluxo pelo chat: skill do projeto `pesquisa-empresas` (`../.claude/skills/pesquisa-empresas/SKILL.md`).

- Integrada à plataforma em `../plataforma` (lê `resultados/`; ver `../CLAUDE.md`). Não mude o formato de `registros.jsonl`/`progresso.json` sem ajustar `plataforma/sincronizar.py`. Normalmente os lotes nascem da **fila de pesquisa** da plataforma, a partir dos perfis identificados no Instagram.
- **Classificação:** o campo `categoria` é o **segmento A–M** (rótulo `"F · Crematórios e funerárias humanas"`), não uma categoria comercial. `empresas/categorias.py` só traduz CNAE/schema.org/nome para os segmentos definidos em `../instagram/prospeccao/categorias.py` — este pacote **depende** de `prospeccao-instagram`. Empresa fora dos 13 segmentos fica sem segmento, e isso é o esperado.
- Python 3.14 no `.venv` **da raiz** (pacote editável; executável `../.venv/Scripts/empresas.exe`).
- Testes: `..\.venv\Scripts\python -m pytest -q` (31); componentes externos: `empresas verificar`.
- O `painel` próprio (127.0.0.1:8765) foi removido em 20/10/2026: a interface é a plataforma, em 127.0.0.1:8770.
- SearXNG opcional via `docker compose up -d` (127.0.0.1:8888).
- Regra do projeto (desde 19/10/2026): trazer o máximo de dados, cada valor com fonte e flag `confirmado`. O que não tem prova entra marcado "(não confirmado)"; CNPJ sem confirmação vira status `provavel` (melhor candidato plausível, ativo antes de baixado). Só sai das colunas principais o que tem evidência contrária (vai para `alternativas`). Dado não confirmado nunca serve de evidência para confirmar outro. Não contornar CAPTCHA/login/anti-robô; não usar serviços pagos.
- Ao mexer na lógica de identificação (`empresas/pesquisa.py`), rode de novo uma lista de teste e compare (ver TESTES.md). Os lotes de referência antigos foram arquivados em `../_backup/` na limpeza de 20/10/2026.
