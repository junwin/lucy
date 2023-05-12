import json
from typing import List, Dict, Set
import time
import string
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


nltk.download('wordnet')
nltk.download('punkt')


class Keywords:
    def __init__(self, language_code="en"):
        self.language_code = language_code
        if language_code == "es":
            self.nlp = spacy.load("es_core_news_sm")
        else:
            self.nlp = spacy.load("en_core_web_sm")
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            nltk.download("punkt")



    def extract_keywords(self, content: str, top_n: int = 10) -> List[str]:
        if 'request keywords:' in content:
            return self.get_specified_keywords(content)

        doc = self.nlp(content.lower())

        no_punct_tokens = [token for token in doc if not token.is_punct]
        no_stop_tokens = [token for token in no_punct_tokens if token.text not in STOP_WORDS]
        filtered_tokens = [token for token in no_stop_tokens if token.pos_ in ["PROPN", "NOUN", "VERB"]]
        lemmatized_words = [token.lemma_ for token in filtered_tokens]
        word_frequency = Counter(lemmatized_words)
        keywords = [word for word, freq in word_frequency.most_common(top_n)]

        return keywords

    def get_specified_keywords(self, input_str: str) -> List[str]:
        match = re.search('```(.*?)```', input_str, re.S)
        if match:
            extracted_text = match.group(1)
            return extracted_text.split(',')
        else:
            return []
