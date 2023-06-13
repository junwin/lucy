import json
from typing import List, Dict, Set, Optional

from datetime import datetime
from time import time
import logging
#from marshmallow import Schema, fields
from src.keywords import Keywords
from src.completion.completion import Completion
from src.completion.message import Message
from src.completion.utils import get_id, get_complete_path



class CompletionManager:
    """
    The CompletionManager class is responsible for managing the completions, where a completion is a
    collection of messages that are related to each other and formed part of a conversation with 
    the openai completions api
    """
    def __init__(self, base_path, agent_name, account_name, language_code="en"):
        self.language_code = language_code
        self.keywords_util = Keywords(language_code)
        self.agent_name = agent_name
        self.account_name = account_name
        self.base_path = base_path
        self.completions = []

 
    def save(self) -> None:
        path = get_complete_path(self.base_path, self.agent_name, self.account_name)
        logging.info(f'CompletionManager save : {path}')
        with open(path, "w") as f:
            # Convert each Completion object and its Messages into a dictionary
            data = []
            for completion in self.completions:
                completion_dict = completion.as_dict()
                data.append(completion_dict)

            # Save the data to the file as JSON
            json.dump(data, f)


    def load(self) -> None:
        path = get_complete_path(self.base_path, self.agent_name, self.account_name)
        logging.info(f'CompletionManager load : {path}')
        try:
            with open(path, "r") as f:
               data = json.load(f)
               for item in data:
                    completion = Completion(
                    id=item['id'],
                    utc_timestamp=item['utc_timestamp'],
                    total_chars=item['total_chars'],
                    messages=[],  # We'll add messages shortly
                    tags=item['tags'],
                    conversation_id=item['conversation_id'])

                    for message_data in item['messages']:
                        completion.add_response_message(message_data['content'], message_data['role'])

                    self.completions.append(completion)
          

        except FileNotFoundError:
            # If the file is not found, set completions to an empty list or default value
            logging.error(f'CompletionManager load file not found: {path}')
            self.completions = []



    def get_completion(self, id: str) -> Completion:
        for completion  in self.completions:
            if completion.id == id:
                return completion
        return None
    
    
    
    def get_completion_byId(self, ids: List[str]) -> List[Completion]:
        completion_list = []
        for completion  in self.completions:
            if completion.id in ids:    
                completion_list.append(completion)
        return  completion_list
    
    def store_completion(self, completion:Completion) -> bool:
        self.completions.append(completion)
        return True
    
    def create_store_completion(self, conversation_id:str, request:str, response:str) -> bool:
        request_message = Message("user", request)
        response_message = Message("assistant", response)
        tags = self.keywords_util.extract_keywords(request + response)

        completion = Completion.create_completion([request_message, response_message], conversation_id, tags)

        self.completions.append(completion)
        return True
    
    def update_completion(self, updated_completion:Completion) -> bool:
        for i, completion in enumerate(self.completions):
            if completion.id == updated_completion.id:
                self.completions[i] = updated_completion
                return True
        return False


    def delete_completion(self, completion_id: str) -> bool:
        for index,completion in enumerate(self.completions):
            if completion.id == completion_id:
                del self.completions[index]
                return True
        return False

    def insert_new_completion_messages(self, messages: List[Dict[str, str]], conversationId:str) -> None:
        id = get_id()
        utc_timestamp = datetime.utcnow().isoformat() + "Z"  # ISO 8601 format
        total_chars = sum(len(conv["content"]) for conv in messages)
        keywords = set()

        for message in messages:
            content = message["content"]
            keywords |= set(self.keywords_util.extract_keywords(content))

        completion = Completion(id, utc_timestamp, total_chars, Message.from_list_dict(messages), list(keywords), conversationId)

        self.store_completion(completion)


    def find_closest_completion_Ids(self, input_text: str, number_to_return=2, min_similarity_threshold=0 ) -> List[str]:
        
        completion_similarities = []
        tokenized_input_text = self.keywords_util.extract_from_content(input_text)
        for completion in self.completions:
            #concat_text = self.concatenate_content(prompt)
            #concatenate_keywords = self.keywords_util.concatenate_keywords(prompt["keywords"])
            similarity = self.keywords_util.compare_keyword_lists_semantic_similarity(tokenized_input_text, completion.tags)

            if similarity > min_similarity_threshold:
                completion_similarities.append((completion.id, similarity))


        sorted_completion_ids = sorted(
            completion_similarities, key=lambda x: x[1], reverse=True
        )

        zz = [id[0] for id in sorted_completion_ids[:number_to_return]]

        return zz

    def find_latest_completion_Ids(self, number_to_return: int) -> List[str]:

        if len(self.completions) > 0:
            sliced_list = self.completions[-number_to_return:]
            result = [completion.id for completion in sliced_list]
            return result

        return []
    
    def find_keyword_promptIds(self, content_text: str, match_operator:str, number_to_return=None) -> List[str]:
        keywords = self.keywords_util.extract_from_content(content_text)
        matched_completion_ids = set()

        for completion in self.completions:
            if self.keywords_util.compare_keywords(keywords, completion.tags, match_operator):
                matched_completion_ids.add(completion.id)

        # Convert the set of matched prompt IDs to a list
        matched_ids_list = list(matched_completion_ids)

        # Return the specified number of prompt IDs, if provided
        if number_to_return is not None:
            return matched_ids_list[:number_to_return]

        return matched_completion_ids
    
    def get_Ids_with_conversation_id(self, conversation_id: str) -> List[str]:
        matching_ids = []

        for completion in self.completions:
            if completion.conversation_id == conversation_id:
                matching_ids.append(completion.id)

        return matching_ids
    
    def get_completion_messages(self, completionIds: List[str], roles: Optional[List[str]] = None) -> List[Message]:
        if roles is None:
            roles = ['user', 'assistant', 'system']

        completions = self.get_completion_byId(completionIds)
        messages = []
        for completion in completions:
            for message in completion.messages:
                if(message.role in roles):
                    messages.append(message)    
        return messages

    def get_default_roles(self) -> List[str]:
        return ['user', 'assistant', 'system']
    
    def get_transcript(self, completionIds: List[str], roles: Optional[List[str]] = None, user_intro = "User: ", assistant_intro = "Assistant:" ) -> str:
        if roles is None:
            roles = self.get_default_roles()
        response_text = ""
        for completion in self.get_completion_byId(completionIds):
            text = completion.format_completion_text(roles, user_intro, assistant_intro)
            if len(text) > 0:
                response_text += text + "\n"
        return response_text
    
    def get_formatted_conversations(self, completionIds: List[str], roles: Optional[List[str]] = None) -> str:
        if roles is None:
            roles = self.get_default_roles()
        response_text = ""
        user_intro = "User: "
        assistant_intro = "Assistant: "
        
        for completion in self.get_completion_byId(completionIds):
            text = completion.format_completion_text(roles, user_intro, assistant_intro)
            if len(text) > 0:
                response_text += text + "\n"
        return response_text
    
    
    def get_distinct_conversation_ids(self) -> List[str]:
        conversation_ids = set()
        for completion in self.completions:
            conversation_ids.add(completion.conversation_id)
        return list(conversation_ids)

    def change_conversation_id(self, old_id: str, new_id: str) -> None:
        for completion in self.completions:
            if completion.coversation_id == old_id:
                completion.coversation_id = new_id