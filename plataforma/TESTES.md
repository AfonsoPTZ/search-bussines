# Relatório de testes da plataforma (20/10/2026)

Ambiente: Windows 11 Pro · Python 3.14.3 (`.venv` na raiz, com os três pacotes) · Edge headless para a interface ·
Claude Code 2.1.304 (extensão do VS Code).

## 1. Automatizados (sem internet)

| Suíte | Resultado |
|---|---|
| `plataforma` | **58 passando** |
| `pesquisa-empresas` | **28 passando** (eram 21; os 7 novos cobrem o lote: batimento, parada segura, erros, trava e gravação) |
| `instagram` | **165 passando** (eram 164; o novo cobre a trava de processo único) |

As suítes antigas também passam nos `.venv` originais de cada módulo. Todos os testes usam dados fictícios (`teste_*`)
no formato real: os registros são montados com `empresas.pesquisa.Registro` e os perfis classificados com
`prospeccao.classificar`.

**O que a suíte da plataforma cobre:**

- **Mesma empresa:** CNPJ confirmado em lotes diferentes, mesmo @ e mesma entrada viram uma empresa. Nome igual só
  vira sugestão (e só na mesma UF). CNPJs de raízes diferentes não unem, matriz e filial sim, e CNPJ não confirmado
  não une. Mesma entrada com site confirmado diferente não une. Hospedagem compartilhada (wixsite, negocio.site) não
  vira chave. Registros antigos sem confirmação e pesquisas ambíguas não geram chave forte.
- **Decisões manuais:** unir e separar persistem depois de reimportar. "Diferentes" não volta como sugestão. Rejeição
  de vínculo sobrevive à sincronização e a uma união. Uma pasta movida e devolvida reencontra uniões e vínculos.
  Uma correção que remove o @ desfaz a união automática, mas nunca a manual.
- **Vínculos e segmentos:** vínculo confirmado pela entrada ou pelo site oficial, sugerido pela busca ou pelo link da
  bio. Segmento vem do perfil vinculado; o inferido fica separado (razão social com "Catedral" não vira igreja;
  funerária pet com perfil E não ganha F).
- **Estados:**
  - Instagram: concluída, parcial (limite ou lista limitada pelo Instagram), em andamento, parada sem batimento,
    pausada e precisa de ação.
  - Empresas: concluída, com falhas, parada e em andamento.
  - Pasta apagada sai da base. Raiz indisponível não apaga nada. Execução criada durante a sincronia não é apagada.
    Arquivar esconde e restaurar devolve.
- **Filtros:** cada filtro sozinho e combinados, incluindo cidade com e sem acento, CNPJ só com dígitos e @. Também:
  segmento por origem, ordenação, paginação, resultado vazio e entradas maliciosas no ordenar e no texto.
- **Ações:** prévia e criação da pesquisa a partir da análise, com pulo das já pesquisadas, linha
  `Nome | @ | Cidade/UF` e ligação com a análise de origem. Também: validação da nova pesquisa, "pesquisar
  novamente", retomar e parar conforme o estado, e duplo "retomar" iniciando um só processo.
- **Servidor HTTP real:**
  - rotas;
  - bloqueio de Host estranho (403), de Origin de outro site (403) e de formulário (415);
  - downloads só da lista permitida, com caminhos `..`/`C:`/espaço final recusados;
  - exportação com filtros e "(não confirmado)";
  - nenhuma fórmula na planilha.
- **Revisão pelo Claude** (processo simulado com o mesmo formato `stream-json`): pedido restrito (prefixo exato),
  andamento, resumo e falha sem resultado.

## 2. Interface (Edge headless, dados reais, banco de teste)

- Todas as rotas abrem sem exceção JS, a 1440 px e a 390 px (sem rolagem horizontal).
- Revisão independente da interface (agente revisor) encontrou 15 problemas. Os relevantes foram corrigidos e
  conferidos com os scripts de reprodução dele:

  | Problema | Antes da correção |
  |---|---|
  | Esc num diálogo | Confirmava a ação anterior |
  | Navegação rápida | Página lenta sobrescrevia a seguinte |
  | Busca com debounce | Vazava entre páginas |
  | Polling | Roubava o foco |
  | "Voltar" com página aberta direto | Saía da aplicação |
  | Contadores de pendência | Inflados |
  | Links | Sem acesso por teclado |
  | Página Sistema | Lenta (2,3 s; agora ≈50 ms) |

## 3. Integração real (ambiente isolado no scratchpad; nenhum arquivo das pastas reais foi tocado)

| Teste | Resultado |
|---|---|
| Sincronizar a base real (3 análises, 14 lotes) | 0,9 s. **113 pesquisas viraram 43 empresas** (uma por entrada distinta), sem união indevida. Rodar de novo não muda nada |
| Pesquisar as empresas do segmento E da análise de 150 seguidores | 2 empresas pesquisadas de verdade (≈1 min), vinculadas aos perfis, com segmento E vindo do perfil. Pedir de novo pula as 2 ("já pesquisada") |
| Análise do Instagram disparada pela plataforma (lista de @, modo sem rede) | Concluída e **completa** |
| Parar um lote real de 8 empresas no meio | As 3 em andamento terminaram e foram gravadas (4 no total), 4 ficaram pendentes, estado "interrompida" |
| Retomar | "4 já concluídas, 4 pendentes"; terminou com exatamente 8 registros |
| Revisão em segundo plano pelo Claude Code (1 item, 2 vezes) | Rodou `empresas revisar`, buscou na web, **não confirmou nada sem prova** e explicou o porquê. Com as regras de prefixo exato, nenhuma negação indevida |
| Comando disfarçado (`python -c … # empresas.exe`) | **Negado** pelo Claude Code (testado com Haiku) |

## 4. Não testado / depende de configuração externa

- **Análise real do Instagram com sessão** (coleta de seguidores na rede): não rodada, para não gastar requisições da
  conta secundária. O caminho é o mesmo da CLI (`prospeccao executar`), que já tem testes e provas reais. A plataforma
  só dispara o processo, como foi verificado no modo sem rede.
- **SearXNG:** o Docker estava desligado, então as pesquisas reais usaram a contingência `ddgs`.
- **Escala acima de ~1.000 perfis por análise:** não medida.
