class PromptBuilderInterface:  # Abstract handler

    def build_prompt(self, content_text:str, conversationId:str, agent_name, account_name, context_type="none", max_prompt_chars=6000, max_prompt_conversations=20, context_name=''):
        pass
    

