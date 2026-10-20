---
name: prospeccao-instagram
description: Prospecção de parceiros do RIP Memorial entre os SEGUIDORES de um perfil do Instagram (funerárias, cemitérios, crematórios, pet, floriculturas, placas/lápides, seguros e planos funerários, igrejas, hospitais/paliativos, luto) e revisão inteligente dos casos duvidosos. Use quando o usuário pedir para analisar/prospectar os seguidores de um @, iniciar ou retomar uma análise (inclusive à noite), ver o andamento, revisar o pacote de revisão, corrigir classificações ou gerar a lista final de potenciais parceiros por categoria. NÃO use para achar CNPJ/contatos de empresas (isso é a skill pesquisa-empresas).
argument-hint: "[@perfil de origem | nome da análise]"
allowed-tools: Bash(.venv/Scripts/prospeccao.exe:*) Read Write
---

# Prospecção pelo Instagram

Ferramenta local da pasta `instagram/` deste projeto (documentação: README.md e TESTES.md de lá).
Executável, a partir da raiz do projeto (ferramenta Bash):

```
.venv/Scripts/prospeccao.exe <comando>
```

Abaixo, `PRO` significa esse executável. Pedido desta chamada (se houver): $ARGUMENTS

## Regras que não mudam
- A coleta usa a sessão de uma conta secundária do usuário (importada do Firefox). Nunca peça senha, nunca imprima cookies.
- Nunca contorne bloqueios: em verificação de segurança/checkpoint, oriente o usuário a resolver no Firefox, rodar `PRO sessao firefox` e retomar.
- Não rode análise de milhares de seguidores sem o usuário pedir. Se pedir "à noite", use `--noite` e deixe rodando em segundo plano.
- Nunca invente @, bio ou categoria. Decida só com o que está no pacote (bio, categoria do Instagram, publicações, destaques).

## 1. Iniciar ou retomar
- Nova análise: `PRO analisar @perfil [-l LIMITE] [--noite] [-c A,F,G|todas] [-d candidatos|todos] [-p duvidosos|nenhuma]`
  Para mais de ~200 seguidores, rode em segundo plano (run_in_background) e acompanhe com `PRO status <analise>`.
  Ritmo medido: ~150 seguidores em ~10–15 min no modo padrão; milhares levam horas.
- Retomar (de onde parou, sem repetir): `PRO retomar <analise> [--noite] [-l NOVO_LIMITE]`
- Interface: a plataforma unificada, em http://127.0.0.1:8770 (`Abrir plataforma.cmd` na raiz do projeto).

## 2. Revisar (o seu trabalho)
1. `PRO revisar <analise> --max 40` → JSON com os itens pendentes: bio, categoria do Instagram, dados comerciais, publicações
   (📌 = fixada), hashtags, local, destaques, categorias consideradas com evidências, "motivo_da_duvida" e "evidencias_contra".
   (O mesmo conteúdo legível fica em `resultados/<analise>/revisao/pacote.md`.)
2. Para cada item decida com base nas 13 categorias (A placas/lápides/fotoporcelana · B cemitérios pet · C cemitérios ·
   D floriculturas · E crematórios/funerárias pet · F crematórios/funerárias humanas · G seguro de vida/planos funerários ·
   H clínicas/hospitais vet · I pet shops/serviços pet · J igrejas · K hospitais/paliativos · L apoio ao luto · M psicólogos/terapeutas do luto):
   - `confirmar`/`corrigir` com as categorias corretas (pode ser mais de uma) quando houver evidência no próprio perfil;
   - `descartar` quando for pessoa física sem serviço próprio, perfil fora do público ou sem relação;
   - `pular` quando a informação não permitir decidir (fica pendente; não chute).
   Fornecedores do setor (sistemas, cursos, fábricas de urnas, mídia) contam como parceiros potenciais: mantenha a categoria
   mais próxima e escreva "fornecedor" na nota.
3. Grave as decisões com Write em `resultados/<analise>/revisao/minhas_decisoes.json`:
   ```json
   {"revisor": "claude", "decisoes": [{"usuario": "x", "decisao": "corrigir", "categorias": ["F","G"], "nota": "bio: plano e funeral 24h"}]}
   ```
   e aplique: `PRO aplicar-revisao <analise> --arquivo "<caminho>"`. Repita em lotes de ~40 até zerar os pendentes.
4. `PRO divergencias <analise>` lista onde a revisão discordou do automático. Se um padrão se repetir (3+ casos), sugira ao
   usuário ajustar a regra em `prospeccao/categorias.py` com teste de regressão — não altere regras sem pedido.

## 3. Entregar
- A análise aparece na plataforma (http://127.0.0.1:8770, `Abrir plataforma.cmd` na raiz do projeto). Todo perfil
  identificado entra automaticamente na **fila de pesquisa**, para depois ganhar CNPJ, telefone e endereço — pela aba
  **Fila de pesquisa** ou pelo comando `/executar-tarefa` do Claude Code. Lembre o usuário desse passo seguinte.
- `PRO exportar <analise>` → `resultados.csv` (uma linha por perfil × categoria, com situação, confiança, evidências, etapas,
  nota de revisão) e `arrobas_por_categoria.md`.
- Responda com: perfil de origem, quantos seguidores obtidos/analisados, identificados por categoria (lista de @ com 1 linha de
  motivo), quantos ficaram pendentes e o caminho do CSV. Diferencie o que veio do automático e o que você revisou.
