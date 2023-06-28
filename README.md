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


## Lucy API Schema

The Lucy API schema supports the following methods:

### Conversation IDs

- `GET /conversationIds`: Retrieves a list of conversation IDs.
  - Required query parameters: `agentName`, `accountName`

- `PUT /conversationIds`: Renames a conversation ID.
  - Required query parameters: `agentName`, `accountName`, `existingId`, `newId`

### Compute Conversations

- `POST /prompt_builder`: Computes the prompt used, given specific parameters.
  - Required request body properties: `agentName`, `accountName`, `selectType`, `query`
  - Additional required property in the request body: `conversationId`

### Ask a Question

- `POST /ask`: Asks a question and returns the AI assistant's response.
  - Required request body properties: `question`, `agentName`, `accountName`, `conversationId`

### Agents

- `GET /agents`: Retrieves a list of agents.

### Prompts

- `POST /completions`: Similar to `POST /computeConversations`, adds a completions to the store.
  - Required request body properties: `agentName`, `accountName`, `selectType`, `query`
  - Additional required property in the request body: `conversationId`

- `GET /completions`: Retrieves one or more completions.
  - Required query parameters: `agentName`, `accountName`
  - Optional query parameter: `conversationId`

- `PUT /completions`: Updates a completions.
  - Required query parameters: `agentName`, `accountName`, `id`
  - Required request body properties: `id`, `prompt`

- `DELETE /completions`: Deletes a completions.
  - Required query parameters: `agentName`, `accountName`, `id`

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
