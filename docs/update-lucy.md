# Updating Lucy

Lucy no longer owns sqlite-vec or the vec0 storage implementation directly.
Those responsibilities now live in `galet-memory`.

## Runtime storage

Lucy supports these values for `embedding_store_backend`:

- unset: use the shared `JsonFileStorage`
- `file`: use `PrimitivesEmbeddingStore` over file primitives
- `sqlite`: use `PrimitivesEmbeddingStore` over SQLite primitives

`embedding_store_backend=sqlite_vec` is no longer a Lucy configuration option.

## sqlite-vec and vec0

Native sqlite-vec loading, vec0 schema management, vec0 query behavior, and the
legacy vec migration utilities are maintained by the `galet-memory` package.
Do not install or configure `/usr/local/lib/sqlite-vec/vec0.so` specifically for
Lucy.

When work requires sqlite-vec directly, install and test `galet-memory` with its
`vec` extra in that repository/environment. The package prefers the
cross-platform `sqlite_vec` Python package and retains explicit native-path
loading only as compatibility support.

## Updating a Lucy checkout

After updating the branch:

```bash
git pull
python -m pip install -r requirements.txt
pytest
```

Every galet distribution is pinned to a released PyPI version in
`requirements.txt`, so updating needs no git access and no editable installs.
`pip check` should report no broken requirements.

If Lucy is developed alongside a local galet checkout, install that one package
editable in place of its PyPI pin:

```bash
python -m pip install -e ../galet-memory --no-deps
```

An editable install overrides the pin for that package only, so the environment
is no longer purely index-based. To go back to the released version:

```bash
python -m pip install --force-reinstall --no-deps galet-memory[vec]==0.1.0
```

The same pattern applies to `galet`, `galet-prompt-builder` and `galet-tools`,
using the versions listed in `requirements.txt`.

When bumping any galet package, update the pin in `requirements.txt` and the
version table in `README.md`.
