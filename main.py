
import logging
from src.message_processor import MessageProcessor, FileResponseHandler
from injector import Injector
from src.container_config import container
from src.config_manager import ConfigManager
from src.response_handler import FileResponseHandler

from src.message_processor_store import MessageProcessorStore

config = ConfigManager('config.json')

# things that should go in a config file
prompt_base_path = config.get("prompt_base_path", "data/prompts")
agents_path = config.get("agents_path", "static/data/agents.json")
preset_path = config.get("preset_path", "static/data/presets.json")

message_processor_store = MessageProcessorStore()

# Configure logging
logging.basicConfig(filename='logs/my_log_file.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def get_prompt_manager(prompt_base_path, agent_name, account_name, language_code):
    prompt_store = container.get(PromptStore)
    return prompt_store.get_prompt_manager(prompt_base_path, agent_name, account_name, language_code)
   

def get_message_processor(agent_name, account_name):
    manager=message_processor_store.get_message_processor(agent_name, account_name)
    return manager

def role_play(language_code='en-US'):
    exit_words = ["adiós", "bye", "quit"]
    prompt_base_path = "data/prompts"

    language = language_code[:2]
    handler = FileResponseHandler()

    #prompt_manager = get_prompt_manager(prompt_base_path, "lucy", "test", language)
    processor = get_message_processor("lucy", "test")

    while True:
        user_input = input(">> ")
        if user_input.lower() in exit_words:
            processor.save_conversations()
            break
        if user_input == "exit":
            return

        response = processor.process_message(user_input, "console")

        print(response)

lucy = [
    {"role": "system", "content": "You are Lucy, a super friendly and helpful AI assistant who can have a conversation and likes to ask questions. Remember to use the information in the prompt and background context when answering questions, including software engineering topics."}
]

role_play('en-US')
