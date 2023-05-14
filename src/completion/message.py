from typing import List, Dict, Set

class Message:
    def __init__(self, role:str, content:str):
        self.role = role
        self.content = content

    @classmethod
    def get_list_of_dicts(cls, messages: List["Message"]) -> List[Dict[str, str]]:
        message_dicts = []
        for message in messages:
            #message.as_list_of_dicts()
            message_dicts.append(message.as_dict())
        return message_dicts
    
    def as_list_of_dicts(self) -> List[Dict[str, str]]:
        return [self.as_dict()]
    
    def as_dict(self):
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, message_dict: Dict[str, str]) -> "Message" :
        return Message(message_dict["role"], message_dict["content"])
    
    @classmethod
    def from_list_dict(cls, message_dict: List[Dict[str, str]]) -> List["Message"]:
        messages = []
        for message in message_dict:
            messages.append(Message(message["role"], message["content"]))
        return messages
