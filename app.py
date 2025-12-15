from flask import Flask, request, jsonify, send_from_directory
from flask_swagger_ui import get_swaggerui_blueprint
from flask_swagger import swagger

from flask_cors import CORS
import ssl
import json
from typing import Set
import logging
from injector import Injector
from datetime import datetime
from src.storage.base import Storage
from src.storage.json_file_storage import JsonFileStorage
from src.storage.models import ChatMessage

from src.response_handler import FileResponseHandler

from src.agent_manager import AgentManager

from src.container_config import container
from src.config_manager import ConfigManager

from src.prompt_builders.prompt_builder import PromptBuilder
from src.message_processors.message_processor import MessageProcessor
from src.message_processors.guided_conversation_processor import GuidedConversationProcessor
from src.message_processors.function_calling_processor import FunctionCallingProcessor
from src.message_processors.automation_processor import AutomationProcessor
from src.completion.completion_store import CompletionStore
from src.completion.completion_manager import CompletionManager
from src.completion.completion import Completion




app = Flask(__name__)
CORS(app)


config = ConfigManager('config.json')
swaggerui_blueprint = get_swaggerui_blueprint(
    config.get("swagger_url", "/api/docs"),
    config.get("api_url", "/static/swagger.json"),
    config={
        'app_name': config.get("app_name", "Lucy API")
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=config.get("swagger_url", "/api/docs"))




# Set up Swagger UI
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'

# things that should go in a config file
prompt_base_path = config.get("prompt_base_path", "data/prompts")
agents_path = config.get("agents_path", "static/data/agents.json")
preset_path = config.get("preset_path", "static/data/presets.json")

storage = container.get(Storage) 


# Configure logging
logging.basicConfig(filename='logs/my_log_file.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')





handler = FileResponseHandler(config.get("account_output_path"), 1000)

# Get the AgentManager instance
agent_manager = container.get(AgentManager)
agent_manager.load_agents()


@app.route('/ask', methods=['POST'])
def ask():
    payload = request.get_json() or {}

    question = payload.get('question', '')
    agentName = (payload.get('agentName', '') or '').lower()
    accountName = (payload.get('accountName', '') or '').lower()
    select_type = payload.get('selectType', '')
    conversationId = payload.get('conversationId', '')
    secondary_agent = (payload.get('secondaryAgent', '') or '').lower()

    if not question or not agentName or not accountName:
        return jsonify({"error": "Missing question, agentName, or accountName"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    my_agent = agent_manager.get_agent(agentName)

    if not select_type:
        select_type = my_agent.get('select_type', '')

    partner_agent = (my_agent.get('partner_agent') or '').lower()
    context_name = ""

    mp = my_agent.get('message_processor', '')

    if mp == 'function_calling_processor':
        processor = FunctionCallingProcessor()
    elif mp == 'automation_processor':
        context_name = f"{agentName}_{partner_agent}"
        processor = AutomationProcessor()
    elif mp == 'guided_conversation_processor':
        context_name = f"{agentName}_{partner_agent}"
        processor = GuidedConversationProcessor()
    else:
        processor = MessageProcessor()

    processor.context_type = select_type

    response = processor.process_message(
        agentName,
        accountName,
        question,
        conversationId,
        context_name,
        partner_agent
    )

    return jsonify({"response": response})



@app.route('/agents', methods=['GET'])
def get_agents():
    try: 
        my_list = agent_manager.get_available_agents()
        zz = jsonify(my_list)
        return jsonify(my_list)
    except Exception as e:
            # log the exception or print the error message
            print(f"An error occurred: {e}")
    return []
   


@app.route('/prompt_builder', methods=['POST'])
def build_prompt():
    payload = request.get_json() or {}

    question = payload.get('query', '')
    agentName = (payload.get('agentName', '') or '').lower()
    accountName = (payload.get('accountName', '') or '').lower()
    select_type = payload.get('selectType', '')
    conversationId = payload.get('conversationId', '')
    context_name = payload.get('contextName', '') or ""

    # NEW: allow optional list of extra system messages
    extra_system_messages = payload.get('extraSystemMessages') or []
    if not isinstance(extra_system_messages, list):
        extra_system_messages = [str(extra_system_messages)]

    if not question or not agentName or not accountName:
        return jsonify({"error": "Missing query, agentName, or accountName"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    my_agent = agent_manager.get_agent(agentName)
    if not select_type:
        select_type = my_agent.get('select_type', 'hybrid')

    prompt_builder = PromptBuilder()

    prompt = prompt_builder.build_prompt(
        content_text=question,
        conversationId=conversationId,
        agent_name=agentName,
        account_name=accountName,
        context_type=select_type,
        max_prompt_chars=payload.get('maxPromptChars', 6000),
        max_prompt_conversations=payload.get('maxPromptConversations', 20),
        context_name=context_name,
        extra_system_messages=extra_system_messages,
    )

    return jsonify(prompt)



@app.route('/chats', methods=['POST'])
def post_chat():
    agentName = (request.json.get('agentName', '') or '').lower()
    accountName = (request.json.get('accountName', '') or '').lower()
    friendly_name = request.json.get('friendlyName')
    tags = request.json.get('tags')

    if not agentName or not accountName:
        return jsonify({"error": "Missing agentName or accountName"}), 400
    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    session = storage.create_chat_session(
        account_name=accountName,
        agent_name=agentName,
        friendly_name=friendly_name,
        tags=tags,
    )

    return jsonify({
        "id": session.id,
        "account_name": session.account_name,
        "agent_name": session.agent_name,
        "friendly_name": session.friendly_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "tags": session.tags,
        "summary": session.summary,
        "importance_score": session.importance_score,
        "include_in_context": session.include_in_context,
        "metadata": session.metadata,
        "messages": [],
    })


@app.route('/chats', methods=['GET'])
def get_chats():
    agentName = (request.args.get('agentName', '') or '').lower()
    accountName = (request.args.get('accountName', '') or '').lower()
    limit = int(request.args.get('limit', '50'))

    if not accountName:
        return jsonify({"error": "Missing accountName"}), 400
    if agentName and not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    sessions = storage.list_chat_sessions(
        account_name=accountName,
        agent_name=agentName or None,
        limit=limit,
        before=None,
    )

    return jsonify([
        {
            "id": s.id,
            "account_name": s.account_name,
            "agent_name": s.agent_name,
            "friendly_name": s.friendly_name,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "tags": s.tags,
            "summary": s.summary,
            "importance_score": s.importance_score,
            "include_in_context": s.include_in_context,
            "metadata": s.metadata,
            "message_count": len(s.messages),
        }
        for s in sessions
    ])
@app.route('/chats/<session_id>', methods=['GET'])
def get_chat(session_id: str):
    session = storage.get_chat_session(session_id)
    if not session:
        return jsonify({"error": "Chat not found"}), 404

    return jsonify({
        "id": session.id,
        "account_name": session.account_name,
        "agent_name": session.agent_name,
        "friendly_name": session.friendly_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "tags": session.tags,
        "summary": session.summary,
        "importance_score": session.importance_score,
        "include_in_context": session.include_in_context,
        "metadata": session.metadata,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "utc_timestamp": m.utc_timestamp.isoformat() if m.utc_timestamp else None,
                "metadata": m.metadata,
            }
            for m in session.messages
        ],
    })

@app.route('/chats/<session_id>/messages', methods=['POST'])
def post_chat_message(session_id: str):
    data = request.get_json() or {}
    role = data.get("role")
    content = data.get("content")
    metadata = data.get("metadata") or {}

    if not role or content is None:
        return jsonify({"error": "Missing role or content"}), 400

    msg = ChatMessage(role=role, content=content, metadata=metadata)

    try:
        storage.append_chat_message(session_id, msg)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify({"status": "ok"})


@app.route('/completions', methods=['POST'])
def post_completions():
    agentName = request.json.get('agentName', '').lower()
    accountName = request.json.get('accountName', '').lower()
    conversationId = request.json.get('conversationId', '')
    prompt = request.get_json()

    if not agentName or not accountName or not conversationId:
        return jsonify({"error": "Missing agentName, accountName, conversationId"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    agent = agent_manager.get_agent(agentName)
    completion_manager = get_completion_manager(agentName, accountName)
    completion = Completion.from_dict(prompt) 
    success = completion_manager.store_completion(completion)

    # add the new prompt to the prompt manager check the bool success to see if it was added


    if not success:
        return jsonify({"error": "Failed to store the new prompt"}), 400

    # Save the new prompt
    completion_manager.save()

    # Return the newly created prompt
    return jsonify(prompt)


@app.route('/completions', methods=['PUT'])
def put_completions():
    agentName = request.args.get('agentName', '').lower()
    accountName = request.args.get('accountName', '').lower()
    prompt_id = request.args.get('id', '')
    data = request.get_json()

    # json_string = request.get_data(as_text=True)
    # data2 = json.loads(json_string)

    if not agentName or not accountName or not prompt_id or not data:
        return jsonify({"error": "Missing agentName, accountName, or data"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    agent = agent_manager.get_agent(agentName)
    completion_manager = get_completion_manager(agentName, accountName)
    completion = Completion.from_dict(data) 
    success = completion_manager.update_completion(prompt_id, completion)

    if success:
        completion_manager.save()
        return jsonify(data)

    return jsonify({"status": "fail", "message": "Prompt failed to update"})


@app.route('/completions', methods=['DELETE'])
def delete_completions():
    agentName = request.args.get('agentName', '').lower()
    accountName = request.args.get('accountName', '').lower()
    prompt_id = request.args.get('id', '')

    if not agentName or not accountName or not prompt_id:
        return jsonify({"error": "Missing agentName, accountName, or id"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    agent = agent_manager.get_agent(agentName)
    completion_manager = get_completion_manager(agentName, accountName)
    success = completion_manager.delete_completion(prompt_id)


    if success:
        completion_manager.save()
        return jsonify({"status": "success", "message": "Prompt successfully deleted"})

    return jsonify({"status": "fail", "message": "Prompt failed to deleted"})


@app.route('/completions', methods=['GET'])
def get_completions():
    agentName = request.args.get('agentName', '').lower()
    accountName = request.args.get('accountName', '').lower()
    conversationId = request.args.get('conversationId', '')

    if not agentName or not accountName or not conversationId:
        return jsonify({"error": "Missing agentName, accountName, or conversationId"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    agent = agent_manager.get_agent(agentName)
    completion_manager = get_completion_manager(agentName, accountName)

    ids = completion_manager.get_Ids_with_conversation_id(conversationId) 
    prompts = completion_manager.get_completion_byId(ids)
    my_completions = []
    for completion in prompts:  
        my_completions.append(completion.as_dict())


    return jsonify(my_completions)




@app.route('/conversationIds', methods=['GET'])
def get_conversation_ids():
    agentName = request.args.get('agentName', '').lower()
    accountName = request.args.get('accountName', '').lower()
    conversationId = request.args.get('conversationId', '')

    if not agentName or not accountName:
        return jsonify({"error": "Missing agentName, accountName"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    agent = agent_manager.get_agent(agentName)

    completion_manager = get_completion_manager(agentName, accountName)
    # prompt_manager.load()
    conversation_ids = completion_manager.get_distinct_conversation_ids()
    return jsonify(conversation_ids)


@app.route('/conversationIds', methods=['PUT'])
def change_conversation_id():
    agentName = request.args.get('agentName', '').lower()
    accountName = request.args.get('accountName', '').lower()
    existingId = request.args.get('existingId', '')
    newId = request.args.get('newId', '')

    if not agentName or not accountName or not existingId or not newId:
        return jsonify({"error": "Missing agentName, accountName, existingId, or newId"}), 400
    
    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    agent = agent_manager.get_agent(agentName)

    completion_manager = get_completion_manager(agentName, accountName)
    completion_manager.change_conversation_id(existingId, newId)
    completion_manager.save()
    return jsonify({"message": "Conversation ID changed successfully"})

def get_completion_manager(agent_name, account_name):
    completion_store = container.get(CompletionStore)
    completion_manager = completion_store.get_completion_manager(agent_name, account_name)
    return completion_manager

def get_complete_path(base_path, agent_name, account_name):
    full_path = base_path + '/' + agent_name + '_' + account_name
    return full_path


def get_processor_name(agent_name, account_name):
    processor_name = agent_name + '_' + account_name
    return processor_name



if __name__ == "__main__":
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(config.get("ssl_cert", "192.168.1.245.pem"), config.get("ssl_key", "192.168.1.245-key.pem"))
    app.run(host=config.get("host", "0.0.0.0"), port=config.get("port", 5000), ssl_context=context, debug=config.get("debug", True))