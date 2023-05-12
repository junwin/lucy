from typing import List
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer


class TextComparator:
    @staticmethod
    def compare_keywords(set1: set, set2: set, operator: str = "and") -> bool:
        if operator == "and":
            return set1 == set2
        elif operator == "or":
            return len(set1.intersection(set2)) > 0
        else:
            raise ValueError("Invalid operator. Please use 'and' or 'or'.")

    @staticmethod
    def compare_texts(text1: str, text2: str, operator: str = "and") -> bool:
        keywords1 = set(text1.lower().split())
        keywords2 = set(text2.lower().split())
        return TextComparator.compare_keywords(keywords1, keywords2, operator)

    @staticmethod
    def compare_semantic_similarity(text1: str, text2: str) -> float:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return similarity[0][0]

    @staticmethod
    def compare_keyword_lists_semantic_similarity(
        keywords1: List[str], keywords2: List[str]
    ) -> int:
        set1 = set(keywords1)
        set2 = set(keywords2)
        similarity = TextComparator.compare_semantic_similarity(
            " ".join(set1), " ".join(set2)
        )
        return int(similarity * 100)
