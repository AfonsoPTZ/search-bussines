---
name: pesquisa-empresas
description: Pesquisa e enriquece dados públicos de empresas brasileiras (CNPJ, razão social, situação cadastral, categoria, telefones, WhatsApp, e-mails, site, Instagram e seguidores, Facebook, LinkedIn, horário, endereço completo, CEP, Google Maps) a partir de uma lista de perfis do Instagram (@perfil), nomes, sites ou CNPJs, com fontes e nível de confiança, e entrega planilha XLSX/CSV. Use quando o usuário pedir para pesquisar, enriquecer, identificar, levantar contatos ou achar o CNPJ de uma ou várias empresas, ou gerar planilha de empresas/leads.
argument-hint: "[lista de empresas ou caminho de arquivo .txt/.csv/.xlsx]"
allowed-tools: Bash(.venv/Scripts/empresas.exe:*) Read Write
---

# Pesquisa de empresas

Ferramenta local da pasta `pesquisa-empresas/` deste projeto (documentação completa no README.md de lá).
Executável, a partir da raiz do projeto (ferramenta Bash):

```
.venv/Scripts/empresas.exe <comando>
```

Abaixo, `EMP` significa esse executável.

Lista recebida nesta chamada (se houver): $ARGUMENTS

## Fluxo

### 1. Montar a lista
- Uma empresa por linha. Formatos aceitos: `@perfil`, URL do Instagram, site (`www.x.com.br`), CNPJ, nome.
- Pistas extras na mesma linha separadas por ` | `: `Padaria Real | Bauru/SP | @padariareal`. Inclua cidade/UF sempre que o usuário informar — isso evita confundir empresas homônimas.
- No chat, `@algo` normalmente é um perfil do Instagram. Se a menção for um arquivo anexado (.txt/.csv/.xlsx), use o arquivo como lista.
- Grave a lista com Write em `pesquisa-empresas/entradas/<AAAA-MM-DD>_<nome-curto>.txt`.
  Arquivos .csv/.xlsx do usuário podem ser passados direto (colunas reconhecidas: nome, instagram, site, cnpj, cidade, uf).

### 2. Rodar a pesquisa automática
```
EMP pesquisar "<arquivo da lista>" --nome <nome-curto>
```
- Faz busca web (SearXNG local, com contingência via ddgs), lê o site oficial (contato/sobre/privacidade), extrai contatos, horário e CNPJ, valida o CNPJ nas bases abertas da Receita (OpenCNPJ/BrasilAPI/minhareceita/CNPJá), pontua a correspondência, pega seguidores do Instagram pelo trecho do buscador, completa endereço pelo CEP e resolve o **segmento A–M** da empresa (pelo CNAE, pelo tipo declarado no site ou, por último, inferido pelo nome). Empresa fora dos 13 segmentos do RIP Memorial fica **sem segmento** — isso é o esperado, não uma falha.
- **Política do usuário: trazer o máximo de dados, marcando o que não está confirmado.** Por isso, quando não dá para confirmar o CNPJ, a ferramenta já preenche o candidato mais plausível com status `provavel` e marca os valores como "(não confirmado)"; perfis achados só pelo nome na busca e sites que bloquearam a leitura também entram marcados. O que tem evidência contrária (site de homônima de outra cidade) fica na aba Alternativas.
- Leva ~5–15 s por empresa (3 em paralelo; `--workers N` muda isso). Para mais de ~40 empresas, rode em segundo plano e acompanhe com `EMP status`.
- Se for interrompido: `EMP retomar` (continua do ponto em que parou e refaz só as que deram erro).
- Se algo falhar em tudo: `EMP verificar` testa buscadores e APIs.

### 3. Revisar o que ficou incerto (o seu trabalho de verdade)
```
EMP revisar
```
Retorna JSON com os registros `provavel`, `parcial`, `nao_encontrada`, confiança `baixa`, com divergências ou com campos importantes não confirmados (`nao_confirmados`), incluindo os candidatos a CNPJ (`escolhido` = sim/provável) e as `alternativas` rejeitadas.

Para cada item (priorize provavel > parcial > baixa; em lotes grandes revise até ~15 e informe o restante):
1. Investigue com WebSearch e WebFetch (ou o agente web-fetch, se WebFetch não estiver disponível): site oficial, página de contato/política de privacidade (costuma ter CNPJ), perfil do Instagram, Google Maps.
2. Só **confirme** algo com uma URL que comprove. Na dúvida, mantenha o dado como não confirmado — não apague dado só por não estar confirmado (o usuário prefere o dado marcado a perder o dado). Apague apenas o que tiver evidência de estar errado (homônima de outra cidade, contato de terceiros).
3. Para confirmar um CNPJ exija pelo menos uma destas evidências: aparece no site/perfil oficial; ou nome + cidade batem e o e-mail/telefone/endereço do cadastro coincide com o da empresa.
4. Registre com `corrigir` (cada chamada atualiza o registro, recalcula status/confiança e regenera as planilhas):
```
EMP corrigir --linha 7 --campo cnpj --confirmar --fonte <url> --nota "CNPJ provável confirmado no rodapé do site"
EMP corrigir --linha 7 --campo cnpj --valor 12.345.678/0001-90 --fonte <url> --confianca media --nota "CNPJ no rodapé do site oficial"
EMP corrigir --linha 7 --campo cnpj --valor 12.345.678/0001-90 --fonte <url> --nao-confirmado --nota "melhor candidato, sem prova"
EMP corrigir --linha 7 --campo cnpj --remover --nota "CNPJ provável é de homônima em outra cidade"
EMP corrigir --linha 7 --campo instagram --confirmar --fonte <url do site que linka o perfil>
EMP corrigir --linha 7 --campo telefones --valor "(14) 3222-1234" --fonte <url>
EMP corrigir --linha 7 --campo site --valor https://www.exemplo.com.br --fonte <url> --substituir
EMP corrigir --linha 7 --campo instagram --valor https://www.instagram.com/x/ --remover --nota "perfil de homônima"
EMP corrigir --linha 7 --campo avaliacao --valor "4,6 no Google (1.200 avaliações)" --fonte <url>
```
Campos: nome_comercial, categoria (= o **segmento A–M**, no formato `"F · Crematórios e funerárias humanas"`), razao_social, cnpj, situacao_cadastral, atividade_principal, endereco, bairro, cidade, uf, cep, google_maps, telefones, whatsapp, emails, site, instagram, seguidores_instagram, facebook, linkedin, outros_canais, horario_funcionamento, avaliacao. Ao corrigir `cnpj`, os dados cadastrais são buscados de novo automaticamente (e herdam confirmado/não confirmado).
`--confirmar` promove valores já encontrados (todos do campo, ou só o `--valor`) a confirmados; `--nao-confirmado` registra um valor novo marcado como não confirmado.
Avaliações (nota do Google etc.) não são coletadas automaticamente; só busque e registre se o usuário pedir.
`outros_canais` é só para canais de contato da empresa (YouTube, TikTok, iFood, linktree...). Contexto e fontes que não são canais (notícias, recuperação judicial, motivo de uma escolha) vão em `--nota`, junto com a URL.
Remova contatos que não são da empresa (e-mail do web designer/agência, telefone de parceiro) com `--remover`.

### 4. Entregar
- `EMP exportar` (se não tiver corrigido nada depois da última exportação, não precisa).
- Responda com: resumo (quantas identificadas/prováveis/parciais/não encontradas), uma tabela curta (entrada, nome, segmento, CNPJ, cidade/UF, telefone ou WhatsApp, status/confiança) deixando claro na tabela o que é **não confirmado**, o que ainda precisa de atenção e por quê, e os caminhos de `empresas.xlsx` e `empresas.csv` (pasta `resultados/<lote>/`). Na planilha, não confirmados aparecem com "(não confirmado)", célula laranja e na coluna "Campos não confirmados".

- Os resultados também aparecem na plataforma unificada (http://127.0.0.1:8770, `Abrir plataforma.cmd` na pasta `Nova pasta (2)`), com filtros por região/segmento e vínculo com os perfis do Instagram. Mencione isso ao entregar.

## Regras
- Apenas dados públicos e comerciais. Não colete sócios, CPFs nem dados pessoais; para MEI/empresário individual o telefone/e-mail do cadastro pode ser pessoal (a planilha avisa).
- Não contorne CAPTCHA, login ou bloqueio anti-robô (Cloudflare etc.). Registre como não lido.
- Não use APIs pagas nem crie contas. Tudo aqui é gratuito.
- Divergências (cidade diferente, CNPJ baixado, CEP do site ≠ cadastro) devem ser mantidas e explicadas, não "resolvidas" escolhendo um lado sem fonte.
- Nunca apresente um dado não confirmado como confirmado (na resposta e na planilha).
