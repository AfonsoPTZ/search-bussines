# Relatório de testes — 18/10/2026

## Ambiente

| Item | Versão ou estado |
|---|---|
| Sistema | Windows 11 |
| Python | 3.14.3 |
| Claude Code | 2.1.301 (extensão do VS Code) |
| Docker | 29.6.2 |
| SearXNG | `latest` |

Saída de `empresas verificar`:

| Componente | Resultado |
|---|---|
| SearXNG local | OK |
| ddgs | OK |
| OpenCNPJ | HTTP 200 |
| BrasilAPI | HTTP 200 |
| minhareceita | HTTP 200 |
| CNPJá | HTTP 200 |

## Testes de unidade

`pytest`: 10 testes passando. Cobrem:

- CNPJ numérico e alfanumérico (exemplo oficial da Receita `12.ABC.345/01DE-35`);
- localização de CNPJ em texto;
- telefones, 0800 e CEP com e sem ponto;
- links tel:, wa.me, mailto, Instagram e Facebook;
- JSON-LD;
- interpretação das entradas;
- similaridade de nomes, inclusive o padrão de loja franqueada.

## Testes reais

Foram 35 empresas reais em 3 lotes. Os arquivos estão em `entradas/`:

| Lote | Formato | Empresas | Tipos de entrada |
|---|---|---|---|
| `teste-real.txt` | txt | 8 | @Instagram, site, nome+cidade, CNPJ, homônima, empresa fictícia |
| `teste-csv.csv` | CSV com colunas | 7 | — |
| `teste-lote20.txt` | txt | 20 | Sem cache. Interrompido à força aos 40 s e retomado |

Os resultados estão em `resultados/*_v3-teste-*`.

### Resultado consolidado (antes da revisão pelo Claude)

| Status | Empresas | | Confiança | Empresas |
|---|---|---|---|---|
| identificada | 24 | | alta | 17 |
| ambígua | 9 | | média | 7 |
| não encontrada | 2 | | baixa | 11 |

Preenchimento dos campos:

| Campo | Preenchido | | Campo | Preenchido |
|---|---|---|---|---|
| site | 30/35 | | e-mails | 18/35 |
| endereço | 26/35 | | telefones | 16/35 |
| CEP | 25/35 | | WhatsApp | 11/35 |
| CNPJ | 24/35 | | Instagram | 23/35 |

Tempo: cerca de 4–6 s por empresa sem cache, com 3 em paralelo. Os 12 itens restantes do lote de 20 levaram 51 s.

### Conferência manual (amostra)

**CNPJs identificados.** Batem com a entidade publicamente conhecida e quase todos vieram do próprio site ou de evidências cruzadas:

| Empresa | Entidade identificada | Observação |
|---|---|---|
| Havan | Havan S.A. | Matriz em Brusque |
| Petrobras | — | CNPJ informado na lista |
| Tok&Stok | Estok Comércio e Representações | CNPJ no site |
| Mocotó | — | Unidade cujo endereço o site publica |
| Confeitaria Colombo | — | CNPJ no site |
| Bacio di Latte | Milano Comércio Varejista | — |
| Bob's | CFK Comércio de Alimentos | Único CNPJ no site oficial |
| Drogaria Araujo | Drogaria Araujo S/A | — |
| Zaffari | Cia Zaffari | — |
| Hering | Cia Hering | — |
| Bauducco | Pandurata Alimentos | — |
| Riachuelo | Lojas Riachuelo S/A | — |
| Renner | Lojas Renner S/A | — |
| Bella Paulista | — | Filial da Rua Haddock Lobo, endereço que o site publica |
| Cacau Show | — | Matriz ativa da raiz publicada em `terms.html` |

**Casos difíceis tratados corretamente:**

| Empresa | O que a ferramenta fez |
|---|---|
| Padaria Real \| Bauru/SP | O site encontrado é de uma homônima de Sorocaba; foi descartado e o caso marcado como ambíguo. A revisão web confirmou que não há Padaria Real conhecida em Bauru |
| Comercial Zzqxw Fictícia | Não encontrada |
| Pastelaria Viçosa \| São Paulo/SP | Só existem homônimas em Brasília; a observação sugere conferir a cidade |
| Kopenhagen, Giraffas, Boticário, Casa do Pão de Queijo, Spoleto, Brasil Cacau, Armazém do Campo | Marcas com dezenas de CNPJs de franqueados ou homônimos; ficaram ambíguas em vez de escolher um franqueado qualquer |
| Livraria da Vila | O site bloqueia robôs (Cloudflare). O bloqueio não foi contornado, e o CNPJ foi identificado por outras evidências |

### Robustez

- **Interrupção forçada:** o processo foi encerrado no meio de um lote de 20. `retomar` continuou das 8 já gravadas e não perdeu nada.
- **Erros isolados:** uma falha numa empresa não interrompe o lote (verificado com um bug real durante o desenvolvimento). `retomar` refaz só os registros com erro.
- **Painel:**
  - listagem, detalhe e download do XLSX funcionando;
  - formulário dispara a pesquisa;
  - acesso a arquivos fora da pasta de resultados é bloqueado (HTTP 404).
- **Fluxo pelo Claude Code:**
  - a skill foi carregada na sessão sem reiniciar;
  - `revisar` → WebSearch/WebFetch → `corrigir` funcionou com status, adição e remoção de valor;
  - o histórico ficou registrado em `correcoes.jsonl`.

### Teste de sessão nova (sem contexto)

**Pedido:** um agente novo, sem nenhuma informação sobre a ferramenta, recebeu apenas o pedido em linguagem natural ("Pesquise estas empresas... @lojasleader / Cantina Roperto | São Paulo/SP").

**O que ele fez:**

- carregou a skill `pesquisa-empresas` sozinho;
- rodou `pesquisar`, `revisar`, `corrigir` e `exportar`;
- revisou os casos com WebSearch/WebFetch;
- entregou a planilha em `resultados/*_leader-roperto/` com fontes.

**Resultado:**

| Empresa | Status / confiança | CNPJ | Observação |
|---|---|---|---|
| Cantina Roperto | identificada / alta | 37.421.154/0001-67 (Empório Roperto) | Confirmado pelo rodapé do site |
| Leader | identificada / média | 30.094.114/0001-09 | Registrou a recuperação judicial e o fechamento da rede, com fontes |

## Bugs encontrados nos testes e corrigidos

1. **Contatos de empresa homônima de outra cidade.** Um site homônimo (outra cidade) tinha os contatos associados à empresa errada. Agora há verificação de cidade com descarte do site.
2. **Título genérico como nome.** O título "Home" foi usado como nome da empresa, e o CNPJ escolhido foi o de um hospital chamado HOME. Agora títulos genéricos são ignorados e há checagem de compatibilidade com o domínio.
3. **Loja franqueada no lugar da marca.** Uma franqueada ("Kopenhagen Mario Ferraz") foi tomada pela marca. Agora a similaridade penaliza nome com palavras a mais, há penalidade de franquia e a confiança fica limitada a "média" quando existem homônimas ativas.
4. **Diretório como site oficial.** Um diretório de empresas foi aceito como site oficial pelo título. Agora o título só vale em página inicial e há uma lista de diretórios conhecidos.
5. **Cookie malformado.** Um cookie malformado de um site quebrava as requisições seguintes da mesma thread. Agora os cookies são limpos a cada requisição e esse erro é tratado.
6. **Escolha arbitrária de filial ou matriz.** Filial e matriz eram escolhidas por ordem arbitrária. Agora a matriz é preferida, a não ser que haja evidência de uma unidade única.
7. **E-mail do web designer.** O e-mail do criador do site (crédito "Website design by...") era captado como contato da empresa. Agora esse tipo de crédito é filtrado. Foi apontado pelo teste de sessão nova.
8. **Pequenos ajustes.** Entidades HTML no nome, UF por extenso no JSON-LD, CEP com ponto, subdomínio em vez do domínio principal, e Facebook ou LinkedIn de parceiros.

---

# Melhorias de 19/10/2026: dados não confirmados e campos novos

## O que foi testado

**Testes de unidade:** 19 passando (eram 10). Os novos cobrem:

- seguidores ("964K Followers", "714 mil seguidores", "1,2 mi");
- horário em texto e em JSON-LD;
- avaliação em JSON-LD;
- categorias (CNAE, schema.org, palavras-chave);
- prioridade de valor confirmado;
- exibição "(não confirmado)" e status `provavel`;
- confirmação posterior por revisão;
- endereço completo;
- compatibilidade com lotes antigos sem a flag.

**Viabilidade, medida antes de implementar:**

| Dado | Medição | Decisão |
|---|---|---|
| Horário em JSON-LD | 0 de 156 páginas | Usar texto |
| Horário em texto | 29 de 156 páginas | Implementado |
| Seguidores nos trechos de busca | 70 de 188 resultados de perfil | Implementado |
| Avaliação no próprio site | 0 de 156 páginas | Só JSON-LD + revisão |
| Avaliação por busca dedicada | 1 de 8 empresas, com notas conflitantes | Não implementado |
| Coordenadas via CEP | CEPs diferentes voltam com o centro da cidade | Não implementado |

## Comparação real: 35 empresas, mesmas listas de 18/10

Lotes "antes" em `resultados/*v3-teste-*`; lotes "depois" (versão final) em `resultados/*v7-teste-*`.

| Campo | Antes | Depois | Dos quais não confirmados |
|---|---|---|---|
| CNPJ | 24 | 34 | 10 |
| Categoria | 0 | 34 | 13 |
| Endereço completo | 26 | 34 | 10 |
| Seguidores do Instagram | 0 | 20 | 0 |
| Horário | 0 | 9 | 0 |

**O que mudou e o que não mudou:**

- **Regressão:** nenhum CNPJ confirmado mudou.
- **Ex-"ambíguas":** as 9 viraram `provavel`, com o motivo nas Observações. Exemplos:
  - Pastelaria Viçosa: "fica em Brasília/DF, não na cidade informada";
  - Giraffas: "pontuação próxima de G Lapa Comércio... (SP)".
- **Empresa fictícia:** continua `nao_encontrada`. Candidatos sem nome parecido não são preenchidos.

## Problemas encontrados na conferência e corrigidos

1. **CNPJ baixado como "provável".** Na Pizzaria Bráz, o CNPJ provável era de uma empresa baixada em 1989. Agora candidatos ativos têm preferência.
2. **Categoria genérica.** Com CNAE genérico, a categoria ficava "Serviços administrativos" (Sorvetes Rochinha), "Comércio atacadista" (Chilli Beans) ou "Gestão de marca" (Coco Bambu). Agora usa a categoria inferida pelo nome/site, marcada como não confirmada: Sorveteria, Ótica, Restaurante.
3. **Duplicata contada como não confirmada.** Um valor confirmado na revisão continuava listado como "não confirmado" quando existia uma cópia não confirmada dele.
4. **Mapa de CNAE incompleto.** Faltavam entradas para doces/bombons, gestão de ativos intangíveis e plano de auxílio-funeral.

## Fluxo de revisão (cópia descartável de um lote)

Sequência de `corrigir` executada e status resultante:

| Passo | Comando | Status resultante |
|---|---|---|
| 1 | `--campo cnpj --remover` | `nao_encontrada` |
| 2 | telefone com `--nao-confirmado` | `parcial` (baixa) |
| 3 | `--confirmar` com fonte | `parcial` (média) |
| 4 | CNPJ com `--nao-confirmado` | `provavel` |
| 5 | `--campo cnpj --confirmar` | `identificada` |

## Planilha e interface

**Planilha:**

- valores não confirmados com sufixo "(não confirmado)", célula laranja e itálico (inclusive links);
- coluna "Campos não confirmados";
- aba Fontes com a coluna "Confirmado";
- aba Alternativas com "Escolhido?" (sim / provável) e os sites rejeitados;
- seguidores gravados como número.

**Painel:** colunas Categoria, Seguidores, Horário, Endereço e Mapa; células não confirmadas destacadas; selo `provavel`.

## Teste de sessão nova (agente sem contexto)

**Pedido:** "traga o máximo de dados públicos e gere a planilha" para:

- Crematório Vaticano | Curitiba/PR
- Cemitério Parque Iguaçu | Curitiba/PR
- Floricultura Vida Nova | Curitiba/PR
- @prever

**O que o agente fez:** carregou a skill sozinho, rodou `pesquisar`, `revisar`, `corrigir` (com `--confirmar`) e `exportar`, e separou confirmado de não confirmado na resposta. Lote em `resultados/*_funerarias-curitiba`.

**Falhas da pesquisa automática:** a revisão dele mostrou 3 falhas, todas corrigidas no código e validadas de novo (lotes `resultados/*v7-*`):

1. **Portal do segmento aceito como site oficial.** O site do Cemitério Parque Iguaçu virou `cemiterio.net.br`.
   - Correção: o domínio precisa conter um termo distintivo do nome, não só a palavra do segmento (cemitério, padaria, floricultura...).
   - Efeito extra: a Padaria Benjamin Abrahão trocou `padaria.net.br` (errado) por `benjaminpadaria.com.br` (correto).
2. **Homônima de outra cidade entrou como confirmada.** Para a Floricultura Vida Nova de Curitiba vieram os dados de uma loja de Blumenau.
   - Correção: os CEPs do site agora são consultados como evidência de cidade. O site de Blumenau (CEP 89030-000) foi rejeitado automaticamente e foi para a aba Alternativas.
   - Correção: um site que não cita a cidade informada entra como não confirmado, a não ser que publique um CNPJ da própria marca (site de rede).
3. **Site de outra empresa associado ao perfil.** O @prever, perfil sem nome público, foi ligado a `sistemaprever.com.br`, que linka outro Instagram.
   - Correção: um site que linka outro Instagram, ou que foi achado só pelo @ sem linkar o perfil, entra como não confirmado. A exceção é o domínio idêntico ao @ (ex.: @giraffas e giraffas.com.br).

**Ajuste adicional:** um CNPJ provável cuja atividade não combina com o segmento do nome ganha um aviso. Exemplo: "a atividade do CNPJ (Serviços financeiros auxiliares) não parece de floricultura". É um aviso, não uma exclusão, porque há casos legítimos: o Parque Iguaçu é registrado como administração de imóveis.

**Regressão:** depois das correções, nenhum CNPJ confirmado mudou nas 37 empresas das listas anteriores.

Testes de unidade: 21 passando.
