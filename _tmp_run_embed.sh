#!/bin/bash
source .venv/bin/activate
SRC=$(cat docs/minidoc/src_curation.md)
python scripts/test_embeddings.py --source "$SRC" --tests-file /tmp/test_strings_curation.txt
