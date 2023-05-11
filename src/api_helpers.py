import os
import json
import openai
import time
from openai.error import RateLimitError
import logging

with open("G:\My Drive\credential\oaicred.json", "r") as config_file:
    config_data = json.load(config_file)

openai.api_key = config_data["openai_api_key"]

def ask_question(conversation, model="gpt-3.5-turbo", temperature=0, max_retries=3, retry_wait=1):
    logging.info(f'ask_question start: {model}')
    retries = 0
    while retries <= max_retries:
        try:
            myAns = openai.ChatCompletion.create(
                model=model,
                messages=conversation,
                temperature=temperature,
            )
            response = myAns.choices[0].message['content']
            response = response.encode('utf-8').decode('utf-8')
            logging.info(f'ask_question end: {model}')
            return response
        except RateLimitError as e:
            if retries == max_retries:
                raise e
            retries += 1
            print(f"RateLimitError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)

def get_completion(prompt, temperature=0, model="gpt-3.5-turbo", max_retries=3, retry_wait=1):
    logging.info(f'get_completion start: {model}')
    messages = [{"role": "user", "content": prompt}]
    retries = 0
    while retries <= max_retries:
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,  # this is the degree of randomness of the model's output
            )
            logging.info(f'get_completion end: {model}')
            return response.choices[0].message["content"]
            
        except RateLimitError as e:
            if retries == max_retries:
                raise e
            retries += 1
            print(f"RateLimitError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)

def get_completion_from_messages(messages, model="gpt-3.5-turbo", temperature=0, max_retries=3, retry_wait=1):
    logging.info(f'get_completion_from_messages start: {model}')
    retries = 0
    while retries <= max_retries:
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,  # this is the degree of randomness of the model's output
            )
            logging.info(f'get_completion_from_messages end: {model}')
            return response.choices[0].message["content"]
        except RateLimitError as e:
            if retries == max_retries:
                raise e
            retries += 1
            print(f"RateLimitError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)
