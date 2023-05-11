import os
import json
from prompt_manager import PromptManager

agent_name = "lucy"
account_name = "test"
prompt_base_path = "data/prompts"
language_code = 'en-US'
test_id = '9999'


def create_sample_data():
    return {
        "prompts": [
            {
                "id": "9999",
                "utc_timestamp": "2023-05-02T14:39:01.823006Z",
                "total_chars": 40,
                "conversation": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant."
                    },
                    {
                        "role": "user",
                        "content": "What's the weather like today?"
                    },
                    {
                        "role": "assistant",
                        "content": "The weather is sunny today."
                    }
                ],
                "keywords": [
                    "todo"
                ],
                "conversationId": "weather"
            },
            {
                "id": "9998",
                "utc_timestamp": "2023-05-02T14:39:01.823006Z",
                "total_chars": 40,
                "conversation": [
                    {
                        "role": "system",
                        "content": "hello world"
                    },
                ],
                "keywords": [
                    "todo"
                ],
                "conversationId": "helloworld"
            },
            {
                "id": "9997",
                "utc_timestamp": "2023-05-02T14:39:01.823006Z",
                "total_chars": 40,
                "conversation": [
                    {
                        "role": "system",
                        "content": "its a lovely world hello world"
                    },
                    {
                        "role": "user",
                        "content": "i could not agree more - its lovely"
                    },
                ],
                "keywords": [
                    "todo"
                ],
                "conversationId": "helloworld2"
            },
            {
                "id": "9996",
                "utc_timestamp": "2023-05-02T14:39:01.823006Z",
                "total_chars": 40,
                "conversation": [
                    {
                        "role": "system",
                        "content": "hello world"
                    },
                ],
                "keywords": [
                    "todo"
                ],
                "conversationId": "helloworld2"
            }
        ]
    }


def create_prompt_manager():
    prompt_manager = PromptManager(
        prompt_base_path, agent_name, account_name, language_code[:2])
    prompt_manager.prompts_data = create_sample_data()
    return prompt_manager


def test_get_prompt():
    prompt_manager = create_prompt_manager()
    prompt = prompt_manager.get_prompt(test_id)
    assert prompt == create_sample_data()["prompts"][0]


def test_get_prompt_not_found():
    prompt_manager = create_prompt_manager()
    prompt = prompt_manager.get_prompt("2")
    assert prompt == []


def test_get_conversation_text():
    prompt_manager = create_prompt_manager()
    prompt = create_sample_data()["prompts"][0]
    conversation_text = prompt_manager.get_conversation_text(prompt)
    expected_text = {
        "system": "You are a helpful assistant.",
        "user": "What's the weather like today?",
        "assistant": "The weather is sunny today."
    }
    assert conversation_text == expected_text


def test_get_conversation_text_by_id():
    prompt_manager = create_prompt_manager()
    conversation_text = prompt_manager.get_conversation_text_by_id(
        "helloworld")
    print(conversation_text)
    expected_text = "system: hello world\n"
    assert conversation_text == expected_text

def test_get_conversation_text_by_id_longer():
    prompt_manager = create_prompt_manager()
    conversation_text = prompt_manager.get_conversation_text_by_id(
        "helloworld2")
    print(conversation_text)
    expected_text = "system: hello world\n"
    # assert conversation_text == expected_text
