from src.agent_manager import AgentManager

from src.api_helpers import ask_question
from src.container_config import container
import logging


class GlindaRequestHandler:

    def __init__(self):
        agent_manager = container.get(AgentManager) 

    def process_glinda_request(self, message, conversationId, agent, account_prompt_manager):
        my_text = account_prompt_manager.get_conversation_text_by_id(conversationId)
        my_request = "given we use the lifecoachschool method - please analyse the following request from the user look for feelings and circumstances " + my_text

        conversation = self.assemble_conversation(my_request, conversationId, "keyword")
 
        # logging.info(f'process_glinda_request: {conversation}')
        response = ask_question(conversation, agent["model"], agent["temperature"])
        # logging.info(f'process_glinda_request: {message}')

        new_request = "given that: " + response + " the user original request is: " + message

        logging.info(f'process_glinda_request result: {new_request}')

        #self.add_response_message(conversationId,  message, response)

        return "continue", new_request
