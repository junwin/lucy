# Lucy

# Introduction
"Lucy" is an innovative project designed to experiment and leverage the capabilities of OpenAI's completion API. The project aims to manage conversational behavior and automate processes using this technology.

# Features

1. **Agents**: These manage the behavior of the project, allowing for simple chats, guided conversations, automation, and function calling.
   
2. **Prompt Builder**: This feature enriches the prompts based on user requests. It factors in long-term relevance, recent trends, or a blend of both to construct a set of messages that can be utilized with the completion API.

3. **Completions**: This component stores and retrieves completions and messages from chats based on agent and user accounts. It also stores system roles for an agent based on the agent name.

4. **Message Processors**: They handle incoming messages and support prompt building, presets, guided conversations, function calling, and automation.

5. **Handlers**: These are used by automation and function calling to support requests made by the model or agents. They handle file loading, file saving, web search, and web page loading.

6. **Chunkers**: These are tools to chunk text when loading a large text file from a webpage, it processes the file in chunks.

7. **Context**: This is an information storage that can be shared with different agents. It is used where multiple agents help process a user request, for example, in a guided conversation or automation.

# Workflow

In "Lucy", the above-mentioned features collaborate effectively to manage and automate conversational behavior. The prompt builder enriches the user request, which the completion stores and recalls as needed. Message processors handle incoming messages, and handlers enhance these capabilities further. The chunkers handle large data, and context serves as shared storage for information.

# Project Link

More about the project can be found at: [https://github.com/junwin/lucy](https://github.com/junwin/lucy)


# Lucy API (v1.1.0)

## Endpoints

### `/conversationIds`

- `GET`: Get a list of conversation IDs
    - Parameters: `agentName` (string, required), `accountName` (string, required)
    - Responses: `200` (A list of conversation IDs), `400` (Bad request)

- `PUT`: Rename a conversation ID
    - Parameters: `agentName` (string, required), `accountName` (string, required), `existingId` (string, required), `newId` (string, required)
    - Responses: `200` (OK), `400` (Bad request)

### `/prompt_builder`

- `POST`: Get the prompt that would be used given an `agentName`, `accountName`, `selectType` and `query` text
    - Request Body: JSON object with `agentName` (string, required), `accountName` (string, required), `selectType` (string, required), `query` (string, required), `conversationId` (string, required)
    - Responses: `200` (A list of prompt elements), `400` (Bad request)

### `/ask`

- `POST`: Ask a question
    - Request Body: JSON object with `question` (string, required), `agentName` (string, required), `accountName` (string, required), `conversationId` (string, required)
    - Responses: `200` (AI assistant's response), `400` (Bad request)

### `/agents`

- `GET`: Get a list of agents
    - Responses: `200` (A list of agent objects)

### `/completions`

- `POST`: Add a new prompt to the completions database
    - Request Body: JSON object with `agentName` (string, required), `accountName` (string, required), `conversationId` (string, required)
    - Responses: `200` (A single prompt object), `400` (Bad request)

- `GET`: Get one or more completions
    - Parameters: `agentName` (string, required), `accountName` (string, required), `conversationId` (string, optional)
    - Responses: `200` (A list of completions objects)

- `PUT`: Update/replace a completion
    - Parameters: `agentName` (string, required), `accountName` (string, required), `id` (string, required)
    - Request Body: JSON object with `id` (string, required), `prompt` (Completion object, required)
    - Responses: `200` (Updated prompt object), `400` (Bad request)

- `DELETE`: Delete a completion
    - Parameters: `agentName` (string, required), `accountName` (string, required), `id` (string, required)
    - Responses: `200` (Completion successfully deleted), `400` (Bad request)

## Schema

### Completion

- `conversation`: Array of objects with `content` (string), `role` (string), `utc_timestamp` (date-time string) 
- `conversationId`: String
- `id`: String
- `keywords`: Array of strings
- `total_chars`: Integer
- `utc_timestamp`: Date-time string


## Getting Started

### Install Dependencies



python3 -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

pip install -r requirements.txt

python -m spacy download en_core_web_sm
python -m spacy download es_core_news_sm

or

python3 -m spacy download en_core_web_sm
python3 -m spacy download es_core_news_sm

### Virtual Environment

To activate the virtual environment:



venv\Scripts\activate  # On Unix-based systems, use `source venv/bin/activate`  source venv/bin/activate


### Running the Flask App



python app.py

You can access the Swagger UI at https://localhost:5000/api/docs or when debugging http://localhost:5000/api/docs.

The web service will start listening on http://localhost:5000. You can send a POST request to http://localhost:5000/ask with a JSON payload containing the question:

Request body:

json

{
  "question": "What is the first sentence in the wind in the willows",
  "agentName": "lucy",
  "accountName": "junwin",
  "conversationId": "1"
}

The web service will return the response in the following format:

json

{
  "response": "The first sentence in \"The Wind in the Willows\" by Kenneth Grahame is: \"The Mole had been working very hard all the morning, spring-cleaning his little home.\""
}

### Setting up HTTPS in Flask using mkcert

To enable HTTPS in your Flask application, you can generate a self-signed certificate using mkcert. Follow the steps below to get started:

    Install mkcert by following the instructions in the official documentation: https://github.com/FiloSottile/mkcert#installation.
    Once you have installed mkcert, generate a certificate for your desired domain name(s) by running the following command: mkcert example.com (replace example.com with your own domain name if desired).
    This will generate two files: a .pem file and a -key.pem file. These files are your SSL certificate and private key, respectively.
    In your Flask application code, add the following lines to enable HTTPS using the generated certificate and key:



import ssl

if __name__ == "__main__":
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('example.com.pem', 'example.com-key.pem')
    app.run(host='0.0.0.0', port=5000, ssl_context=context, debug=True)

That's it! You should now be able to access your Flask application using HTTPS. Note that because you are using a self-signed certificate, your browser may display a security warning when you try to access it. This is normal and you can safely ignore it - just be sure not to enter any sensitive information on the site until you have verified that the certificate's fingerprint matches the expected value.
