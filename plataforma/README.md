# Plataforma de prospecção

Uma única interface local para as duas automações deste diretório:

| Automação | Pasta | O que faz |
|---|---|---|
| Análise de seguidores do Instagram | `instagram/` (pacote `prospeccao`) | Lê os seguidores de um @ e classifica cada perfil nos 13 segmentos de parceiros (A–M) |
| Pesquisa de empresas | `pesquisa-empresas/` (pacote `empresas`) | Pesquisa empresas na internet (busca, site oficial, bases abertas da Receita) e registra cada dado com fonte e confirmação |

A plataforma não substitui nenhuma delas. Ela as executa, acompanha o andamento e junta os resultados numa **base
consultável**:

- empresas e perfis com filtros, detalhes e histórico;
- a **fila de pesquisa**, que liga as duas metades do trabalho;
- vínculo perfil ↔ empresa;
- revisão de duplicidades;
- revisão pelo Claude Code.

Desde 20/10/2026 ela é a **única** interface: os painéis próprios das duas ferramentas (8765 e 8766) foram
removidos.

## O fluxo em uma frase

A análise do Instagram descobre **quem** interessa (o @, o nome e o segmento A–M); a pesquisa de empresas descobre
**quem é essa empresa** (CNPJ, telefone, endereço, site). Entre as duas está a **fila**:

```
Instagram  ->  FILA (pendente)  ->  pesquisa de empresas  ->  base de empresas
```

Todo perfil `identificado`, de execução não arquivada e sem empresa confirmada entra na fila sozinho, e sai dela
quando ganha a empresa. Assim nada se perde se você parar e voltar noutro dia.

Custo: zero. Não há API paga nem serviço externo novo, e tudo roda em `127.0.0.1`.

---

## Abrir

Clique duas vezes em **`Abrir plataforma.cmd`**, na pasta raiz. Ou, no terminal:

```powershell
cd "C:\Users\User\Desktop\Nova pasta (2)"
.\.venv\Scripts\python -m plataforma painel        # abre http://127.0.0.1:8770
```

Fechar a janela encerra só a interface. Análises e pesquisas em andamento continuam rodando e reaparecem ao reabrir.

### Instalar (só se recriar o ambiente)

Clique duas vezes em **`instalar.cmd`**, na raiz. Ou, no terminal:

```powershell
cd "C:\Users\User\Desktop\Nova pasta (2)"
py -3.14 -m venv .venv
.\.venv\Scripts\pip install -e ".\instagram[dev]"
.\.venv\Scripts\pip install -e ".\pesquisa-empresas[dev]"
.\.venv\Scripts\pip install -e ".\plataforma[dev]"
```

**A ordem importa**: `pesquisa-empresas` depende de `prospeccao-instagram` (que define os 13 segmentos A–M) e a
plataforma depende das duas. Há um ambiente só, na raiz; os `.venv` que existiam dentro de `instagram/` e
`pesquisa-empresas/` foram removidos em 20/10/2026.

---

## Áreas da interface

| Área | Para quê |
|---|---|
| **Visão geral** | Totais, execuções em andamento ou que precisam de atenção, próximos passos e perfis por segmento |
| **Instagram** | Iniciar uma análise (@, segmentos, limite, modo noite), ver a sessão e a lista de análises |
| **Fila de pesquisa** | Quem foi identificado e ainda espera os dados da empresa. Pesquisar os pendentes, ou dispensar quem não é empresa |
| **Empresas** | Base de empresas com busca e filtros combináveis, exportação CSV/XLSX, nova pesquisa e "pesquisar novamente" |
| **Perfis** | Todos os perfis analisados, com segmento, situação e empresa vinculada. Permite pesquisar as empresas dos filtrados |
| **Execuções** | Histórico de análises, pesquisas e revisões pelo Claude, com estado real, progresso, falhas e pendentes |
| **Revisão** | Duplicidades sugeridas, vínculos sugeridos, execuções com itens incertos e perfis sem pesquisa |
| **Sistema** | Sessão do Instagram, SearXNG, Claude Code, pastas, sincronização e suas decisões recentes |

### Painel de uma análise do Instagram

- **Fases e números:** as 4 fases (lista → perfis → publicações → resultado) e os contadores (obtidos, analisados, bios
  lidas, identificados, para revisar, falhas, pendentes).
- **Andamento:** última etapa registrada, tempo de execução e estimativa medida no ritmo real.
- **Avisos:** separados em "Precisa de você" e "Temporário".
- **Conclusão:** só é **completa** quando a lista acessível foi percorrida até o fim. Os outros casos aparecem como:

  | Caso | Como aparece |
  |---|---|
  | Chegou ao limite definido | "Concluída parcialmente", com o total público do perfil |
  | O Instagram limita a lista | "Concluída parcialmente" |
  | O processo morreu | "Parada sem finalizar" |
  | Pausada por bloqueio | "Pausada" ou "Precisa de você" |

- **Ações:** retomar (com novo limite e modo noite), parar com segurança e arquivar.
- **Pesquisar as empresas destes perfis:**
  - escolha "identificados" ou "identificados + para revisar" e filtre por segmento;
  - a prévia mostra a lista que será enviada;
  - perfis já pesquisados nos últimos 30 dias são pulados.
- **Revisão pelo Claude:** copiar o pedido para o chat, ou revisar em segundo plano.

### Painel de uma pesquisa de empresas

Mostra:

- progresso, empresas em andamento e estado;
- contagem por resultado (CNPJ confirmado, provável, sem CNPJ, não encontrada, erro), itens para revisar e revisados;
- campos encontrados e origem dos dados (site oficial, Receita, busca…), com os sites mais consultados;
- itens com erro técnico.

"Refazer falhas" e "Retomar" pesquisam só o que falta.

### Base de empresas

**Filtros**, combináveis entre si e aplicados no banco:

- busca por nome, @, CNPJ, site ou cidade;
- UF e cidade (com ou sem acento);
- segmento A–M, por origem (perfil identificado ou inferido);
- status, confiança;
- Instagram (com, sem, vinculado, sugerido) e contato (com, sem, WhatsApp);
- pendências: revisar, não confirmados, sem CNPJ, divergência, possível duplicidade, desatualizada, erro;
- origem (via Instagram ou lista), execução e período.

Também dá para ordenar e paginar, e a exportação CSV/XLSX usa os mesmos filtros.

**Detalhe de cada empresa:**

- **Todos os campos**, cada valor com a origem, o link da fonte e o estado: **Confirmado / Parcialmente confirmado /
  Não confirmado / Não encontrado**. São os mesmos dados da ferramenta de empresas; nada é reclassificado.
- **Perfis do Instagram vinculados**, com a evidência. Dá para confirmar, rejeitar ou vincular outro.
- **Duplicidades:** possíveis duplicidades, com as opções unir ou "são diferentes".
- **Histórico:** histórico de pesquisas (com "separar", se uma pesquisa for de outra empresa), candidatos a CNPJ,
  alternativas descartadas e revisões registradas.

---

## Fluxo completo

1. **Instagram:** informe o @ e inicie. A análise roda como processo próprio e grava tudo na hora (checkpoint).
2. A plataforma lê as pastas a cada 4 s e mostra o andamento. Os perfis entram na base de perfis e os identificados
   entram na **fila de pesquisa**.
3. **No mesmo dia ou depois**, esvazie a fila, de uma destas três formas (todas fazem a mesma pesquisa):

   | Onde | Como |
   |---|---|
   | Aba **Fila de pesquisa** | Botão **Pesquisar pendentes** (dá para filtrar por segmento e limitar a quantidade) |
   | Painel de uma análise | **"Pesquisar as empresas destes perfis"**, só os daquela análise |
   | Claude Code, no VS Code | O comando **`/executar-tarefa`**, que também revisa os incertos com fonte |

   A lista sai no formato `Nome | @perfil | Cidade/UF`, e a pesquisa fica ligada à análise de origem.
4. A ferramenta de empresas pesquisa (≈5–15 s por empresa, 3 em paralelo). Pode parar e retomar sem repetir nada.
5. As empresas entram na base **vinculadas aos perfis**. O vínculo é confirmado porque a pesquisa partiu do @. Elas
   recebem o segmento do perfil identificado.
6. Revise os incertos: pelo chat ("Copiar pedido") ou em segundo plano (o Claude registra cada confirmação com a URL
   da fonte).
7. Em **Empresas**, filtre por UF/cidade e segmento, abra os detalhes e exporte.

---

## Como os dados são organizados

- **Fonte da verdade:** as pastas de resultados das ferramentas (`*.jsonl` com checkpoint), sem mudanças de formato.
- **Banco de consulta:** `plataforma/dados/plataforma.sqlite`, com dois tipos de conteúdo:

| Tipo | Conteúdo | O que acontece com ele |
|---|---|---|
| Derivado | Execuções, perfis, pesquisas, campos de filtro das empresas, **a fila** | É refeito a partir das pastas, a qualquer momento |
| Seu | Atribuição pesquisa → empresa, uniões e separações, vínculos confirmados ou rejeitados à mão, duplicidades decididas, execuções arquivadas, **perfis dispensados da fila**, histórico de decisões | Fica preservado entre sincronizações. **Faça backup desse arquivo** |

- **Migrações:** são automáticas, pelo `PRAGMA user_version`. Cada versão nova do esquema acrescenta um passo em
  `db.py`; nenhum passo antigo é alterado. Para reconstruir só o derivado:
  `.\.venv\Scripts\python -m plataforma sincronizar --completa`.

### Mesma empresa, duplicidades e vínculos

**Quando duas pesquisas viram uma empresa só.** Elas precisam compartilhar uma **chave forte**:

- CNPJ confirmado;
- @ informado na lista ou confirmado (site oficial linka o perfil, ou revisão);
- site oficial confirmado.

Hospedagens compartilhadas não unem nada: `*.wixsite.com`, `*.negocio.site`, linktree e similares.

**Quando a mesma entrada se repete** (por exemplo, "pesquisar novamente"), as pesquisas também viram uma empresa,
desde que **nenhum** CNPJ, site ou @ confirmado conflite.

**O que nunca une automaticamente:**

- CNPJs confirmados de raízes diferentes. Matriz e filial (mesma raiz) são a mesma empresa.
- Nome igual. Vira **sugestão** em Revisão, e você decide: unir ou "são diferentes".

**Quando uma correção muda identificadores.** Se uma correção remove o identificador que uniu duas pesquisas, a
associação automática é refeita. Uniões e separações feitas por você nunca são desfeitas.

**Pesquisas exibidas e segmento:**

- A empresa exibe a **pesquisa mais recente sem erro técnico**. As anteriores ficam no histórico.
- **Segmento (A–M):** é o **único** critério de classificação do projeto. Vem, nesta ordem:
  1. do **perfil vinculado e identificado** — a evidência mais específica (uma funerária *pet* tem CNAE de funerária,
     mas é E, não F);
  2. sem perfil, do **segmento que a pesquisa já resolveu** pelo CNAE da Receita ou pelo tipo declarado no site;
  3. sem nenhum dos dois, da **inferência pelo nome**, com as mesmas regras A–M.

  Os casos 2 e 3 aparecem tracejados, marcados "inferido, não confirmado", e podem ser filtrados à parte. Empresa
  fora dos 13 segmentos fica **sem segmento** — é o esperado, não uma falha. Não existem mais categorias comerciais
  genéricas (padaria, restaurante): foram removidas em 20/10/2026.

**Vínculos perfil ↔ empresa:**

| Situação | Vínculo |
|---|---|
| A pesquisa partiu do @, ou o site oficial linka o perfil | Confirmado |
| Perfil achado só pela busca, ou link da bio aponta para o site da empresa | Sugerido; você confirma ou rejeita |

Decisões suas prevalecem sobre a sincronização.

**Pastas de resultados:**

- Uma pasta apagada sai da base, mas só se ela realmente não existir e a pasta raiz estiver acessível.
- Uma pasta que volta reencontra as suas decisões.
- Arquivar esconde a execução sem apagar arquivos.

---

## Revisão pelo Claude Code

| Forma | Como funciona |
|---|---|
| **Copiar pedido** | Gera o texto para colar no chat (`/pesquisa-empresas Revise o lote "…"`). Nada roda sem você ver |
| **Revisar em segundo plano** | Roda `claude -p` (o `claude.exe` da extensão do VS Code, ou `PLATAFORMA_CLAUDE`) com a sua assinatura: sem custo extra, mas consome a cota de uso |

A revisão em segundo plano roda em `--permission-mode dontAsk`. Ela só pode:

- executar a própria ferramenta, nos subcomandos `revisar`, `corrigir` e `exportar` (regras de prefixo exato);
- ler a skill;
- no caso de empresas, buscar e ler páginas na web.

Qualquer outra ação é negada automaticamente. O andamento, as ações executadas e o resumo final aparecem em
**Execuções**. Há tempo máximo de 1 hora e um botão para parar.

---

## Linha de comando

```powershell
.\.venv\Scripts\python -m plataforma painel [--porta 8770] [--sem-navegador]
.\.venv\Scripts\python -m plataforma sincronizar [--completa]     # atualiza o banco a partir das pastas
.\.venv\Scripts\python -m plataforma resumo                       # visão geral em JSON

# fila de pesquisa
.\.venv\Scripts\python -m plataforma fila resumo                  # quantos pendentes, por segmento
.\.venv\Scripts\python -m plataforma fila listar [--estado …] [--segmentos A,B] [--limite N] [--json]
.\.venv\Scripts\python -m plataforma fila pesquisar [--limite N] [--segmentos A,B]
.\.venv\Scripts\python -m plataforma fila dispensar @perfil --motivo "não é empresa"
.\.venv\Scripts\python -m plataforma fila reabrir @perfil
```

`fila listar --json` é o que o comando `/executar-tarefa` do Claude Code usa.

As CLIs `prospeccao` e `empresas` e as skills continuam iguais. As ferramentas ganharam:

- `empresas parar [LOTE]` (parada segura);
- a variável `EMPRESAS_ENTRADAS`;
- trava de processo único por lote ou análise.

## Variáveis de ambiente

| Variável | Padrão | Uso |
|---|---|---|
| `PLATAFORMA_PORTA` | `8770` | Porta da interface |
| `PLATAFORMA_DADOS` | `plataforma/dados` | Banco, log e revisões do Claude |
| `PLATAFORMA_CLAUDE` | extensão do VS Code (versão mais nova) | Caminho do `claude.exe` |
| `PLATAFORMA_DIAS_REPESQUISA` | `30` | Pula perfis cuja empresa foi pesquisada há menos que isso |
| `PLATAFORMA_DIAS_DESATUALIZADA` | `90` | Empresa "desatualizada" no filtro de pendências |
| `PROSPECCAO_RESULTADOS`, `EMPRESAS_RESULTADOS`, `EMPRESAS_ENTRADAS`, `EMPRESAS_CACHE`, `SEARXNG_URL` | — | Das ferramentas (veja os READMEs delas) |

Nenhum segredo fica no projeto. A sessão do Instagram continua criptografada (DPAPI) em
`%LOCALAPPDATA%\prospeccao-instagram` e nunca é enviada à interface.

## Segurança

- A interface atende só em `127.0.0.1`.
- Ela recusa Host estranho (DNS rebinding) e ações vindas de outros sites: exige Origin próprio e corpo JSON.
- A CSP bloqueia scripts externos.
- Downloads só saem de uma lista fixa de arquivos dentro das pastas de resultados.
- Nomes de execução são validados contra a listagem real, inclusive as particularidades do Windows.
- Valores vindos da web não viram fórmula nas planilhas.

## Testes

```powershell
cd plataforma;          ..\.venv\Scripts\python -m pytest -q    # 69 testes
cd ..\pesquisa-empresas; ..\.venv\Scripts\python -m pytest -q   # 31
cd ..\instagram;         ..\.venv\Scripts\python -m pytest -q   # 163
```

Detalhes e testes reais em [TESTES.md](TESTES.md).

## Limitações

- **A base reflete o que as ferramentas encontraram.** Dados não confirmados aparecem como tal; a plataforma não
  confirma nada sozinha.
- **Segmento inferido** pelo CNAE ou nome é só indicativo.
- **Pesquisa de empresas a partir de perfis:** a qualidade depende do nome e da cidade do perfil. Perfis de pessoas
  ou de fora do Brasil tendem a dar "parcial" ou "não encontrada".
- **Revisão em segundo plano** depende do Claude Code instalado e logado. Ela consome cota da assinatura.
- **SearXNG** é opcional. Sem o Docker ligado, a pesquisa usa a contingência `ddgs`, com menos buscadores.
- **Escala:** já foi usada com uma base real de 3 análises, 1.004 perfis, 14 lotes e 113 pesquisas, com a
  sincronização inicial em cerca de 1 s (essa base foi arquivada em `_backup/` na limpeza de 20/10/2026). Análises
  com dezenas de milhares de perfis devem funcionar, mas não foram medidas.
