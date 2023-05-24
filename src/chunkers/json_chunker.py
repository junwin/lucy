
from typing import List, Dict
import logging
import json
import nltk
from nltk.tokenize import sent_tokenize



class JsonChunker():  
     
    def read_chunks(self, data, chunk_size):
            sentences = sent_tokenize(data)

            current_chunk = []
            current_chunk_size = 0

            for sentence in sentences:
                sentence_length = len(sentence)
                
                if current_chunk_size + sentence_length <= chunk_size:
                    current_chunk.append(sentence)
                    current_chunk_size += sentence_length
                else:
                    yield " ".join(current_chunk)
                    current_chunk = [sentence]
                    current_chunk_size = sentence_length

            if current_chunk:
                yield " ".join(current_chunk)