
from src.api_helpers import get_completion


class SummarizeRequestHandler:

    def process_summarize_request(self, message, conversationId, account_prompt_manager):
        my_text = account_prompt_manager.get_conversation_text_by_id(conversationId)
        my_request = "please summarize this: " + my_text

        response = get_completion(my_request, 0, "gpt-3.5-turbo")
        return "return", response
