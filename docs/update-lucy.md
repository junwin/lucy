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

If Lucy is developed alongside an editable `galet-memory` checkout, install the
local package explicitly as needed:

```bash
python -m pip install -e ../galet-memory --no-deps
```

Keep the Lucy and galet-memory Galet dependency versions aligned before adding a
permanent galet-memory VCS pin to Lucy's requirements.
