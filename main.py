
import logging
from src.message_processor import MessageProcessor
from injector import Injector
from src.container_config import container
from src.config_manager import ConfigManager
from src.agent_manager import AgentManager


config = ConfigManager('config.json')


# Configure logging
logging.basicConfig(filename='logs/my_log_file.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')



def role_play():
    exit_words = ["adiós", "bye", "quit"]

    while True:
        user_input = input(">> ")
        if user_input.lower() in exit_words:
            break
        if user_input == "exit":
            return
        response = ask(user_input)  
        print(response)

def ask(question: str) -> str:
    agentName = "doris"
    accountName = "cli"
    #select_type = request.json.get('selectType', '')
    conversationId = "cli"
    agent_manager = container.get(AgentManager)
    my_agent = agent_manager.get_agent(agentName)
    select_type = my_agent['select_type']

    processor = MessageProcessor()

    processor.context_type = select_type
    # Modify the process_message method in the MessageProcessor class if needed
    #process_message(self, agent_name:str, account_name:str, message, conversationId="0"):
    response = processor.process_message(agentName, accountName, question, conversationId)
    # processor.save_conversations()
    return response


role_play()
