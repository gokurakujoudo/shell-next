# Maintaining documentation

The site is built from `docs/` with MkDocs. `mkdocs.yml` owns navigation and
theme configuration; `docs/assets/stylesheets/brand.css` owns the presentation.
The supplied `shell-next-logo.png` remains the canonical logo. Its byte-identical
copy in `docs/assets/` makes site builds independent of remote image hosts.

## Build and preview

```console
python -m pip install -e ".[docs]"
python -m mkdocs build --strict
python -m scripts.docs.validate
python -m mkdocs serve
```

The local preview is served at `http://127.0.0.1:8000`. Generated output lives in
`site/` and is ignored by Git. Strict builds fail on broken Markdown links or
navigation warnings; the validator also checks generated HTML links, fragments,
assets, and logo integrity.

## GitHub Pages

The `documentation` workflow builds pull requests for review. Pushes to
`codex/impl`, the repository's default branch, build and deploy through the
`github-pages` environment. The deploy job receives only Pages write and OIDC
permissions. No package publication is needed for documentation updates.

The public address is [gokurakujoudo.github.io/shell-next](https://gokurakujoudo.github.io/shell-next/).
If the default branch changes, update the workflow branch filter, deploy
condition, MkDocs edit links, and README logo URL together.

## Wiki drafts

Review-ready wiki files live in the repository's
[wiki directory](https://github.com/gokurakujoudo/shell-next/tree/codex/impl/wiki).
They are drafts, separate from the published Pages content. `Home.md`,
`_Sidebar.md`, and `_Footer.md` use GitHub Wiki naming conventions. Publishing
them to the separate wiki repository is an explicit follow-up operation.

The wiki is a short entry guide. Keep detailed API behavior in the Pages guides
and link to those pages rather than maintaining a second full specification.
