# Prospecção de parceiros pelo Instagram

Ferramenta local que recebe o @ de um perfil do Instagram, percorre os seguidores acessíveis e devolve uma lista de @
organizada pelos 13 segmentos comerciais do RIP Memorial. Cada @ vem com a evidência da classificação, a confiança, as
etapas usadas e o link do perfil. Os casos que o código não decide com segurança vão para um **pacote de revisão**,
que o Claude Code (pela sua assinatura) ou uma pessoa revisa depois.

Este módulo é independente da ferramenta `pesquisa-empresas` (CNPJ e contatos). Ele não pesquisa empresas na internet
e não enriquece contatos. Custo: zero. Não usa Apify, API paga nem chave de API, nem mesmo na revisão.

> **Plataforma unificada (20/10/2026):** esta ferramenta também pode ser usada pela interface única em `../plataforma` (`Abrir plataforma.cmd` na pasta raiz, http://127.0.0.1:8770), que junta as análises do Instagram e as pesquisas de empresas numa base consultável, com filtros, vínculos perfil ↔ empresa e histórico. A CLI, a skill e o painel abaixo continuam funcionando.

---

## 1. Configurar o ambiente (uma vez)

No VS Code: **Terminal → Novo terminal**:

```powershell
cd "C:\Users\User\Desktop\Nova pasta (2)\instagram"
.\.venv\Scripts\python -m pip install -e ".[dev]"     # já instalado; só se recriar o .venv
```

### Sessão do Instagram (obrigatória para coletar)

O Instagram só mostra a lista de seguidores, as bios e as publicações para quem está logado. A ferramenta usa a sessão
de uma conta sua e **nunca pede a senha**. Use uma **conta secundária**: leitura automatizada pode levar o Instagram a
pedir verificação ou a restringir temporariamente a conta.

| Opção | Como fazer |
|---|---|
| Importar do Firefox | Entre em instagram.com pelo Firefox e rode `.\.venv\Scripts\prospeccao.exe sessao firefox` (ou clique em **Importar do Firefox** no painel) |
| Colar o cookie | No navegador logado: F12 → Aplicativo (Chrome/Edge) ou Armazenamento (Firefox) → Cookies → `instagram.com` → valor de `sessionid`. Rode `prospeccao sessao definir` (entrada oculta) ou cole no painel |

Conferir: `prospeccao sessao testar` → "Sessão válida: logado como @...".

A sessão fica em `%LOCALAPPDATA%\prospeccao-instagram\sessao.bin`, fora do projeto, criptografada com o DPAPI do
Windows. Ela nunca aparece no painel, nos logs ou nas exportações e só é enviada ao instagram.com. Para apagar:
`prospeccao sessao remover`. Os cookies do Chrome e do Edge não são lidos: a criptografia vinculada ao app não é
contornada.

---

## 2. Usar pelo painel (forma principal)

```powershell
.\.venv\Scripts\prospeccao.exe painel
```

O painel abre em `http://127.0.0.1:8766`, acessível só deste computador.

1. Informe o @ de origem, por exemplo `@feirafunerariabrasil`.
2. Marque as categorias (todas vêm marcadas).
3. Se quiser, defina um limite de seguidores.
4. Leitura de perfis: `candidatos` é o recomendado.
5. Publicações: `duvidosos` é o recomendado.
6. **Modo noite**: marque para análises longas. Veja a seção 4.
7. Clique em **Iniciar análise**.

A página da análise mostra:

- **as 4 etapas** (lista de seguidores → perfis por prioridade → publicações dos duvidosos → resultado), com contagens;
- tempo decorrido, última etapa concluída e uma estimativa medida pelo ritmo real da execução;
- seguidores públicos, obtidos, analisados, bios lidas, publicações lidas, identificados, para revisar, sem
  informação suficiente, repetidos e falhas;
- avisos separados em **Precisa de você** (verificação de segurança, sessão expirada, perfil inacessível) e
  **Temporário** (o Instagram pediu para esperar, a internet caiu);
- os @ por categoria, com **filtros** por categoria, confiança e situação;
- links para o CSV, a lista Markdown e o **pacote de revisão** (Markdown, JSON e modelo de decisões);
- **Parar com segurança** e **Retomar**, que continua de onde parou sem repetir perfis.

A porcentagem só aparece para a lista de seguidores e quando o total é conhecido (limite ou total público do perfil).
Ela não aparece quando o Instagram limita a lista.

## 3. Usar pelo terminal

```powershell
.\.venv\Scripts\prospeccao.exe analisar @feirafunerariabrasil -l 500
.\.venv\Scripts\prospeccao.exe analisar @feirafunerariabrasil --noite          # análise longa, para deixar à noite
.\.venv\Scripts\prospeccao.exe retomar feirafuneraria --noite -l 3000          # continua e amplia o limite
```

| Comando | O que faz |
|---|---|
| `analisar @X [-c A,B…\|todas] [-l N] [-d candidatos\|todos\|nenhum] [-p duvidosos\|nenhuma] [--noite]` | Coleta e classifica os seguidores de @X |
| `analisar --arquivo lista.txt` | Classifica uma lista de @ já obtida (`.txt`/`.csv`, ou o `followers_1.json` do "Baixar suas informações" da Meta, que só vale para a sua própria conta) |
| `retomar [ANALISE] [-l N] [--noite\|--sem-noite]` | Continua uma análise interrompida, pausada ou que chegou ao limite |
| `parar [ANALISE]` | Para com segurança depois do perfil atual |
| `status [ANALISE]` | Andamento em JSON (fase, contadores, eventos) |
| `exportar [ANALISE]` | Gera de novo `resultados.csv` e `arrobas_por_categoria.md` |
| `pacote [ANALISE]` | Gera o pacote de revisão (`revisao/pacote.md`, `pacote.json`, `decisoes.json`) |
| `revisar [ANALISE] [--max N] [--todos]` | Itens pendentes do pacote em JSON (para o Claude no chat) |
| `aplicar-revisao [ANALISE] [--arquivo F]` | Aplica as decisões em lote |
| `corrigir [ANALISE] -u @X -c F,G \| --descartar [--nota] [--revisor]` | Registra uma decisão avulsa |
| `divergencias [ANALISE]` | Onde a revisão discordou do automático (material para ajustar regras) |
| `reclassificar [ANALISE]` | Reaplica as regras atuais aos dados já coletados, sem internet |
| `classificar @X --nome … --bio … [--categoria-ig …]` | Testa a classificação de um perfil digitado, sem rede |
| `listar` · `sessao …` · `painel` | Lista análises, gerencia a sessão, abre a interface |

`ANALISE` pode ser a pasta, um pedaço do nome ou ficar em branco (a mais recente).

### Pelo chat do Claude Code

A skill pessoal `prospeccao-instagram` (`~/.claude/skills/prospeccao-instagram/SKILL.md`) ensina o fluxo ao Claude.
Peça, por exemplo:

- "analisa os seguidores do @feirafunerariabrasil com limite de 500";
- "revisa os duvidosos da análise da feira e me dá a lista final".

O Claude lê o pacote em lotes, decide com base na bio, nas publicações e nos destaques, grava as decisões com nota e
aplica com `aplicar-revisao`.

---

## 4. Execução prolongada (modo noite)

A análise roda em **fases**. Tudo é gravado na hora e a fase atual é deduzida dos arquivos, não da memória:

1. **lista**: percorre a lista de seguidores e grava cada @ novo em `seguidores.jsonl`, já com a prioridade da
   triagem. A página inteira vai para o disco antes de o cursor avançar.
2. **perfis**: analisa em ordem de prioridade, para os perfis mais promissores saírem primeiro. Cada perfil é gravado
   em `perfis.jsonl` assim que é analisado.
3. **publicações**: duvidosos e contas comerciais sem categoria.

| Situação | O que acontece |
|---|---|
| Fechou o programa, a energia caiu, o PC reiniciou | Nada do que foi gravado se perde. Linhas cortadas pela queda são isoladas. **Retomar** continua sem repetir ninguém |
| Falha de rede passageira | Até 3 tentativas com intervalo crescente. Sem modo noite: pausa (`erro_rede`) e você retoma |
| O Instagram pede para esperar (429 / "Please wait a few minutes") | Espera 1, 3 e 10 min. **Com modo noite**, espera ainda 15, 30, 60 e 60 min e continua sozinho (as esperas voltam a valer depois de progresso real). Esgotadas: pausa (`pausado_limite_instagram`) |
| Verificação de segurança, checkpoint, `feedback_required`, sessão expirada | **Para na hora** e mostra "Precisa de você", também no modo noite. Resolva no Firefox, rode `sessao firefox` e retome |
| Perfil de origem inexistente ou privado | Para e informa |

Tempo medido (prova real de 150 seguidores, modo padrão): **18 minutos**, com 101 bios lidas, 25 perfis na etapa de
publicações e 24 leituras de destaques (~6,7 s por requisição). Projetando as proporções medidas no gabarito de 1.000
(54% das bios lidas, 16% na etapa de publicações), os ~12.800 seguidores de @feirafunerariabrasil dariam cerca de
10 mil requisições, ou seja, **18 a 26 horas**. Isso é só uma estimativa: o comportamento do Instagram em milhares de requisições seguidas não
foi testado. Rode em partes (`-l 2000`, depois `retomar -l 4000`…).

---

## 5. Resultados

Cada análise cria `resultados/<data>_<origem>/`:

| Arquivo | Conteúdo |
|---|---|
| `resultados.csv` | Uma linha por (perfil, categoria), `;`, abre no Excel. Inclui: situação, confiança, evidências, limitação, tipo de perfil, estado, categoria do Instagram, bio, outras categorias, nota de revisão, **etapas executadas, fontes usadas e prioridade na triagem** |
| `arrobas_por_categoria.md` | @ por categoria, possíveis correspondências separadas |
| `seguidores.jsonl` | Lista de seguidores com a prioridade da triagem (fase 1) |
| `perfis.jsonl` | Análises (fases 2 e 3). Vale o último registro de cada @, e a classificação automática original é preservada |
| `revisao/pacote.md` · `pacote.json` · `decisoes.json` | Pacote de revisão e modelo de decisões |
| `correcoes.jsonl` | Decisões de revisão, com nota e revisor |
| `estado.json` · `origem.json` · `log.txt` | Andamento e eventos · perfil de origem · saída das execuções do painel |
| `executando.lock` | Existe só durante a execução: impede dois processos na mesma análise |

`resultados/` contém dados reais de terceiros: fica no `.gitignore` e não deve ser publicada.

| Campo | Valores |
|---|---|
| Situação | `identificado` (confiança alta/média) · `revisar` (indício fraco, pessoa física, privado, criador de conteúdo, publicações sem oferta de serviço…) · `descartado` (pela revisão). Revisar nunca é apresentado como empresa confirmada |
| Confiança | `alta` (termo específico confirmado em mais de um campo ou pela categoria do Instagram) · `media` (um campo, só @/nome, só publicações, ou fornecedor do setor) · `baixa` |
| Tipo de perfil | `empresa`, `instituicao`, `profissional`, `pessoal`, `indeterminado` |
| Estado da análise | `completa` · `so_nome` (não lido pela triagem) · `privado` · `detalhes_indisponiveis` |
| Etapas | `lista`, `perfil`, `publicacoes`, `destaques`: quais leituras foram feitas para aquele @ |

---

## 6. Como a descoberta funciona

### Triagem em etapas (só com o @ e o nome, sem requisição extra)

| Prioridade | Quando | Lida no modo `candidatos`? |
|---|---|---|
| 0 segmento | Termo de algum segmento no @ ou nome, inclusive fraco ("pax", "placas", "urnas", "sepelios") | sim, primeiro |
| 1 comercial | Nome com cara de empresa ("Grupo", "Complexo", "inox", "&", "Memorial"…) | sim |
| 2 profissional | Nome de pessoa com cargo ("Dra.", "Consultor", "Cerimonialista") | sim |
| 3 indefinido | Nem nome de pessoa nem de empresa (`@ossel.compreagora`) | sim |
| 4 pessoa | Parece nome de pessoa ("Maria Souza", `joao_pereira89`). **Não é descartado**: fica por último e é lido no modo `todos` | não |
| 9 privado | Conta privada (o Instagram não permite conta comercial privada) | não |

Os critérios são configuráveis em `triagem.json`. Copie de `triagem.exemplo.json`. Dá para ajustar:

- até que prioridade cada modo lê;
- palavras comerciais e prenomes extras;
- @ a excluir;
- quem passa pela etapa de publicações;
- a leitura de destaques.

Medido no gabarito de 1.000 seguidores reais (a análise que você rodou no modo `todos`):

| | Triagem antiga | Triagem nova |
|---|---|---|
| Bios lidas | 167 | 538 (o `todos` lê 694) |
| Identificados que a triagem deixa de fora | **59 de 189 (31%)** | **4 de 205 (2%)**, todos com nome de pessoa |

### Etapa de publicações

Ela é usada só onde ajuda. Pela ordem:

1. classificação duvidosa;
2. conta comercial sem categoria;
3. sinais comerciais sem categoria;
4. bio vazia com @/nome de segmento ou comercial.

Para cada um, lê fixados e as últimas 12 publicações (legenda, hashtags, local) com a mesma consulta GraphQL do site
(`PolarisProfilePostsQuery`). Os títulos dos destaques são lidos só para os duvidosos que continuarem inconclusivos.
Regras:

- Um termo numa única publicação é só indício; vale quando se repete ou está num **post fixado**.
- **Categoria sustentada só pelas publicações exige oferta de serviço** no mesmo post (orçamento, WhatsApp, valores,
  planos, entrega, atendimento…). Sem isso, vai para revisão. Isso evita páginas que só falam do tema, como lendas de
  cemitério. As palavras do próprio nome do perfil não contam como oferta.
- O local marcado conta quando se repete ou tem o nome do próprio perfil; um local visitado uma vez não conta.
- @ citados nas legendas não contam.

### Classificação (regras, sem custo por perfil)

As regras ficam em `prospeccao/categorias.py`:

- pesos 3/2/1;
- frases compostas que reservam o trecho ("crematório pet" não é crematório humano);
- vocabulário em português, espanhol e inglês (sepelios, ataúdes, cementerio, cremation, burial, embalming…).

Também em `classificar.py`:

- **@ de outras contas citados na bio não são evidência** ("Casado com @…dafuneraria").
- **Pessoa física** (casado(a), 💍, papai/mamãe, versículo, estudante, "cursando", "Blog pessoal") e **criador de
  conteúdo** sem sinal comercial forte vão no máximo para revisão.
- Religião declarada por pessoa ("Católica") não é igreja; exige contexto institucional (igreja, paróquia, missa…).
- **Fornecedores do setor** (sistemas, cursos, fábricas, mídia, congressos) ficam identificados com a ressalva "atua
  para o setor".
- Perfil pet com termos funerários genéricos não vira funerária humana.
- Psicólogo sem menção a luto vai para revisão.

### Por que esta forma de coleta (pesquisa e testes de 19/10/2026)

| Alternativa | Resultado |
|---|---|
| API oficial da Meta | Não lista seguidores nem publicações de outras contas |
| Sem login | `web_profile_info` dá 429 na 1ª chamada; páginas de perfis comuns vêm vazias |
| Instaloader 4.15.4 | `get_followers()` quebrado desde set/2026 (issue #2741). Usado como referência para as consultas de perfil, publicações e destaques |
| instagrapi | API privada do app; relatos de "ChallengeRequired" (issue #2797) |
| **Endpoints do site com a sessão do usuário (escolhida)** | Seguidores (`friendships/<id>/followers`), perfil (GraphQL), publicações (GraphQL) e destaques (consulta legada) testados aqui e funcionando. Feed e destaques via REST (`/api/v1/feed/user`, `highlights_tray`) respondem 302 e não são usados |

### Salvaguardas

- Ritmo de 4–5 s entre requisições com variação, mais pausa de 60 s a cada 60. É ajustável por
  `PROSPECCAO_INTERVALO_PAGINA`, `PROSPECCAO_INTERVALO_PERFIL`, `PROSPECCAO_PAUSA_A_CADA` e `PROSPECCAO_PAUSA_LONGA`.
- Limite de requisições: espera, depois pausa. Verificação de segurança: para. **Nada é contornado**: não há CAPTCHA,
  proxy, troca de IP ou de conta, nem disfarce de navegador ou de impressão digital TLS.
- Lista parcial do Instagram (`should_limit_list_of_followers`) é registrada e informada.
- O painel atende só em 127.0.0.1 e recusa formulários de outros sites (CSRF) e hosts estranhos (DNS rebinding).

---

## 7. Limitações conhecidas

- Exige sessão logada. O uso prolongado pode levar o Instagram a pedir verificação da conta.
- Escala: só testada até 1.000 seguidores (a sua análise, sem nenhum bloqueio). Análises de vários milhares levam
  horas, e a reação do Instagram nessa escala não foi medida.
- **A etapa de publicações teve ganho pequeno na amostra real**: em 25 perfis, recuperou 1 empresa (`@maggiotraslados`,
  repatriação funerária, identificada pelo contexto de uma publicação) e levou 1 caso para revisão. As regras de oferta
  de serviço impedem que páginas temáticas virem empresa, mas o volume de acertos ainda é baixo. Ela fica ligada porque
  é barata (só duvidosos) e o pacote de revisão aproveita as legendas.
- Destaques: 24 leituras na prova real, nenhuma mudou resultado. Por isso só são lidos para duvidosos.
- No modo `candidatos`, profissionais autônomos com nome de pessoa e sem pista no @ não são lidos (4 de 205 no
  gabarito). Use `-d todos` quando isso importar.
- Falso positivo conhecido: criadores de conteúdo do tema cuja bio não diz que são criadores (ex.: perfil sobre
  tanatopraxia). O pacote de revisão serve para isso.
- Os endpoints e os `doc_id` do site mudam sem aviso. Variáveis de ajuste: `PROSPECCAO_DOC_ID_PERFIL`,
  `PROSPECCAO_DOC_ID_POSTS` e `PROSPECCAO_QUERY_HASH_DESTAQUES`.

## 8. Testes

```powershell
.\.venv\Scripts\python -m pytest -q
```

Os testes usam só dados fictícios (`teste_*`) e um Instagram simulado. Nenhum teste automatizado acessa a internet.
Detalhes e provas reais em [TESTES.md](TESTES.md).
