from typing import List, Dict
import logging
import json
import nltk
from src.chunkers.text_chunker import TextChunker
from src.api_helpers import get_completion

class ChunkedFileProcessor():  


    def summarize_text_chunk(self, chunk: str) -> str:
        prompt =" your task is to summarize the following text into less than 400 words: " + chunk
        summary = get_completion(prompt)
        return summary
    
    def process_file_chunks(self, file_path, chunker: TextChunker, chunk_size) -> str:
        logging.info(f'process_json_chunks: start')

        with open(file_path, 'r') as file:
            file_contents = file.read()

        return self.process_text_data(file_contents, chunker, chunk_size)

  
    
    def process_text_data(self, data, chunker: TextChunker, chunk_size=1000) -> str:
        logging.info(f'process_json_chunks: start')

        digest = ""
        chunker = TextChunker()
        chunks = chunker.read_chunks(data, chunk_size)

        for chunk in chunks:
            summary = summary = self.summarize_text_chunk(chunk)
            digest += summary

        return digest


       