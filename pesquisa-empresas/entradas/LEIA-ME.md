# entradas/ — listas enviadas para a pesquisa de empresas

As listas de empresas a pesquisar (`.txt`, `.csv`, `.xlsx`). Uma empresa por linha, aceitando
`@perfil`, URL do Instagram, site, CNPJ ou nome, com pistas separadas por ` | `:

```
Funerária São José | @funerariasaojose | Curitiba/PR
```

As listas criadas pela plataforma (inclusive as que saem da **fila de pesquisa**) caem aqui automaticamente.
Uma cópia da lista também fica dentro da pasta da pesquisa, em `../resultados/<lote>/entrada.*`.

- Pode conter **dados reais de terceiros**: não publique.
- **Não é versionada** (veja o `.gitignore` da raiz).
