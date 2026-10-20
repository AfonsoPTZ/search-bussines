# resultados/ — pesquisas de empresas

Cada pesquisa cria aqui uma pasta `AAAA-MM-DD_HHMMSS_<nome>/`, com os registros (um por empresa, cada dado com a
sua fonte e se está confirmado), o progresso, as correções da revisão e as planilhas `empresas.xlsx` / `.csv`.

**Esta pasta é a fonte da verdade.** O banco da plataforma é só um índice, refeito a partir daqui com
`plataforma sincronizar --completa`.

- Contém **dados reais de terceiros**: não publique e não apague.
- **Não é versionada** (veja o `.gitignore` da raiz): não vem no `git clone` e não vai para o repositório.
- **Faça backup** desta pasta — ela não tem cópia em lugar nenhum.
