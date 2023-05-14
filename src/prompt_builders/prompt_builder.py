
import openai
import logging
import re
from injector import Injector

from src.container_config import container
from src.config_manager import ConfigManager  
from src.prompt_store import PromptStore
from src.prompt_manager import PromptManager
from src.response_handler import FileResponseHandler
from src.source_code_response_handler import SourceCodeResponseHandler
from src.agent_manager import AgentManager
from src.message_preProcess import MessagePreProcess
from src.preset_handler import PresetHandler
from src.api_helpers import ask_question, get_completion
from src.preset_prompts import PresetPrompts 

from src.completion.completion_manager import CompletionManager
from src.completion.completion_store import CompletionStore
from src.completion.completion import Completion
from src.completion.message import Message
 



class PromptBuilder:
    def __init__(self, agent_name: str, account_name :str ):
        # self.name = name

        agent_manager = container.get(AgentManager)
        self.agent = agent_manager.get_agent(agent_name)
        self.config = container.get(ConfigManager) 

        self.completion_manager_store = container.get(CompletionStore)
        self.account_completion_manager = self.completion_manager_store.get_completion_manager(agent_name, account_name, self.agent['language_code'][:2])
        self.agent_account = self.config.get("agent_internal_account_name")
        self.agent_completion_manager = self.completion_manager_store.get_completion_manager(agent_name, self.agent_account, self.agent['language_code'][:2])

        prompt_base_path=self.config.get('prompt_base_path')  
        prompt_store = container.get(PromptStore)
        #self.account_prompt_manager: PromptManager = prompt_store.get_prompt_manager(self.agent['name'], account_name, self.agent['language_code'][:2])
        #self.agent_prompt_manager: PromptManager = prompt_store.get_prompt_manager(self.agent['name'], self.config.get("agent_internal_account_name"), self.agent['language_code'][:2])   
         
        self.seed_conversations = []
        self.context_type = self.agent["select_type"]
        self.handler = container.get(FileResponseHandler)   
        self.preprocessor = container.get(MessagePreProcess)
        self.account_name = account_name
        self.preset_handler = PresetHandler(container.get(PresetPrompts))

    def build_prompt(self, content_text:str, conversationId:str, agent, context_type="none", seed_name="seed", seed_paramters=[], max_prompt_chars=6000, max_prompt_conversations=20):
        logging.info(f'build_prompt: {context_type}')


        # agent properties that are used with the completions API
        model = agent["model"]
        temperature = agent["temperature"]
        num_past_conversations = agent["num_past_conversations"]
        num_relevant_conversations = agent["num_relevant_conversations"]
        use_prompt_reduction = agent["use_prompt_reduction"]

        my_user_content =  Message('user', content_text) 


        # get the agents seed prompts - this is fixed information for the agent
        agent_matched_seed_ids = self.get_matched_ids(self.agent_completion_manager, "keyword_match_all", seed_name, num_relevant_conversations, num_past_conversations)
        agent_matched_ids = self.get_matched_ids(self.agent_completion_manager, "keyword", content_text, num_relevant_conversations, num_past_conversations)
        agent_all_matched_ids = agent_matched_seed_ids + agent_matched_ids
        matched_messages_agent = self.agent_completion_manager.get_completion_messages(agent_all_matched_ids)

        if context_type == "simpleprompt":
            # use the text from compeltions
            my_agent_completions = self.agent_completion_manager.get_completion_byId(agent_matched_ids)
            my_text = my_agent_completions[0].concatenate_content()
            content_text = my_text + content_text   
            matched_messages_agent = []
 


        # get any matched account prompts for the account - this is fixed information for the account
        account_matched_ids = self.get_matched_ids(self.account_completion_manager, context_type, content_text, num_relevant_conversations, num_past_conversations)
        matched_messages_account = self.account_completion_manager.get_completion_messages(account_matched_ids)

        # does this agent use an open ai model to reduce and select only relevant prompts
        if use_prompt_reduction:
            text_info = self.account_completion_manager.get_formatted_text(account_matched_ids)

            preset_values = [text_info, content_text]
            my_useful_response = self.preset_handler.process_preset_prompt_values("getrelevantfacts", preset_values)
            useful_reponse = self.get_data_item(my_useful_response, "Useful information:")

            if useful_reponse != 'NONE' :
                matched_messages_account =  [Message('assistant', useful_reponse)]
            else:
                matched_messages_account = []

        agent_message_dicts = Message.get_list_of_dicts(matched_messages_agent)
        account_message_dicts = Message.get_list_of_dicts(matched_messages_account)
        full_prompt = agent_message_dicts + account_message_dicts  + my_user_content.as_list_of_dicts()

        #logging.info(f'returned prompt: {full_prompt}')
        # zz = Message.get_list_of_dicts(full_prompt)
        return full_prompt

    def get_matched_ids(self, completion_manager: CompletionManager, context_type : str, content_text : str, num_relevant_conversations : int, num_past_conversations : int):
        matched_accountIds = []

        if context_type == "keyword":
            matched_accountIds = completion_manager.find_keyword_promptIds(content_text, 'or', num_relevant_conversations)
        elif context_type == "keyword_match_all":
            matched_accountIds = completion_manager.find_keyword_promptIds(content_text,'and', num_relevant_conversations)
        elif context_type == "semantic":
            matched_accountIds = completion_manager.find_closest_completion_Ids(content_text, num_relevant_conversations, 0.1)
        elif context_type == "hybrid":
            matched_prompts_closest = completion_manager.find_closest_completion_Ids(content_text, num_relevant_conversations, 0.1)
            matched_prompts_latest = completion_manager.find_latest_completion_Ids(num_past_conversations)
            matched_accountIds = matched_prompts_closest + matched_prompts_latest
        elif context_type == "latest":
            matched_accountIds = completion_manager.find_latest_completion_Ids(num_past_conversations)
        else:
            matched_accountIds = []

        # sort the account prompts
        distinct_list = list(set(matched_accountIds))
        sorted_list = sorted(distinct_list)

        return sorted_list

    def get_data_item(self, input_string, data_point):
        regex_pattern = f"{re.escape(data_point)}\\s*(.*)"
        result = re.search(regex_pattern, input_string)
        if result:
            return result.group(1).strip()
        else:
            return None
     
