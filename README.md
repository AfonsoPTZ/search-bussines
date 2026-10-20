# Prospecção RIP Memorial

Plataforma local para encontrar parceiros do RIP Memorial e levantar os dados de contato deles.

Tudo roda no seu computador, em `127.0.0.1`. **Custo zero**: não há API paga nem serviço externo novo.

---

## Começar do zero (notebook novo)

```powershell
git clone <url-do-repositorio>
cd "Nova pasta (2)"
```

Depois **clique duas vezes em `instalar.cmd`**. Ele acha o Python, cria o ambiente e instala tudo (alguns minutos).

Em seguida, **clique duas vezes em `Abrir plataforma.cmd`** e abra <http://127.0.0.1:8770>.

> Precisa de **Python 3.11 ou mais novo** ([python.org](https://www.python.org/downloads/), marcando *Add python.exe to PATH*) e do **Git**.
> Os dados (análises, pesquisas e o banco) **não vêm no repositório** — veja [Os seus dados](#os-seus-dados).

### Dia a dia

| Quero | Faço |
|---|---|
| Abrir a plataforma | Dois cliques em `Abrir plataforma.cmd` → <http://127.0.0.1:8770> |
| Fechar | Fecho a janela preta. Análises e pesquisas em andamento continuam rodando |
| Reinstalar o ambiente | Apago a pasta `.venv` e rodo `instalar.cmd` de novo |

---

## Como o trabalho funciona

O trabalho tem **duas metades**, e é importante não confundi-las:

```
  ┌──────────────────────┐        ┌──────────────┐        ┌───────────────────────┐
  │  1. INSTAGRAM        │        │  2. FILA     │        │  3. EMPRESAS          │
  │  quem é parceiro     │  ───►  │  esperando   │  ───►  │  quem é essa empresa  │
  │  em potencial        │        │  os dados    │        │                       │
  │                      │        │              │        │                       │
  │  @, nome, segmento   │        │              │        │  CNPJ, telefone,      │
  │  A–M                 │        │              │        │  endereço, site       │
  └──────────────────────┘        └──────────────┘        └───────────────────────┘
```

1. **Instagram** — você informa um `@` e a ferramenta lê os seguidores dele, classificando cada perfil nos
   **13 segmentos de parceiros (A–M)**. Isso descobre *quem* interessa, mas não os dados da empresa.
2. **Fila de pesquisa** — todo perfil identificado entra automaticamente nesta fila, esperando o segundo passo.
   Nada se perde se você parar e voltar noutro dia.
3. **Empresas** — a pesquisa busca CNPJ, razão social, telefone, WhatsApp, e-mail, site e endereço de cada um,
   **sempre com a fonte** e dizendo o que está confirmado e o que não está.

### Esvaziar a fila: duas formas

| Forma | Como |
|---|---|
| Pela interface | Aba **Fila de pesquisa** → botão **Pesquisar pendentes** |
| Pelo Claude Code | Abra o projeto no VS Code e escreva **`/executar-tarefa`** no Claude |

As duas fazem a mesma pesquisa. A diferença é que o Claude também **revisa os casos incertos**: procura o site
oficial, confirma o CNPJ com a fonte e registra cada decisão. Depois é só recarregar a plataforma.

---

## Os 13 segmentos (A–M)

São o **único** critério de classificação do projeto, dos dois lados. Uma empresa que não é de nenhum deles
(padaria, restaurante, mercearia) fica **sem segmento** — isso é o esperado, não uma falha.

| | | | |
|---|---|---|---|
| **A** Placas, lápides e fotoporcelana | **B** Cemitérios pet | **C** Cemitérios | **D** Floriculturas |
| **E** Crematórios e funerárias pet | **F** Crematórios e funerárias humanas | **G** Seguro de vida e planos funerários | **H** Clínicas e hospitais veterinários |
| **I** Pet shops e serviços pet | **J** Igrejas e comunidades religiosas | **K** Hospitais e cuidados paliativos | **L** Organizações de apoio ao luto |
| **M** Psicólogos e terapeutas do luto | | | |

As regras ficam em `instagram/prospeccao/categorias.py` — **um lugar só**. A pesquisa de empresas traduz para
elas o CNAE da Receita e o tipo declarado no site (`pesquisa-empresas/empresas/categorias.py`).

---

## Como o projeto é organizado

| Pasta | Pacote | O que faz |
|---|---|---|
| `instagram/` | `prospeccao` | Lê os seguidores de um `@` e classifica nos segmentos A–M. Define os segmentos |
| `pesquisa-empresas/` | `empresas` | Pesquisa dados públicos de empresas brasileiras, com fonte e confirmação |
| `plataforma/` | `plataforma` | A interface única, a fila e o banco de consulta que junta as duas |
| `.claude/skills/` | — | Os comandos do Claude Code (`/executar-tarefa` e os das duas ferramentas) |

Cada pasta tem o seu próprio `README.md` com os detalhes.

### Linha de comando

```powershell
.venv\Scripts\plataforma.exe painel              # a interface
.venv\Scripts\plataforma.exe fila resumo         # o que está pendente
.venv\Scripts\plataforma.exe fila listar         # quem está esperando
.venv\Scripts\plataforma.exe fila pesquisar --limite 50
.venv\Scripts\plataforma.exe sincronizar         # relê as pastas de resultados

.venv\Scripts\prospeccao.exe analisar @perfil    # análise do Instagram
.venv\Scripts\empresas.exe pesquisar lista.txt   # pesquisa de empresas
```

---

## Os seus dados

**Nada de dados reais vai para o repositório.** Estas pastas ficam só na sua máquina (veja `.gitignore`):

| Onde | O que é |
|---|---|
| `instagram/resultados/` | As análises (JSONL com checkpoint). **Fonte da verdade** |
| `pesquisa-empresas/resultados/` e `entradas/` | As pesquisas e as listas enviadas. **Fonte da verdade** |
| `plataforma/dados/plataforma.sqlite` | O banco: a fila e **as suas decisões** (uniões, vínculos, arquivamentos) |

- O resto do banco é **derivado**: dá para refazer com `plataforma sincronizar --completa`.
- **Faça backup** de `plataforma/dados/` e das pastas `resultados/` — elas não têm cópia em lugar nenhum.
- São dados reais de terceiros: não publique e não apague.
- A sessão do Instagram **nunca** fica no projeto: é criptografada (DPAPI) em `%LOCALAPPDATA%\prospeccao-instagram`.

---

## Testes

```powershell
cd instagram;          ..\.venv\Scripts\python -m pytest -q    # 163
cd ..\pesquisa-empresas; ..\.venv\Scripts\python -m pytest -q  # 31
cd ..\plataforma;        ..\.venv\Scripts\python -m pytest -q  # 69
```

Os testes nunca escrevem nas pastas de resultados reais (usam `tmp_path`).

## Segurança

- A interface atende **só em `127.0.0.1`** e recusa Host estranho (DNS rebinding) e ações vindas de outros sites.
- Nenhum segredo fica no projeto.
- Só dados públicos e comerciais. Nada de sócios, CPFs ou dados pessoais.
- **Nada não confirmado é apresentado como confirmado**, em lugar nenhum.
