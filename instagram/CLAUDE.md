# instagram (prospeccao)

Prospecção de parceiros do RIP Memorial entre os seguidores de um perfil do Instagram. Uso e arquitetura: README.md. Testes e provas reais: TESTES.md. Fluxo pelo chat: skill do projeto `prospeccao-instagram` (`../.claude/skills/prospeccao-instagram/SKILL.md`).

- **Este pacote é o dono dos 13 segmentos A–M.** `categorias.py` os define e `classificar.segmentos_de_texto()` é a função compartilhada que a plataforma e a pesquisa de empresas usam para inferir segmento a partir de texto. Mudou aqui, mudou nos três.
- A coleta é independente de `../pesquisa-empresas` (CNPJ/contatos): não reutilizar aquele fluxo aqui. A integração fica em `../plataforma` (lê `resultados/`); não mude o formato de `perfis.jsonl`/`estado.json` sem ajustar `plataforma/sincronizar.py`. Todo perfil identificado entra na **fila de pesquisa** da plataforma.
- Python 3.14 no `.venv` **da raiz** (pacote editável; executável `../.venv/Scripts/prospeccao.exe`). Única dependência: httpx.
- Testes: `..\.venv\Scripts\python -m pytest -q` (163; offline, dados fictícios `teste_*`, Instagram simulado com MockTransport).
- Módulos: `arrobas` · `perfis` · `categorias` (13 categorias + regras) · `classificar` · `triagem` (prioridade de leitura só por @/nome; `triagem.json` opcional) · `coleta` (HTTP + sessão do usuário: seguidores, perfil, publicações, destaques) · `sessao` (DPAPI, fora do projeto) · `execucao` (fases lista → perfis → publicações; checkpoint, retomada, modo noite) · `revisao` (pacote, decisões em lote, divergências) · `exportar` · `cli`.
- O `painel` próprio (127.0.0.1:8766) foi removido em 20/10/2026: a interface é a plataforma, em 127.0.0.1:8770.
- Regras do projeto: nunca contornar CAPTCHA/checkpoint/bloqueio/429 (sem proxy, troca de IP, impersonação de TLS ou contas falsas); aguardar ou parar e informar. Não inventar seguidores nem preencher listas. Nunca imprimir/logar cookies. @ citados na bio/legendas não são evidência.
- Ao mudar regras de classificação: rode os testes e meça sem gravar nada sobre as análises reais (carregue `iterar_registros`, reclassifique em memória e compare). Só use `prospeccao reclassificar` numa análise quando for intencional. Lembre que a mudança afeta também o segmento inferido das empresas (`segmentos_de_texto`).
- `resultados/` tem dados reais de terceiros: não publicar.
