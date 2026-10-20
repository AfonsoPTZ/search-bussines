# dados/ — banco da plataforma

| Arquivo | O que é |
|---|---|
| `plataforma.sqlite` | O banco de consulta: a fila de pesquisa e **as suas decisões** |
| `plataforma.log` | Log da interface |
| `claude/` | Execuções da revisão pelo Claude Code em segundo plano |

O banco tem dois tipos de conteúdo:

- **Derivado** das pastas de resultados (execuções, perfis, pesquisas, campos de filtro das empresas). Pode ser
  refeito a qualquer momento com `plataforma sincronizar --completa`.
- **Seu**: uniões e separações de empresas, vínculos confirmados ou rejeitados à mão, duplicidades decididas,
  execuções arquivadas, perfis dispensados da fila e o histórico dessas decisões. **Isto não dá para refazer.**

Por isso: **faça backup de `plataforma.sqlite`** e nunca o apague.

Esta pasta **não é versionada** (veja o `.gitignore` da raiz) e é criada sozinha na primeira execução.
