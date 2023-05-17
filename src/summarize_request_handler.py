
from src.api_helpers import get_completion
from src.container_config import container
from src.completion.completion_store import CompletionStore
from src.preset_handler import PresetHandler


class SummarizeRequestHandler:

    def process_summarize_request(self, message:str, conversation_id:str, agent_name:str, account_name:str) -> str:
        #presets = container.get(PresetPrompts)
        #preset = presets.get_prompt("summarize")
        completion_store = container.get(CompletionStore)
        completion_manager = completion_store.get_completion_manager(agent_name, account_name)
        ids = completion_manager.get_Ids_with_conversation_id(conversation_id)
        my_text = completion_manager.get_formatted_text(ids, None, "User: ", "Assistant:" ) 
        handler = PresetHandler()
        response = handler.process_preset_prompt_values("summarize", [my_text])   

        return  response
