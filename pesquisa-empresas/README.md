# Pesquisa de empresas

Ferramenta local que pesquisa empresas brasileiras na internet e gera uma planilha com dados públicos
(CNPJ, razão social, situação cadastral, categoria, atividade, endereço completo, CEP, Google Maps, telefones,
WhatsApp, e-mails, site, Instagram e seguidores, Facebook, LinkedIn, horário de funcionamento). Cada valor vem com
a URL de origem e cada empresa recebe status e nível de confiança.

**Política: trazer o máximo de dados, marcando o que não está confirmado.** Um dado encontrado sem prova de que
pertence à empresa (CNPJ só provável, perfil achado só pelo nome, site que bloqueou a leitura, categoria inferida)
entra na planilha com o sufixo "(não confirmado)" e célula laranja, em vez de ser descartado. Só fica de fora o que
tem evidência contrária (ex.: site de uma homônima de outra cidade), e mesmo isso vai para a aba Alternativas.

Custo: zero. Não usa API paga nem chave de API. Usa sua assinatura do Claude Code e ferramentas abertas e gratuitas.

> **Plataforma unificada (20/10/2026):** a interface desta ferramenta é a plataforma em `../plataforma`
> (`Abrir plataforma.cmd` na raiz, <http://127.0.0.1:8770>), que junta as análises do Instagram e as pesquisas de
> empresas numa base consultável, com filtros por segmento e região, vínculos perfil ↔ empresa e histórico.
> Normalmente os lotes nascem da **fila de pesquisa** de lá. A CLI e a skill abaixo continuam funcionando; o painel
> próprio desta ferramenta foi removido.
>
> **Classificação (20/10/2026):** o campo `categoria` passou a ser o **segmento A–M** de parceiros do RIP Memorial
> (`"F · Crematórios e funerárias humanas"`), e não mais uma categoria comercial genérica. Empresa fora dos 13
> segmentos fica **sem segmento** — é o esperado.

---

## Como usar

### Pelo chat do Claude Code (forma principal)

Em qualquer sessão do Claude Code, em qualquer pasta, escreva algo como:

```
Pesquise estas empresas e gere a planilha:
@padariareal
Confeitaria Colombo | Rio de Janeiro/RJ
www.empresa.com.br
12.345.678/0001-90
```

Ou chame a skill direto: `/pesquisa-empresas @perfil1 @perfil2 ...`

A skill `pesquisa-empresas` (em `C:\Users\User\.claude\skills\pesquisa-empresas\SKILL.md`) faz o Claude:

1. gravar a lista em `entradas/`;
2. rodar a pesquisa automática;
3. revisar os casos incertos com WebSearch/WebFetch e registrar as correções com fonte;
4. entregar um resumo e o caminho da planilha.

**Dicas para a lista:**

- Uma empresa por linha.
- Adicione pistas com `|`, como `Nome | Cidade/UF | @instagram | site`. Informar a cidade ajuda muito a separar empresas com o mesmo nome.
- Também aceita `.csv` ou `.xlsx` com colunas `nome`, `instagram`, `site`, `cnpj`, `cidade`, `uf`.

### Pelo terminal

```powershell
cd "C:\Users\User\Desktop\Nova pasta (2)\pesquisa-empresas"
.\.venv\Scripts\empresas.exe pesquisar entradas\minha-lista.txt --nome clientes-outubro
```

| Comando | O que faz |
|---|---|
| `empresas pesquisar ARQ [--nome N] [--workers 3]` | Pesquisa a lista (`.txt`, `.csv` ou `.xlsx`) e gera as planilhas |
| `empresas pesquisar --texto "A\nB"` | Mesma coisa, com a lista passada direto no comando |
| `empresas retomar [LOTE]` | Continua um lote interrompido e refaz as empresas que deram erro |
| `empresas status [LOTE]` | Mostra o andamento |
| `empresas parar [LOTE]` | Para com segurança: as empresas em andamento terminam e as demais ficam para `retomar` |
| `empresas revisar [LOTE] [--todos]` | Lista em JSON o que precisa de revisão (status provável/parcial, confiança baixa, divergência ou campos importantes não confirmados) |
| `empresas corrigir [LOTE] --linha N --campo C --valor V --fonte URL [--nota] [--confianca] [--substituir] [--remover]` | Registra uma correção com fonte |
| `empresas corrigir ... --campo C [--valor V] --confirmar --fonte URL` | Confirma valor(es) já encontrado(s); com `--campo cnpj` confirma o CNPJ provável |
| `empresas corrigir ... --valor V --fonte URL --nao-confirmado` | Registra um valor marcado como não confirmado |
| `empresas exportar [LOTE]` | Regenera o XLSX e os CSVs |
| `empresas lotes` | Lista os lotes |
| `empresas verificar` | Testa os buscadores e as APIs de CNPJ |

`LOTE` pode ser o nome da pasta, um pedaço do nome, ou ficar em branco (usa o último lote).

### Interface

Esta ferramenta não tem mais painel próprio. A interface é a **plataforma**, em <http://127.0.0.1:8770>
(`Abrir plataforma.cmd` na raiz do projeto): lá dá para iniciar pesquisas, acompanhar o progresso, filtrar a base
por segmento e região, ver o vínculo com os perfis do Instagram e exportar.

---

## Onde ficam os resultados

Cada pesquisa cria uma pasta `resultados/<data>_<nome>/` com estes arquivos:

| Arquivo | Conteúdo |
|---|---|
| `empresas.xlsx` | Planilha principal com as abas abaixo |
| `empresas.csv` | Aba principal em CSV separado por `;` (abre direto no Excel em português) |
| `fontes.csv` | Uma linha por valor encontrado, com a URL que o comprova |
| `registros.jsonl` | Dados brutos, um registro por empresa. É a fonte da verdade e permite retomar o lote |
| `correcoes.jsonl` | Histórico das correções feitas na revisão |
| `progresso.json` | Andamento do lote (com PID e batimento a cada 20 s; status `executando`, `concluido`, `concluido_com_erros`, `interrompido` ou `erro`) |
| `executando.lock` | Existe só durante a execução: impede dois processos no mesmo lote |
| `plataforma.json` | (quando criado pela plataforma) descrição e análise do Instagram de origem |

Abas do `empresas.xlsx`:

| Aba | Conteúdo |
|---|---|
| Empresas | Uma linha por empresa. Coluna "Campos não confirmados" lista o que está marcado |
| Fontes | Valor, se está confirmado, origem e URL de cada dado |
| Alternativas | CNPJs considerados (com o escolhido marcado como "sim" ou "provável", pontuação e motivos) e sites rejeitados com o motivo |
| Consultas | Buscas feitas e páginas lidas |
| Legenda | Significado de cada status, nível de confiança e origem |

### Status

| Status | Significado |
|---|---|
| `identificada` | CNPJ confirmado na base da Receita |
| `provavel` | CNPJ preenchido com o candidato mais plausível, **não confirmado**. As Observações dizem por quê (empate, cidade diferente, achado só pelo nome) e os outros candidatos ficam na aba Alternativas |
| `parcial` | Site, perfil ou contatos encontrados, mas sem CNPJ |
| `nao_encontrada` | Nada encontrado (candidatos sem relação com o nome ficam só na aba Alternativas) |
| `ambigua` | Só em lotes antigos (antes de 19/10/2026): nenhum CNPJ escolhido |
| `erro` | Falha técnica; rode `retomar` |

### Colunas novas (19/10/2026)

| Coluna | De onde vem |
|---|---|
| Categoria | CNAE da Receita traduzido para algo legível ("Restaurante", "Funerária / serviços funerários"). Se o CNAE for genérico (escritório, holding, atacado) ou não houver CNPJ, é inferida pelo tipo declarado no site ou por palavras do nome/site, e fica não confirmada |
| Seguidores Instagram (aprox.) | Número que o buscador mostra para o perfil (arredondado pelo Instagram). Número, ordenável no Excel |
| Horário (como publicado) | Texto do site/perfil ("Segunda a sábado: 11h40 às 22h") ou dados estruturados. Pode ser o horário da loja ou do atendimento; veja a fonte |
| Avaliação | Só quando o próprio site publica em dados estruturados, ou registrada na revisão |
| Endereço completo | Rua, bairro, cidade/UF e CEP numa célula só. Quando só o CEP é conhecido, rua/bairro/cidade vêm da consulta de CEP |
| Campos não confirmados | Lista dos campos da linha marcados como não confirmados |

### Confiança

| Nível | Quando |
|---|---|
| `alta` | CNPJ informado na lista, publicado no site ou perfil da empresa, ou confirmado por várias evidências (nome, cidade, domínio do e-mail, telefone, endereço) |
| `media` | Boa correspondência, mas com alguma divergência, ou existem outras empresas ativas com o mesmo nome (franquias) |
| `baixa` | Confira antes de usar (todo registro `provavel` é baixa) |

Campos vazios significam "nada encontrado". Valores sem prova aparecem como "(não confirmado)", nunca como confirmados.

---

## Como funciona

```
lista ──► interpretação (@perfil / site / CNPJ / nome + pistas)
      ──► busca web: SearXNG local (Bing, DuckDuckGo, Yahoo, Brave...) ─ contingência: biblioteca ddgs
      ──► site oficial: página inicial + contato/sobre/privacidade/lojas
           (links tel:, wa.me, mailto:, JSON-LD schema.org, rodapé com CNPJ, redes sociais)
      ──► Instagram: nome público do perfil + bio mostrada no trecho do buscador
      ──► CNPJ: candidatos do site/perfil (evidência forte) ou de buscas (fraca)
           ──► consulta nas bases abertas da Receita: OpenCNPJ → BrasilAPI → minhareceita.org → CNPJá
           ──► pontuação: nome, cidade/UF, CNPJ publicado no site, domínio do e-mail,
               telefone e endereço coincidentes, situação cadastral
      ──► consolidação com fonte por campo, divergências e status
      ──► XLSX/CSV  ──► revisão pelo Claude (casos incertos)
```

### Salvaguardas contra associar dados à empresa errada

- **Site de empresa homônima em outra cidade:** o site é descartado (vai para a aba Alternativas) e o motivo fica registrado.
- **Evidência só de dados confirmados:** um perfil ou site não confirmado nunca serve para confirmar um CNPJ.
- **CNPJ provável:** entre os candidatos plausíveis, empresas ativas têm preferência sobre baixadas/inaptas.
- **Títulos genéricos:** nomes como "Home" ou "Início" nunca são usados como nome da empresa.
- **Diretórios e guias de empresas:** não são aceitos como site oficial.
- **Lojas franqueadas** (nome = marca + local): são penalizadas na escolha do CNPJ.
- **Mesma raiz de CNPJ (matriz e filiais):** conta como uma única empresa. Sem pista da unidade, a ferramenta escolhe a matriz. Se o endereço ou o telefone do site bater com uma única unidade, escolhe essa unidade.
- **CNPJ baixado publicado no site:** a ferramenta também consulta a matriz da mesma raiz.
- **Sites com proteção anti-robô** (Cloudflare etc.): não são contornados; ficam registrados como "não lido".
- **robots.txt:** é respeitado.

### Fontes e limites (todas gratuitas, sem chave)

| Fonte | Uso | Limite conhecido |
|---|---|---|
| SearXNG local (Docker) | Busca web | Nenhum próprio. Os buscadores consultados podem bloquear temporariamente |
| `ddgs` (Python) | Busca web de contingência | Não documentado; bloqueios aparecem como "sem resultados" |
| OpenCNPJ | Dados de CNPJ, com e-mail e telefone | Não publicado |
| BrasilAPI / minhareceita.org | Dados de CNPJ (sem e-mail) | Não publicado |
| CNPJá open | Dados de CNPJ (última contingência) | 5 consultas por minuto |
| BrasilAPI CEP / ViaCEP | Completar rua/bairro/cidade a partir do CEP | Não publicado |
| r.jina.ai | Leitura de sites que só funcionam com JavaScript | Cerca de 20 por minuto. Recebe só a URL pública. Desative com `EMPRESAS_JINA=0` |

O cache em `cache/cache.sqlite` evita repetir requisições:

| Tipo | Validade |
|---|---|
| Buscas | 7 dias |
| Páginas | 7 dias |
| Dados de CNPJ e de CEP | 30 dias |

---

## Manutenção

### SearXNG (opcional, recomendado)

O SearXNG precisa do Docker Desktop aberto. Ele roda em `127.0.0.1:8888` e não fica exposto na rede.

```powershell
docker compose up -d     # liga (volta sozinho quando o Docker abre)
docker compose down      # desliga
```

Sem o SearXNG, a ferramenta usa o `ddgs` automaticamente. Funciona, mas com menos buscadores.

A configuração fica em `searxng/settings.yml`. Ela parte dos padrões oficiais e só habilita JSON, Bing e Yahoo.

### Atualizar e reinstalar

```powershell
.\.venv\Scripts\python -m pip install -U ddgs httpx openpyxl selectolax tldextract rapidfuzz
docker compose pull; docker compose up -d
```

Para reinstalar do zero (Python 3.11 ou mais novo):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
```

### Testes

```powershell
.\.venv\Scripts\python -m pytest -q      # testes de unidade (CNPJ, extração, entradas, confirmação, categorias)
.\.venv\Scripts\empresas.exe verificar   # componentes externos
```

### Configuração por variável de ambiente

| Variável | Padrão |
|---|---|
| `SEARXNG_URL` | `http://127.0.0.1:8888` |
| `EMPRESAS_JINA` | `1` |
| `EMPRESAS_RESULTADOS` | pasta de resultados |
| `EMPRESAS_ENTRADAS` | pasta `entradas` |
| `EMPRESAS_CACHE` | caminho do cache |

Os intervalos entre requisições ficam em `empresas/config.py`.

### Estrutura do código

| Arquivo | Responsabilidade |
|---|---|
| `entradas.py` | Interpreta a lista (txt, csv ou xlsx) |
| `web.py` | Busca e leitura de páginas (cache, robots.txt, ritmo por domínio) |
| `extrair.py` | E-mails, telefones, WhatsApp, redes, CNPJ, CEP, endereço, horário, seguidores, avaliação, JSON-LD |
| `categorias.py` | CNAE / tipo schema.org / nome → **segmento A–M** (definidos em `../instagram/prospeccao/categorias.py`) |
| `cnpj.py` | Validação de CNPJ, inclusive alfanumérico |
| `cadastro.py` | APIs de CNPJ e de CEP com contingência |
| `pesquisa.py` | Lógica de identificação, pontuação e consolidação |
| `lote.py` | Execução em paralelo com checkpoint e retomada |
| `exportar.py` | XLSX e CSV |
| `cli.py` | Comandos |

---

## Limitações conhecidas

- **Franquias e marcas com muitos CNPJs** (Giraffas, Boticário, Casa do Pão de Queijo...): sem CNPJ publicado no site, ficam como `provavel` (melhor candidato, não confirmado), porque existem dezenas de franqueados com o mesmo nome fantasia. Confira na aba Alternativas.
- **Instagram sem login:** a página do perfil hoje não mostra dados sem login. Nome, bio e seguidores vêm do trecho que o buscador exibe; quando o buscador não mostra, ficam vazios. Login e CAPTCHA não são contornados.
- **Avaliações (nota do Google):** não são coletadas automaticamente. A API do Google é paga e raspar o Maps viola os termos; em testes, buscas por "avaliações" trouxeram nota para 1 de 8 empresas, com valores conflitantes. A coluna existe para quando o próprio site publica a nota ou quando ela é registrada na revisão.
- **Coordenadas (latitude/longitude):** não incluídas. A consulta de CEP gratuita devolve o centro da cidade para muitos CEPs, o que seria precisão falsa. O link do Google Maps (nome + endereço) abre o local certo.
- **Horário:** depende de o site ou perfil publicar em texto; às vezes é o horário do SAC, não da loja (a fonte mostra a página).
- **Categoria:** segue o CNAE oficial, que às vezes difere do que o público conhece (ex.: Havan é registrada como supermercado).
- **Sites com proteção anti-robô ou que só funcionam com JavaScript:** podem não ser lidos.
- **Busca por nome de empresas muito pequenas:** depende do que os buscadores indexam. Informar a cidade e o `@perfil` melhora bastante o resultado.
- **Dados do cadastro da Receita:** o telefone e o e-mail costumam ser do contador e ficam em colunas separadas. Em MEI e empresário individual podem ser pessoais; a planilha avisa nesses casos (LGPD).
- **Bloqueios temporários dos buscadores:** em lotes muito grandes (centenas de empresas), os buscadores podem bloquear por um tempo. Use `--workers 2` e `retomar` se necessário.
- **Opção não implementada, para listas enormes:** baixar a base aberta completa da Receita (cerca de 8 GB compactados, atualizada todo mês em `arquivos.receitafederal.gov.br`) e buscar por nome localmente.
