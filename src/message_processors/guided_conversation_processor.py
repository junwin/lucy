
import logging
import re
import yaml
from datetime import datetime
from dateutil.parser import parse
import pytz

from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.context.context_manager import ContextManager
from src.context.context import Context
from src.message_processors.message_processor import MessageProcessor
from src.completion.completion_store import CompletionStore
from src.completion.completion_manager import CompletionManager
from src.completion.completion import Completion
from src.container_config import container
from src.agent_manager import AgentManager
from src.config_manager import ConfigManager


class GuidedConversationProcessor(MessageProcessorInterface):
    def __init__(self):
        # self.name = name
        self.agent_manager = container.get(AgentManager)
        self.config = container.get(ConfigManager)
        prompt_base_path = self.config.get('prompt_base_path')
        self.seed_conversations = []
        self.message_processor = MessageProcessor()

    def process_message(self, agent_name: str, account_name: str, message, conversationId="0", context_name='', second_agent_name='') -> str:
        logging.info(f'Guided conversation: Processing message inbound: {message}')

        primary_agent = self.agent_manager.get_agent(agent_name)
        first_session = False
        new_session = False


        # get the context for this conversations
        context_mgr = ContextManager(self.config)
        context = context_mgr.get_context(account_name, context_name)
        if context is None:
            context = Context(context_name, "life coaching", "", 'none', account_name, conversationId)
            context.add_action("First Session", '', '')
            context_mgr.post_context(context)
            first_session = True


        completion_manager_store = container.get(CompletionStore)
        # primary account completion manager
        primary_account_completion_manager = completion_manager_store.get_completion_manager(agent_name, account_name, primary_agent['language_code'][:2])
        latest_completion_Ids = primary_account_completion_manager.find_latest_completion_Ids(1)

        #get the latest completion message - we can use this to see if and when the laset session occured
        if len(latest_completion_Ids) > 0:
            latest_completion_message = primary_account_completion_manager.get_completion(latest_completion_Ids[0])
            utc_timestamp = parse(latest_completion_message.utc_timestamp)
            elapsed_time = (datetime.now(pytz.utc) - utc_timestamp).total_seconds()
            new_session_time = self.config.get("elapsed_new_session_seconds")
            if elapsed_time > new_session_time:
                context.add_action("New Session", '', '')
                new_session = True
                first_session = False


        # get the latest completion messages as text
        #completions = primary_account_completion_manager.get_transcript(latest_completion_Ids)
        transcript =''
        if len(latest_completion_Ids) > 0:
            transcript = primary_account_completion_manager.get_transcript(latest_completion_Ids, ['user','assistant'], account_name, agent_name )
            context.add_transcript_item(account_name, transcript) 
            context_mgr.post_context(context)



        context_text = ""
        critic_message = ""
        if(first_session):
            critic_message = f" First session for user please welcome the user: : {account_name} is {message} \n"
        elif(new_session):
            critic_message = f" New session for user please review the context carefully : {account_name} is {message} \n"
        else:
            critic_message = f" Latest response from user: {account_name} is {message} \n"


        #if len(latest_completion_Ids) > 0:
        #    /context.transcript = context.transcript + " "  + transcript
         #   context_mgr.post_context(context)
      

        logging.info(f'Guided conversation: Processing message critic message: {critic_message}') 

        # process the messages and context in secondary agent
        response = self.message_processor.process_message(second_agent_name, account_name, critic_message, conversationId, context_name)
        logging.info(f'Guided conversation: agent: {second_agent_name} response: {response}')


        recommendations_start = response.find('Recommendations:')
        recommendations_end = response.find("'''", recommendations_start+18)
        if recommendations_end == -1 and recommendations_start != -1:
            recommendations_end = len(response)

        yaml_start = response.find('```')
        yaml_end = response.find('```', yaml_start+3)

        recommendations = response[recommendations_start:recommendations_end].strip()
        yaml_section = response[yaml_start:yaml_end].strip()

        if len(recommendations) > 0:
            context.recomendations = recommendations.strip()
        
        if len(yaml_section) > 0:
            context.conversation_state = yaml_section.strip()

        context_mgr.post_context(context)

        context_text = context.context_formated_text2('compact')
        #message = account_name + " says:" + message
        response = self.message_processor.process_message(agent_name, account_name, message, conversationId, context_name)

        return response

        
        

        
 