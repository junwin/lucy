---
tags:
  - Agent
  - src.agent
---


language_code - used in keywords to process text
select_type aka context_type  - determins how to select data for the contex (hybrid, document, history, keyword)
max_prompt_conversations  aka  max_prompt_conversations  -- number of past conversations used when send a new request
max_prompt_documents - not used  - was intended to manage how many keyword releated conversations could be added
temperature  - temperature on API calls
save_reposnses - aka save_responsesn - detemines is responses from the API are stored as conversations
model  - gpt model to use
message_processor - name of concrete message processor to be used on inbound messages
max_function_call_iterations  - aka max_iterations - maximum iterations for call backs from API to be handled
prompt_budget_tokens - not actually used  - intended to manage prompt size
system_prompt  - basic introduction used when creating a prompt for this agent - plain text
style_prompt - any style guidence added to a prompt plain text
persona - used to provide description of agent personality - plain text
partner_agent - aka - partner agent name - when the agent wishes to delegate tasks they are sent to this agent name
