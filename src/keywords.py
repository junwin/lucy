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


    def extract_from_content(self, content: str, top_n: int = 10) -> List[str]:
        return self.extract_keywords(content, top_n)


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

    def compare_keyword_lists_semantic_similarity(self, keywords1: List[str], keywords2: List[str]) -> float:
        t1 = self.concatenate_keywords(keywords1)   
        t2 = self.concatenate_keywords(keywords2)
        similarity = self.compare_semantic_similarity(t1, t2 )
        return round(similarity, 6)
    

    def compare_semantic_similarity(self, text1: str, text2: str) -> float:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return round(similarity[0][0],6)
    
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