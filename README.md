# Lucy

This project is an implementation of the Lucy API, providing various methods to interact with the AI assistant.

## Lucy API Schema

The Lucy API schema supports the following methods:

### Conversation IDs

- `GET /conversationIds`: Retrieves a list of conversation IDs.
  - Required query parameters: `agentName`, `accountName`

- `PUT /conversationIds`: Renames a conversation ID.
  - Required query parameters: `agentName`, `accountName`, `existingId`, `newId`

### Compute Conversations

- `POST /computeConversations`: Computes the prompt used, given specific parameters.
  - Required request body properties: `agentName`, `accountName`, `selectType`, `query`
  - Additional required property in the request body: `conversationId`

### Ask a Question

- `POST /ask`: Asks a question and returns the AI assistant's response.
  - Required request body properties: `question`, `agentName`, `accountName`, `conversationId`

### Agents

- `GET /agents`: Retrieves a list of agents.

### Prompts

- `POST /prompts`: Similar to `POST /computeConversations`, gets the prompt that would be used, given specific parameters.
  - Required request body properties: `agentName`, `accountName`, `selectType`, `query`
  - Additional required property in the request body: `conversationId`

- `GET /prompts`: Retrieves one or more prompts.
  - Required query parameters: `agentName`, `accountName`
  - Optional query parameter: `conversationId`

- `PUT /prompts`: Updates a prompt.
  - Required query parameters: `agentName`, `accountName`, `id`
  - Required request body properties: `id`, `prompt`

- `DELETE /prompts`: Deletes a prompt.
  - Required query parameters: `agentName`, `accountName`, `id`

## Getting Started

### Install Dependencies



python3 -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

pip install -r requirements.txt

python -m spacy download en_core_web_sm
python -m spacy download es_core_news_sm

### Virtual Environment

To activate the virtual environment:



venv\Scripts\activate  # On Unix-based systems, use `source venv/bin/activate`

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