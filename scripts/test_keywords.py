#!/usr/bin/env python3
"""Test what keywords are extracted from various queries."""
import sys
sys.path.insert(0, '.')
from src.keywords.keywords import Keywords

kw = Keywords()
for q in ['tasklist', 'tasklists_manage', 'tasklist tool handler', 'storage', 'handler', 'tasklist tool']:
    print(f"{q!r} -> {kw.extract_keywords(q, top_n=10)}")
