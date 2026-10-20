---
name: executar-tarefa
description: Executa o trabalho pendente da plataforma de prospecção RIP Memorial — pega os perfis do Instagram que estão na fila esperando os dados da empresa (CNPJ, telefone, endereço, site), roda a pesquisa, revisa com fonte o que ficou incerto e grava tudo no banco da plataforma. Use quando o usuário pedir para executar a tarefa, rodar os pendentes, processar a fila, buscar os dados das empresas dos perfis analisados, ou simplesmente disser /executar-tarefa.
argument-hint: "[quantos itens, ou segmentos A-M, ou vazio para o padrão]"
allowed-tools: Bash(.venv/Scripts/plataforma.exe:*) Bash(.venv/Scripts/empresas.exe:*) WebSearch WebFetch Read
---

# Executar a tarefa pendente

Você está no projeto de prospecção do RIP Memorial. O trabalho se divide em duas metades:

| Metade | Quem faz | O que descobre |
|---|---|---|
| Análise do Instagram | o usuário, pela interface (http://127.0.0.1:8770) | **quem** é parceiro em potencial: o @, o nome e o segmento A–M |
| Pesquisa de empresas | **você, com este comando** | **quem é essa empresa**: CNPJ, razão social, telefone, WhatsApp, e-mail, site, endereço |

Entre as duas existe a **fila de pesquisa**. Sua tarefa é esvaziá-la.

Pedido desta chamada (pode estar vazio): $ARGUMENTS

Os comandos abaixo rodam a partir da raiz do projeto. `PLAT` = `.venv/Scripts/plataforma.exe`, `EMP` = `.venv/Scripts/empresas.exe`.

## 1. Ver o que está pendente

```
PLAT fila resumo
```

Devolve `por_estado` (pendente/pesquisando/concluido/dispensado) e `por_segmento`.

- **`pendente` = 0** → não há o que fazer. Diga isso ao usuário, mostre quantos já foram concluídos e pare aqui.
- Se o usuário pediu um número ou segmentos em `$ARGUMENTS`, use. Senão, o padrão é **até 50 itens**.

Para ver quem são, antes de rodar:
```
PLAT fila listar --limite 20
PLAT fila listar --json --limite 20      (saída estruturada)
```

## 2. Pesquisar

```
PLAT fila pesquisar --limite 50
PLAT fila pesquisar --limite 50 --segmentos F,C      (só alguns segmentos)
```

Isso cria uma pesquisa de empresas com os pendentes, marca-os como `pesquisando` e **inicia o processo em segundo plano**. O comando devolve o id da execução (`emp:AAAA-MM-DD_HHMMSS_fila`); guarde o nome da pasta (a parte depois de `emp:`), que é o **lote**.

Leva cerca de **5 a 15 segundos por empresa**, 3 em paralelo. Para acompanhar:
```
EMP status "<lote>"
```
Espere terminar (`status` = `concluido` ou `concluido_com_erros`) antes de seguir. Não fique consultando em intervalos curtos: calcule o tempo esperado (itens × 10 s ÷ 3) e verifique de poucas em poucas vezes.

Se parar no meio: `EMP retomar "<lote>"` continua de onde estava, sem repetir nada.

## 3. Revisar o que ficou incerto — é aqui que você agrega valor

```
EMP revisar "<lote>"
```

Devolve os registros `provavel`, `parcial`, `nao_encontrada`, de confiança `baixa`, com divergências ou com campos importantes não confirmados — junto com os candidatos a CNPJ e as alternativas descartadas.

Revise **no máximo 15 itens**, priorizando `provavel` > `parcial` > confiança baixa. Para cada um:

1. Investigue com WebSearch e WebFetch: site oficial, página de contato, política de privacidade (costuma trazer o CNPJ), o perfil do Instagram, Google Maps.
2. **Só confirme com uma URL que comprove.** Na dúvida, mantenha o dado como não confirmado — não apague um dado só por não estar confirmado. Apague apenas o que tiver evidência de estar errado (homônima de outra cidade, contato de terceiros).
3. Para confirmar um CNPJ, exija: ele aparece no site/perfil oficial; **ou** nome + cidade batem e o e-mail/telefone/endereço do cadastro coincidem com os da empresa.
4. Registre cada achado:

```
EMP corrigir "<lote>" --linha 7 --campo cnpj --confirmar --fonte <url> --nota "CNPJ no rodapé do site oficial"
EMP corrigir "<lote>" --linha 7 --campo cnpj --valor 12.345.678/0001-90 --fonte <url> --nota "..."
EMP corrigir "<lote>" --linha 7 --campo cnpj --remover --nota "CNPJ provável é de homônima em outra cidade"
EMP corrigir "<lote>" --linha 7 --campo telefones --valor "(14) 3222-1234" --fonte <url>
EMP corrigir "<lote>" --linha 7 --campo instagram --confirmar --fonte <url do site que linka o perfil>
```

Campos: `nome_comercial, categoria, razao_social, cnpj, situacao_cadastral, atividade_principal, endereco, bairro, cidade, uf, cep, google_maps, telefones, whatsapp, emails, site, instagram, seguidores_instagram, facebook, linkedin, outros_canais, horario_funcionamento, avaliacao`.

O campo **`categoria` é o segmento A–M**, no formato `"F · Crematórios e funerárias humanas"` — nunca uma categoria comercial genérica. Se precisar corrigi-lo, use esse formato. Empresa que não é de nenhum dos 13 segmentos fica **sem segmento**, e isso está certo.

## 4. Fechar

```
EMP exportar "<lote>"
PLAT sincronizar
PLAT fila resumo
```

A sincronização leva os resultados para o banco da plataforma e tira da fila quem já virou empresa.

Perfis que não são empresa (perfil pessoal, página de notícias, fornecedor de fora do Brasil) devem sair da fila para não voltarem sempre:
```
PLAT fila dispensar @fulano @sicrano --motivo "perfil pessoal, não é empresa"
```

## 5. Responder ao usuário

Um resumo curto, em português, com:

- quantos perfis foram pesquisados e quantos saíram da fila;
- a contagem por resultado (CNPJ confirmado / provável / sem CNPJ / não encontrada);
- o que você revisou e confirmou, com a fonte;
- **o que continua incerto e por quê** — deixando claro o que é não confirmado;
- quantos ainda restam na fila;
- o lembrete de que tudo isso já está em http://127.0.0.1:8770 (aba **Empresas**, com filtro por segmento e região).

## Regras

- Apenas dados públicos e comerciais. Não colete sócios, CPFs nem dados pessoais.
- Não contorne CAPTCHA, login ou bloqueio anti-robô. Registre como não lido.
- Não use APIs pagas nem crie contas.
- **Nunca apresente um dado não confirmado como confirmado**, nem na planilha nem na resposta.
- Divergências (cidade diferente, CNPJ baixado, CEP do site ≠ cadastro) devem ser mantidas e explicadas, não "resolvidas" escolhendo um lado sem fonte.
- Não mexa em outros lotes nem em análises do Instagram.
