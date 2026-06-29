from typing import List, Dict, Set
from collections import Counter
from nltk.stem import SnowballStemmer
from nltk.tokenize import word_tokenize
import nltk
from nltk.corpus import wordnet as wn
from datetime import datetime
import re

CODELIKE_RE = re.compile(r"""
    (/[^\s]+) |                # paths like /home/...
    ([a-zA-Z0-9_-]+\.[a-z0-9]+) # filenames like config_manager.py
""", re.VERBOSE)

SYMBOL_RE = re.compile(r"^[=+\-*/<>:;,.()\[\]{}|\\]+$")

DEFAULT_CUSTOM_EXCLUDE = {
    # your recurring repo/chat noise:
    "src", "repo_lucy", "file", "load", "task", "tasklist", "tasklists",
    "summarize", "relative", "config_manager.py",
    # chatty verbs (if you keep VERB):
    "let", "use", "add", "want", "suppose", "normalization", "normalize", "normalized", "normalizes", "try", "tries", "tried", "see", "look", "looks", "looking", "check", "checks", "checking",    
    # additional exclusions
    "state", "domain", "model", "list", "validation", "result", "error", "documentation", "docs", "planning", "service", "manager", "helper", "tool", "tools", "assistant", "assistants", "user", "users", "person", "people", "team", "project", "projects", "code", "codesnippet", "codesnippets", "snippet", "snippets",
      "function", "functions", "class", "classes", "method", "methods", "field", "object", "objects", "variable", "variables", "data", "information", "info", "detail", "details", "context", "contexts", "input", "inputs", "output", "outputs",
      "run", "runs", "execute", "executes", "executing", "purpose",
}

# Import spaCy lazily inside _initialize_nlp_model to avoid requiring the
# heavy dependency at import time. Tests monkeypatch _initialize_nlp_model so
# they don't need spaCy; provide a default STOP_WORDS set here so tests can
# override it.
STOP_WORDS = set()


def ensure_nltk_data(*, logger=None) -> None:
    """Ensure required NLTK datasets are available.

    We auto-download on first run to avoid a common new-machine failure mode.
    """

    required = ["punkt"]

    for pkg in required:
        try:
            # punkt is stored under tokenizers/punkt
            if pkg == "punkt":
                nltk.data.find("tokenizers/punkt")
            else:
                nltk.data.find(pkg)
        except LookupError:
            if logger:
                logger.info("NLTK data '%s' not found; downloading...", pkg)
            nltk.download(pkg, quiet=True)
            # Re-check so we fail loudly if download did not work
            if pkg == "punkt":
                nltk.data.find("tokenizers/punkt")
            else:
                nltk.data.find(pkg)


class Keywords:
    """
    The Keywords class is responsible for managing the keywords, where a keyword is a
    collection of words that are related to each other and formed part of a conversation with
    the openai completions api. The class provides methods to extract keywords from a string and
    compare keywords to determine if they are similar.

    Attributes:
        language_code (str): The language code to be used for text processing.
        nlp (spacy.lang): The spacy NLP model loaded based on the language code.
    """

    def __init__(self, language_code="en"):
        self.language_code = language_code
        self.nlp = None
        self._initialize_nlp_model()

    def _initialize_nlp_model(self):
        try:
            # Local import to avoid requiring spaCy for tests that monkeypatch
            # this method out.
            import spacy
            from spacy.lang.en import STOP_WORDS as SPACY_STOP_WORDS

            if self.language_code == "es":
                self.nlp = spacy.load("es_core_news_sm")
            else:
                self.nlp = spacy.load("en_core_web_sm")

            # Ensure NLTK data is present (auto-download on first run)
            ensure_nltk_data()

            # Update module-level STOP_WORDS to the spaCy set
            global STOP_WORDS
            STOP_WORDS = set(SPACY_STOP_WORDS)

        except Exception as e:
            # If spaCy isn't available (e.g., in test environments), raise a
            # RuntimeError so callers can handle it, but allow tests which
            # monkeypatch this method to bypass it.
            raise RuntimeError(f"Failed to initialize NLP dependencies: {e}")

    def extract_from_content(self, content: str, top_n: int = 10) -> List[str]:
        return self.extract_keywords(content, top_n)

    def extract_keywords(self, content: str, top_n: int = 10) -> List[str]:
        if 'request keywords:' in content:
            return self.get_specified_keywords(content)

        doc = self.nlp(content.lower())

        tokens = [t for t in doc if not t.is_punct and not t.is_space]

        # for t in tokens:
        #    if t.text in {"obsidian_importer", "indexed_records"}:
        #        print(t.text, t.pos_, t.lemma_)

        # POS filter removed — the existing stopword exclusion list
        # (DEFAULT_CUSTOM_EXCLUDE) and length/symbol/codelike filters
        # already handle noise. Removing this lets domain terms like
        # "endpoints" that spaCy may mis-tag as VERB survive extraction.

        # Lemmatize
        lemmas = [t.lemma_.lower() for t in tokens]


        cleaned = []
        for l in lemmas:
            if not l.strip():
                continue
            if l in STOP_WORDS or l in DEFAULT_CUSTOM_EXCLUDE:
                continue
            if len(l) < 2:                 # drops "d"
                continue
            if SYMBOL_RE.match(l):         # drops "=" and friends
                continue
            if CODELIKE_RE.search(l):      # drops /paths and filenames
                continue
            cleaned.append(l)


        # Now stop-word filter on lemmas (not token.text)
        # lemmas = [l for l in lemmas if l not in STOP_WORDS and l.strip()]

        word_frequency = Counter(cleaned)
        keywords = [w for w, _ in word_frequency.most_common(top_n)]
        return keywords

    def get_specified_keywords(self, input_str: str) -> List[str]:
        match = re.search('```(.*?)```', input_str, re.S)
        if match:
            extracted_text = match.group(1)
            return extracted_text.split(',')
        else:
            return []

    def compare_keyword_lists_semantic_similarity(self, keywords1: List[str], keywords2: List[str]) -> float:
        t1 = self.concatenate_keywords(keywords1)
        t2 = self.concatenate_keywords(keywords2)
        similarity = self.compare_semantic_similarity(t1, t2)
        return round(similarity, 6)

    def compare_semantic_similarity(self, text1: str, text2: str) -> float:
        try:
            # Prefer sklearn implementation when available for better quality
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
            return round(float(similarity[0][0]), 6)
        except Exception:
            # Fallback lightweight implementation (no sklearn). Uses simple
            # token-frequency vectors and cosine similarity. Good enough for
            # tests and environments without sklearn installed.
            import math
            from collections import Counter

            def tokenize(t: str):
                return re.findall(r"\w+", t.lower())

            v1 = Counter(tokenize(text1))
            v2 = Counter(tokenize(text2))
            all_keys = set(v1) | set(v2)
            dot = sum(v1[k] * v2[k] for k in all_keys)
            norm1 = math.sqrt(sum((v1[k]) ** 2 for k in all_keys))
            norm2 = math.sqrt(sum((v2[k]) ** 2 for k in all_keys))
            if norm1 == 0 or norm2 == 0:
                return 0.0
            sim = dot / (norm1 * norm2)
            return round(sim, 6)

    def compare_keywords(self, set1: set, set2: set, operator: str = "and") -> bool:
        set1 = set(set1)  # Convert to set if not already a set
        set2 = set(set2)  # Convert to set if not already a set

        if operator == "and":
            return set1 == set2
        elif operator == "or":
            return len(set1.intersection(set2)) > 0
        else:
            raise ValueError("Invalid operator. Please use 'and' or 'or'.")

    def concatenate_keywords(self, keyword_list: List[str]) -> str:
        concatenated_keywords = " ".join(keyword_list)
        return concatenated_keywords
