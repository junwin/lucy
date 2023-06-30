# Agents

# Agents
- Agents manage the `behavior` of handling requests from a user by:
    - Using different message processors.
    - Setting the role of the agent when making requests to the completions API using a repertoire of completions specific to a particular agent.
- They determine the model and temperature used when calling the completions API.
# Agent Configuration
- The primary way to set up an agent is by editing `static/data/agents.json`. An example is provided below.
- Set up the agent's completion JSON at `data/completions`. The agent's intrinsic completions are in files of the format `<agent_name>_aaaa_conv.json`. For example, `lucy_aaaa_conv.json`.
## Example: static/data/agents.json
    {
        "name": "doris",
        "seed_conversation": [],
        "language_code": "en-US",
        "select_type": "latest",
        "num_past_conversations": 3,
        "num_relevant_conversations":0,
        "max_output_size": 4000,
        "write_file_threshold": 60000,
        "use_prompt_reduction": false,
        "temperature": 0,
        "save_responses": false,
        "model": "gpt-4-0613",
        "message_processor": "automation_processor",
        "partner_agent": "colin",
        "roles_used_in_context": [
            "user", "assistant"
        ]
    }


**Fields:**

- `seed_conversation` - Deprecated.
- `language_code` - ISO language code, mainly used when text-to-speech and speech-to-text is implemented.
- `select_type` - Determines how previous messages are used to build a prompt. Possible options are "latest", "semantic", "keyword", "keyword_match_all", "hybrid".
- `num_past_conversations` - For "latest" and "hybrid", this determines how many previous conversations are included.
- `num_relevant_conversations` - For "hybrid", "keyword", and "semantic", this determines how many conversations to include.
- `write_file_threshold` - Deprecated.
- `max_output_size` - Deprecated.
- `use_prompt_reduction` - If set to true, a separate call to the API is made to assess how relevant the prompt is to the request, reducing the prompt to useful content only.
- `temperature` - The temperature used when making API requests.
- `save_responses` - If set to false, messages are not saved locally. Defaults to true.
- `model` - Specifies the API model to be used.
- `message_processor` - The message processor that will handle requests to the agent. Defaults to 'message_processor'.
- `partner_agent` - Some message processors use multiple agents, for example, one to handle a request and another to assess the results.
- `roles_used_in_context` - When building a prompt based on stored completion messages, you can choose the roles to include. This would allow you to increase the relevance of the 'user' statements, for example.


# Agent Completion Example


    [
        {
            "id": "1",
            "utc_timestamp": "2023-05-01T17:24:32.966867Z",
            "total_chars": 39,
            "messages": [
                {
                    "content": "You are Debo, a super friendly and helpful AI assistant who loves software engineering. Remember to use the information in the prompt when performing requests, paying close attention to the output format. As an assistant, you can request any of the following actions shown in triple quotes. These are performed externally by putting them in
    
     your response. Pay attention to the use of triple backticks used when initiating an action:\n '''action_save_file: file_path: ```insert your path``` file_name: ```insert your file name``` file_content:```your file content:```\n'''action_load_file: file_path: ```insert your path``` file_name: ```insert your file name```\n'''action_execute_command: command: ```your command``` command_path: ```your path```\n'''action_request_user_action: ```your message:```\n'''action_add_steps: current_node_id: ```node id``` name: ```node name``` description: ```your description``` state: ```your state```\n",
                    "role": "system"
                }
            ],
            "tags": [
                "seed"
            ],
            "conversation_id": "seed"
        }
    ]

