# src/api_helpers.py
import json
import time
import logging
from openai import OpenAI, RateLimitError, APIError
from src.container_config import container
from src.config_manager import ConfigManager

config = container.get(ConfigManager)
credential_path = config.get('credential_path')

with open(f"{credential_path}/oaicred.json", "r") as config_file:
    config_data = json.load(config_file)

# Prefer env var if you want, but this matches your current pattern
client = OpenAI(api_key=config_data["openai_api_key"])


def ask_question(conversation, model="gpt-4o", temperature=0, max_retries=3, retry_wait=1) -> str:
    logging.info(f'ask_question start: {model}')
    logging.info(f'before send: {conversation}')
    retries = 0

    while retries <= max_retries:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=conversation,
                temperature=temperature,
            )
            content = resp.choices[0].message.content or ""
            logging.info(f'ask_question end: {model}')
            return content

        except RateLimitError as e:
            if retries == max_retries:
                raise e
            retries += 1
            logging.warning(f"RateLimitError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)

        except APIError as e:
            if retries == max_retries:
                raise e
            retries += 1
            logging.warning(f"APIError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)


def get_completion(prompt: str, temperature: int = 0, model: str = "gpt-4o-mini",
                   max_retries: int = 3, retry_wait: int = 1):
    logging.info(f'get_completion start: {model}')
    messages = [{"role": "user", "content": prompt}]
    logging.info(f'before send: {messages}')

    retries = 0
    while retries <= max_retries:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            logging.info(f'get_completion end: {model}')
            return resp.choices[0].message.content

        except RateLimitError as e:
            if retries == max_retries:
                raise e
            retries += 1
            logging.warning(f"RateLimitError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)

        except APIError as e:
            if retries == max_retries:
                raise e
            retries += 1
            logging.warning(f"APIError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)


def get_completion_from_messages(messages, model="gpt-4o-mini", temperature=0,
                                 max_retries=3, retry_wait=1):
    logging.info(f'get_completion_from_messages start: {model}')
    retries = 0

    while retries <= max_retries:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            logging.info(f'get_completion_from_messages end: {model}')
            return resp.choices[0].message.content

        except RateLimitError as e:
            if retries == max_retries:
                raise e
            retries += 1
            logging.warning(f"RateLimitError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)

        except APIError as e:
            if retries == max_retries:
                raise e
            retries += 1
            logging.warning(f"APIError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)


def get_completionWithFunctions(messages, functions, temperature: int = 0,
                                model: str = "gpt-4o-mini",
                                max_retries: int = 3, retry_wait: int = 1):
    """
    Modern version of your function-calling helper using tools=.
    NOTE: the rest of the system still expects a dict-like message with
    .get("function_call"), so we’ll adapt the SDK object to that shape.
    """
    logging.info(
        f'get_completionWithFunctions start: model {model} functions {functions} messages {messages}'
    )
    retries = 0

    # Wrap Lucy's function defs into "tools" format
    tools = [
        {"type": "function", "function": fn_def}
        for fn_def in functions
    ]

    while retries <= max_retries:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
            )
            logging.info(f'get_completionWithFunctions end: {model}')

            choice = resp.choices[0]
            msg = choice.message

            # Adapt the message to your existing contract:
            # a dict with "content" and optional "function_call"
            out = {
                "role": msg.role,
                "content": msg.content or "",
            }

            # tools → one or more tool_calls
            if msg.tool_calls:
                # For simplicity, we support single tool call as before.
                # You *could* loop and handle multiple later.
                tc = msg.tool_calls[0]
                out["function_call"] = {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                }

            return out

        except RateLimitError as e:
            if retries == max_retries:
                raise e
            retries += 1
            logging.warning(f"RateLimitError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)

        except APIError as e:
            if retries == max_retries:
                raise e
            retries += 1
            logging.warning(f"APIError encountered, retrying... (attempt {retries})")
            time.sleep(retry_wait)
