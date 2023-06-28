import logging
import argparse
from src.message_processors.message_processor import MessageProcessor
from src.message_processors.function_calling_processor import FunctionCallingProcessor
from injector import Injector
from src.container_config import container
from src.config_manager import ConfigManager
from src.agent_manager import AgentManager


# Set up command line argument parsing
parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--agentName', metavar='agent', type=str, nargs=1, default=['doug'],
                    help='the name of the agent')
parser.add_argument('--accountName', metavar='account', type=str, nargs=1, default=['user_id'],
                    help='the name of the account')
args = parser.parse_args()

config = ConfigManager('config.json')

# Configure logging
logging.basicConfig(filename='logs/my_log_file.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def role_play(agentName: str, accountName: str):
    exit_words = ["adiós", "bye", "quit"]

    while True:
        user_input = input(">> ")
        if user_input.lower() in exit_words:
            break
        if user_input == "exit":
            return
        response = ask(user_input, agentName, accountName)  
        print(response)

def ask(question: str, agentName: str, accountName: str) -> str:
    conversationId = "cli"
    agent_manager = container.get(AgentManager)
    my_agent = agent_manager.get_agent(agentName)
    select_type = my_agent['select_type']

    if 'message_processor' in my_agent and my_agent['message_processor'] == 'function_calling_processor':
        processor = FunctionCallingProcessor()
    else:
        processor = MessageProcessor()

    processor.context_type = select_type
    response = processor.process_message(agentName, accountName, question, conversationId)
    return response

# Use command line arguments for agentName and accountName
role_play(args.agentName[0], args.accountName[0])
