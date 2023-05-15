from typing import List, Dict, Set
from src.completion.message import Message
from src.completion.utils import get_id
from datetime import datetime
import time






class Completion:
    def __init__(self, id:str, utc_timestamp:str, total_chars:int, messages:List[Message], tags:List[str], conversation_id:str):
        self.id = id
        self.utc_timestamp = utc_timestamp
        self.total_chars =  total_chars
        self.messages = messages
        self.tags = tags
        self.conversation_id = conversation_id

    def __repr__(self):
        return f"Completion(id={self.id}, utc_timestamp={self.utc_timestamp}, total_chars={self.total_chars}, messages={self.messages}, tags={self.tags}, conversation_id={self.conversation_id})"
    
    @classmethod
    def create_completion(cls,messages, conversation_id, tags):
        completion = Completion(
            id= get_id(),
            utc_timestamp=datetime.utcnow().isoformat() + "Z",
            total_chars=0,
            messages=messages,
            tags=tags,
            conversation_id=conversation_id)
        return completion
    
    def as_dict(self):
        return {
            "id": self.id,
            "utc_timestamp": self.utc_timestamp,
            "total_chars": self.total_chars,
            "messages": [message.as_dict() for message in self.messages],
            "tags": self.tags,
            "conversation_id": self.conversation_id
        }   
    
    @classmethod
    def from_dict(cls, completion_dict: Dict[str, str]) -> "Completion" :
        my_competion =  Completion(completion_dict["id"], completion_dict["utc_timestamp"], completion_dict["total_chars"], [], completion_dict["tags"], completion_dict["conversation_id"])
        my_competion.messages = Message.from_list_dict(completion_dict["messages"])
        return my_competion

    def is_none_or_empty(self, string):
        return string is None or string.strip() == "" 
    

    
    def add_response_messages(self, request: str, response: str):

        self.add_response_message(response, "assistant")
        self.add_response_message(request, "user")


    def add_response_message(self, message_text: str, message_role: str):
        conversation = []
        if  (not self.is_none_or_empty(message_text) and  not self.is_none_or_empty(message_role)):
            message = Message(message_role, message_text)
            self.messages.append(message)
            
    def format_completion_text(self):
        concatenated_content = ""
        for message in self.messages:
            concatenated_content += message.content + " "

        return concatenated_content.strip()
