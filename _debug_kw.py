"""Check POS tagging for 'endpoints' in different contexts."""
from src.keywords.keywords import Keywords
import spacy

kw = Keywords()
nlp = kw.nlp

tests = [
    "the http endpoints module needs to be refactored",
    "what endpoints are available for chat",
    "the presence of endpoints should have included",
    "endpoints",
]

for text in tests:
    doc = nlp(text.lower())
    for t in doc:
        if "endpoint" in t.text.lower():
            print(f"'{text}'")
            print(f"  token='{t.text}' pos={t.pos_} lemma={t.lemma_}")
    print()
