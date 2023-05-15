# Class: `PromptBuilder`

The `PromptBuilder` class is responsible for constructing the prompt that will be used for the conversation with the OpenAI GPT model. It retrieves information from various sources including fixed agent information, account-specific prompts, and the completion manager. The class uses different strategies to match relevant prompts based on the specified context type.

### Attributes

- `agent_manager`: An instance of the `AgentManager` class used to manage different agents.
- `config`: An instance of the `ConfigManager` class used to manage the configuration settings.
- `seed_conversations`: A list to store seed conversations.
- `handler`: An instance of the `FileResponseHandler` class used to handle responses.
- `preset_handler`: An instance of the `PresetHandler` class used to handle preset settings.

### Methods

- `__init__`: The class constructor.
- `build_prompt`: Constructs the prompt for the conversation with the OpenAI GPT model.
- `get_matched_ids`: Finds matched prompts IDs based on the specified context type.
- `get_data_item`: Retrieves a data item from a string using a specified data point.

### Usage

```python
prompt_builder = PromptBuilder()
prompt = prompt_builder.build_prompt(content_text, conversationId, agent_name, account_name, context_type, max_prompt_chars, max_prompt_conversations)
```

# Class Documentation

## Class: CompletionManager

The CompletionManager class handles operations on conversation completions. It manages loading, saving, and manipulating completion data that is used to facilitate the conversation with the OpenAI GPT-3 API. A completion is a group of messages that form part of a conversation. The class provides methods to save and load completions, get completions by ID, store completions, create new completions, update and delete completions, find related completions, and more.

### Method Descriptions

- `save(self) -> None`: This method saves the current state of the CompletionManager, storing all the completion data to a JSON file.
- `load(self) -> None`: This method loads completion data from a JSON file into the CompletionManager.
- `get_completion(self, id: str) -> Completion`: This method retrieves a completion from the CompletionManager by its ID.
- `get_completion_byId(self, ids: List[str]) -> List[Completion]`: This method retrieves a list of completions from the CompletionManager by their IDs.
- `store_completion(self, completion:Completion) -> bool`: This method stores a new completion in the CompletionManager.
- `create_store_completion(self, conversation_id:str, request:str, response:str) -> bool`: This method creates a new completion and stores it in the CompletionManager.
- `update_completion(self, updated_completion:Completion) -> bool`: This method updates a completion in the CompletionManager.
- `delete_completion(self, completion_id: str) -> bool`: This method deletes a completion from the CompletionManager by its ID.
- `insert_new_completion_messages(self, messages: List[Dict[str, str]], conversationId:str) -> None`: This method inserts a new completion message to a completion in the CompletionManager.
- `find_closest_completion_Ids(self, input_text: str, number_to_return=2, min_similarity_threshold=0 ) -> List[str]`: This method finds the IDs of the completions that are most similar to the given input text.
- `find_latest_completion_Ids(self, number_to_return: int) -> List[str]`: This method retrieves the IDs of the most recent completions.
- `find_keyword_promptIds(self, content_text: str, match_operator:str, number_to_return=None) -> List[str]`: This method finds completion IDs that match the keywords in the content text.
- `get_Ids_with_conversation_id(self, conversation_id: str) -> List[str]`: This method retrieves completion IDs that match the given conversation ID.
- `get_completion_messages(self, completionIds: List[str]) -> List[Message]`: This method retrieves all messages from the completions with the given IDs.
- `get_formatted_text(self, completionIds: List[str]) -> str`: This method retrieves the formatted text for the completions with the given IDs.
- `get_distinct_conversation_ids(self) -> List[str]`: This method retrieves a list of unique conversation IDs from the completions.
- `change_conversation_id(self, old_id: str, new_id: str) -> None`: This method changes a conversation ID from old_id to new_id in the completions.

## Class: Completion

The Completion class represents a single completion. A completion is a collection of messages that are related to each other and formed part of a conversation with the OpenAI completions API. The class provides methods to create completions, convert completions to and from dictionary format for storage and retrieval, and add new messages to a completion.

### Method Descriptions

- `create_completion(cls,messages, conversation_id, tags)



# Class: Keywords

The `Keywords` class is responsible for managing keywords. A keyword is a collection of words that are related to each other and form part of a conversation with the OpenAI completions API. The class provides methods to extract keywords from a string and compare keywords to determine if they are similar.

## Attributes

- `language_code (str)`: The language code to be used for text processing.
- `nlp (spacy.lang)`: The spacy NLP model loaded based on the language code.

## Method Descriptions

- `__init__(self, language_code="en")`: Constructor for the `Keywords` class. Initializes a spacy NLP model based on the given language code.

- `extract_from_content(self, content: str, top_n: int = 10) -> List[str]`: Extracts keywords from the given content. Returns a list of the top N keywords.

- `extract_keywords(self, content: str, top_n: int = 10) -> List[str]`: Similar to `extract_from_content`, but also checks for specific keywords in the content.

- `get_specified_keywords(self, input_str: str) -> List[str]`: Extracts specified keywords from the input string.

- `compare_keyword_lists_semantic_similarity(self, keywords1: List[str], keywords2: List[str]) -> float`: Compares two lists of keywords for semantic similarity. Returns a similarity score between 0 and 1.

- `compare_semantic_similarity(self, text1: str, text2: str) -> float`: Compares two texts for semantic similarity using TF-IDF and cosine similarity. Returns a similarity score between 0 and 1.

- `compare_keywords(self, set1: set, set2: set, operator: str = "and") -> bool`: Compares two sets of keywords based on the given operator. Returns True if the keywords match based on the operator, False otherwise.

- `concatenate_keywords(self, keyword_list: List[str]) -> str`: Concatenates a list of keywords into a single string.

