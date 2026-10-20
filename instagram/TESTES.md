# Relatório de testes

Versão 2 (triagem em etapas, publicações, execução em fases, modo noite, pacote de revisão): 19–20/10/2026.
Versão 1 (coleta e classificação básicas): 19/10/2026, resumida no fim.

## Ambiente

Windows 11 Pro · Python 3.14.3 (`.venv` do módulo) · httpx 0.28.1 · pytest 9.1.1.

## 1. Testes automatizados (dados simulados)

`.\.venv\Scripts\python -m pytest -q` → **164 testes passando** (95 na versão 1). O `pyflakes` não aponta nada.

Todos usam perfis fictícios (`teste_*`) e um Instagram simulado (`httpx.MockTransport`) ou um cliente falso. Nenhum
acessa a internet.

| Área | O que é verificado |
|---|---|
| Arrobas e normalização | Formatos aceitos e rejeitados; letras estilizadas; campos ausentes |
| 13 categorias | Um perfil típico de cada uma (A a M) |
| Mais de uma categoria | Funerária com plano e crematório pet → F, G, E; floricultura e placas; cemitério e planos |
| Nomes genéricos | `@grupoxyz` (só as publicações dizem o que é) → identificado com a ressalva "evidência só nas publicações" |
| Só nas publicações | Termo numa única publicação = indício; repetido ou **fixado** = evidência; local do próprio perfil vale, local visitado não; destaques contam |
| Termos ambíguos | Hashtags `#pet #flores #luto` numa padaria; página de lendas que fala de cemitério sem oferecer serviço ("relatos reais", "neste plano", "plantão" do próprio nome); "traslado" de aeroporto × traslado funerário; @ citados em legendas |
| Não confirmar como empresa | Pessoa física do setor (casado(a), 💍, papai, "homem de fé", "curto anime", estudante, "cursando"); criador de conteúdo; religião pessoal ("Católica"); "santuários" de decoração; menção a @ de funerária; perfil privado; psicólogo sem luto |
| Sem informação / ausente | Bio vazia; publicações com legenda `None`; perfil sem publicações; publicações inacessíveis (não param nem se repetem na retomada) |
| Vocabulário novo | Sepelios, ataúdes, urnas, cementerio, cremation, burial, arte tumular, memorial por QR, placas personalizadas, equipamentos funerários, repatriação, indústria de coroas |
| Fornecedor do setor | Identificado com a ressalva "atua para o setor"; "62 anos no setor funerário" não é fornecedor |
| Triagem | As 6 prioridades; nome de pessoa não é descartado, só ordenado; modos; `triagem.json` configurável e inválido |
| Fases e lotes | Lista → perfis por prioridade → publicações; duplicidade entre páginas; ordem de leitura por prioridade |
| Recuperação e retomada | Pausa na fase de lista (retoma da página) e na de perfis (não relê lista nem perfis); limite e retomada com limite maior; pedido de parada; linhas truncadas em `seguidores.jsonl` e `perfis.jsonl`; falha de um perfil não para a análise; migração de análise antiga sem `seguidores.jsonl` |
| Rede e limites | 429 → espera → nova tentativa; esgotado → pausa; desafio/checkpoint/`feedback_required` → para; sessão expirada; queda de rede com novas tentativas; HTTP 503 → recuperação; cookie renovado em outro domínio; erro parcial do GraphQL de publicações (foto do local) é ignorado |
| Modo noite | Espera e continua sozinho; esgota as esperas e pausa; **verificação de segurança nunca é aguardada** |
| Pacote de revisão | Campos exigidos (bio, categoria IG, dados comerciais, publicações, hashtags, categorias consideradas, motivo, evidências contra, link, estado); decisões em lote (corrigir, descartar, pular, erro por item); classificação automática preservada; divergências; estado "revisado" |
| Exportação | CSV com BOM e `;`, uma linha por categoria, colunas Etapas/Fontes/Prioridade; Markdown |
| Painel | Fases, tempo, "sem informação", filtros por categoria/confiança, pacote, proteção contra caminho fora da pasta, CSRF e Host |

## 2. Investigação real das publicações (sessão da conta secundária)

| Teste | Resultado |
|---|---|
| GraphQL `PolarisProfilePostsQuery` (doc_id do Instaloader 4.15.4) | **Funciona**: 12 posts com legenda, `taken_at`, `code`. Vem com erro parcial em `location.profile_pic_url`, sem efeito nos dados |
| Post fixado | Identificável pelo campo `timeline_pinned_user_ids` (3 fixados em @placasplacarte) |
| Local do post | `location.name` (ex.: "Marmoraria Placarte Marmores e Granitos") |
| Destaques (consulta `query_hash` legada) | **Funciona**: títulos do perfil oficial do Instagram; lista vazia para quem não tem destaques |
| REST `/api/v1/feed/user/<id>/` e `/highlights/<id>/highlights_tray/` | HTTP 302 (não usados) |

## 3. Medição offline no gabarito real de 1.000 seguidores

A análise `2026-10-19_111019_feirafunerariabrasil`, rodada pelo usuário no modo `todos`, leu a bio de todos os 694
perfis públicos. Ela serviu de gabarito. As regras novas foram aplicadas **em memória**, sem alterar os arquivos.

| Medida | Regras e triagem antigas | Novas |
|---|---|---|
| Bios que o modo `candidatos` leria | 167 | 538 |
| Identificados (com bio lida) | 189 | 205 |
| Identificados que o modo `candidatos` deixaria de fora | **59 (31%)** | **4 (2%)**, todos com nome de pessoa |
| Novos identificados | — | 36 |
| Saíram de "identificado" para revisão | — | 20 |
| Perfis que iriam para a etapa de publicações | — | 159 (16%) |

- **Os 36 novos, revisados manualmente:** 32 são empresas ou profissionais reais do setor. Exemplos: fábricas de
  urnas e ataúdes, funerárias em espanhol, italiano e holandês, repatriação, arte tumular, memorial por QR code e
  cerimonialistas. 4 são duvidosos: um podcast sobre a morte, um arquivo digital de jazigos, um professor de
  tanatopraxia e um agente funerário pessoa física.
- **Os 20 que saíram, revisados:** pessoas físicas do setor ("casado com…", "papai", "homem de fé", estudante),
  criadores de conteúdo, religião pessoal e perfis classificados por @ de outra conta.
  - 17 vão para a fila de revisão.
  - 3 ficam sem correspondência: 2 perfis pessoais (correto) e `@memorias.redentora`, cuja única pista era a menção a
    `@funeraria.redentora`. Como é conta comercial sem categoria, numa execução real ele passaria pela etapa de
    publicações.

## 4. Prova real da versão 2 — @feirafunerariabrasil, 150 seguidores

Análise `2026-10-19_183724_poc-v2-feira150`: modo `candidatos`, publicações `duvidosos`, limite de 150.

| Medida | Valor |
|---|---|
| Páginas da lista | 6 |
| Seguidores obtidos e analisados | 150 (149 também estão no gabarito de 1.000) |
| Bios lidas | 101 (o modo `todos` leu 124 desses mesmos perfis) |
| Não lidos pela triagem | 49 (25 privados, 24 com nome de pessoa) |
| Etapa de publicações | 25 perfis, 25 leituras de publicações, 24 de destaques, 0 falhas |
| Tempo | 18 min (1.081 s) |
| Limites do Instagram, verificações, quedas | **Nenhum** |
| Identificados na execução | 52 (o gabarito tinha 47 nesses perfis) |
| Identificados depois das correções desta rodada (reclassificado offline) | 51 · revisar 11 |

**Etapa de publicações, resultado real:**

- Na execução, 2 perfis mudaram. `@assustadosdeplantao` (página de lendas urbanas) virou A e C por legendas sobre
  cemitérios: **falso positivo**, corrigido com a regra "só publicações exige oferta de serviço". `@luzcameraevida` foi
  para revisão.
- Depois das correções, as legendas já coletadas recuperaram `@maggiotraslados` (bio vazia; uma publicação fala de
  repatriação funerária).
- Saldo: **1 empresa a mais e 0 falsos positivos nesta amostra.** O ganho é pequeno.
- Destaques: 24 leituras, nenhuma mudou um resultado. Por isso o padrão passou a ser ler destaques só para os
  duvidosos.

**Revisão manual dos 52 identificados da execução:**

- **47 corretos.**
- **3 relevantes com categoria ou anotação imprecisa** (indústria de coroas como F, curso de florista fúnebre como D,
  funerária marcada como fornecedor). Os três foram corrigidos.
- **2 falsos positivos**: criadores de conteúdo sobre tanatopraxia. Um foi corrigido com a detecção de "criador de
  conteúdo"; o outro não tem sinal na bio e continua.
- **Precisão na amostra revisada: 50 de 52 (96%)** são parceiros potenciais reais; 47 de 52 (90%) com a categoria
  exata.

Cada falha encontrada virou um teste de regressão com dado fictício equivalente.

## 5. O que está comprovado, simulado ou limitado

| Situação | Itens |
|---|---|
| Comprovado em uso real | Coleta paginada; leitura de bio/categoria; publicações (fixados, legendas, hashtags, local); destaques; triagem por prioridade; execução em fases; limite; tempo e eventos na interface; pacote de revisão gerado; reclassificação offline; compatibilidade com análises antigas |
| Medido offline em dados reais | Cobertura da triagem (31% → 2% de perdas) e efeito das regras no gabarito de 1.000 |
| Só com dados simulados | 429 persistente, modo noite esperando e retomando, checkpoint/desafio, sessão expirada, queda de rede, lista limitada pelo Instagram, retomada de uma análise antiga com migração (nada disso ocorreu nas provas reais), aplicação de decisões de revisão |
| Limitado por fatores externos | Exige sessão logada. Escala acima de 1.000 seguidores não testada. Endpoints e `doc_id` podem mudar |

---

## Histórico — versão 1 (19/10/2026)

- **Investigação:** sem login, tudo devolve 429 ou páginas vazias. Com login, `friendships/<id>/followers/` e o
  GraphQL de perfil funcionam. @feirafuneraria não existe; o perfil correto é @feirafunerariabrasil.
- **Prova real:** 300 seguidores, 77 bios lidas, 65 identificados, cerca de 10 min, sem bloqueios.
- **Análise de 1.000 rodada pelo usuário** (modo `todos`): 694 bios, 87 min, sem bloqueios. É o gabarito da versão 2.
- **Bugs corrigidos na v1:** conflito de cookie `csrftoken`; linha truncada corrompia o registro seguinte.
