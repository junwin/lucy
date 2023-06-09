from flask import Flask, request, jsonify, send_from_directory
from flask_swagger_ui import get_swaggerui_blueprint
from flask_swagger import swagger

from flask_cors import CORS
import ssl
import json
from typing import Set
import logging
from injector import Injector

from src.response_handler import FileResponseHandler

from src.agent_manager import AgentManager

from src.container_config import container
from src.config_manager import ConfigManager

from src.prompt_builders.prompt_builder import PromptBuilder
from src.message_processors.message_processor import MessageProcessor
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



# Configure logging
logging.basicConfig(filename='logs/my_log_file.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')





handler = FileResponseHandler(config.get("account_output_path"), 1000)

# Get the AgentManager instance
agent_manager = container.get(AgentManager)
agent_manager.load_agents()


@app.route('/ask', methods=['POST'])
def ask():
    question = request.json.get('question', '')
    agentName = request.json.get('agentName', '')
    agentName = agentName.lower()
    accountName = request.json.get('accountName', '')
    accountName = accountName.lower()
    select_type = request.json.get('selectType', '')
    conversationId = request.json.get('conversationId', '')

    if not question or not agentName or not accountName:
        return jsonify({"error": "Missing question, agentName, accountName, or conversationId"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    my_agent = agent_manager.get_agent(agentName)
    
    file_path = get_complete_path(prompt_base_path, agentName, accountName)
    if not select_type:
        select_type = my_agent['select_type']


    processor = MessageProcessor()

    processor.context_type = select_type
    # Modify the process_message method in the MessageProcessor class if needed
    #process_message(self, agent_name:str, account_name:str, message, conversationId="0"):
    response = processor.process_message(agentName, accountName, question, conversationId)
    # processor.save_conversations()
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

    question = request.json.get('query', '')
    agentName = request.json.get('agentName', '')
    agentName = agentName.lower()
    accountName = request.json.get('accountName', '')
    accountName = accountName.lower()
    select_type = request.json.get('selectType', '')
    conversationId = request.json.get('conversationId', '')

    if not question or not agentName or not accountName:
        return jsonify({"error": "Missing question, agentName, accountName, or conversationId"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    my_agent = agent_manager.get_agent(agentName)


    if not select_type:
        select_type = my_agent['select_type']

    #agents = agent_manager.get_available_agents()

    prompt_builder = PromptBuilder()


    #processor = get_message_processor(prompt_base_path, agentName, accountName, agents, processors)
    #build_prompt(self, content_text:str, conversationId:str, agent, context_type="none", seed_name="seed", seed_paramters=[], max_prompt_chars=6000, max_prompt_conversations=20):

    prompt_builder.context_type = select_type

    #def build_prompt(self, content_text:str, conversationId:str, agent_name, account_name, context_type="none", max_prompt_chars=6000, max_prompt_conversations=20):

    prompt = prompt_builder.build_prompt( question, conversationId, agentName, accountName, select_type)

    

    return jsonify(prompt)


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