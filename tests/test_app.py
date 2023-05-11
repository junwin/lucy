import requests
import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app
from typing import Set



@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_missing_parameters(client):
    response = client.post('/prompts', json={})
    assert response.status_code == 400


def test_post_prompts(client):
    # POST a new prompt
    post_data = {
        "agentName": "lucy",
        "accountName": "test",
        "selectType": "recent",
        "query": "what is the meaning of life?",
        "conversationId": "tc1",
        "id": "1682546435750517801",
        "utc_timestamp": "2023-04-26T22:00:35.750517Z",
        "total_chars": 312,
        "conversation": [
            {
                "role": "user",
                "content": "what is the meaning of life?",
                "utc_timestamp": "2023-04-26T22:00:35.750517Z"
            },
            {
                "role": "system",
                "content": "The meaning of life is a philosophical question and can vary from person to person. Some believe it's about finding happiness, while others think it's about making a difference in the world.",
                "utc_timestamp": "2023-04-26T22:00:35.750517Z"
            }
        ],
        "keywords": [
            "meaning",
            "life",
            "philosophical",
            "happiness",
            "difference"
        ],
        "conversationId": "tc1"
    }

    post_response = client.post('/prompts', json=post_data)
    assert post_response.status_code == 200
    # assert post_response.json == post_data

    # GET the prompts for the specified agentName, accountName, and conversationId
    get_response = client.get('/prompts', query_string={'agentName': 'lucy', 'accountName': 'test', 'conversationId': 'tc1'})
    assert get_response.status_code == 200
    assert any(prompt['conversationId'] == post_data['conversationId'] for prompt in get_response.json)
