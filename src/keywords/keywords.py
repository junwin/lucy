from typing import List, Dict, Set
from collections import Counter
from nltk.stem import SnowballStemmer
from nltk.tokenize import word_tokenize
import nltk
import spacy
from nltk.corpus import wordnet as wn
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from datetime import datetime
from spacy.lang.en import STOP_WORDS
import re


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
            if self.language_code == "es":
                self.nlp = spacy.load("es_core_news_sm")
            else:
                self.nlp = spacy.load("en_core_web_sm")

            # Ensure NLTK data is present (auto-download on first run)
            ensure_nltk_data()

        except Exception as e:
            raise RuntimeError(f"Failed to initialize NLP dependencies: {e}")

    def extract_from_content(self, content: str, top_n: int = 10) -> List[str]:
        return self.extract_keywords(content, top_n)

    def extract_keywords(self, content: str, top_n: int = 10) -> List[str]:
        if 'request keywords:' in content:
            return self.get_specified_keywords(content)

        doc = self.nlp(content.lower())

        tokens = [t for t in doc if not t.is_punct and not t.is_space]

        # POS filter first (optional order)
        tokens = [t for t in tokens if t.pos_ in {"PROPN", "NOUN", "VERB"}]

        # Lemmatize
        lemmas = [t.lemma_.lower() for t in tokens]

        # Now stop-word filter on lemmas (not token.text)
        lemmas = [l for l in lemmas if l not in STOP_WORDS and l.strip()]

        word_frequency = Counter(lemmas)
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
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return round(similarity[0][0], 6)

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
