from flask import Flask, request, jsonify, send_file, make_response
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
import ssl
import logging
import os

from src.storage.base import Storage
from src.storage.models import ChatMessage, UserProfile

from src.agent_manager import AgentManager
from src.container_config import container
from src.config_manager import ConfigManager
from src.prompt_builders.prompt_builder import PromptBuilder
from src.message_processors.processor_factory import ProcessorFactory
from src.message_endpoints.ask_request_handler import AskRequestHandler


app = Flask(__name__)
CORS(app)

config = ConfigManager("config.json")

# -----------------------------------------------------------------------------
# Serve OpenAPI (swagger.json) with cache disabled
# -----------------------------------------------------------------------------
@app.route("/swagger.json", methods=["GET"])
def swagger_json():
    """
    Serve the OpenAPI 3.0 spec file with cache disabled so Swagger UI always
    reloads when the file changes.
    """
    path = os.path.join(app.root_path, "static", "swagger.json")
    resp = make_response(send_file(path))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# -----------------------------------------------------------------------------
# Swagger UI
# -----------------------------------------------------------------------------
swaggerui_blueprint = get_swaggerui_blueprint(
    config.get("swagger_url", "/api/docs"),
    "/swagger.json",  # <-- served by route above (no-cache)
    config={
        "app_name": config.get("app_name", "Lucy API"),
    },
)
app.register_blueprint(
    swaggerui_blueprint,
    url_prefix=config.get("swagger_url", "/api/docs"),
)

# -----------------------------------------------------------------------------
# things that should go in a config file
# -----------------------------------------------------------------------------
prompt_base_path = config.get("prompt_base_path", "data/prompts")
agents_path = config.get("agents_path", "static/data/agents.json")
preset_path = config.get("preset_path", "static/data/presets.json")

storage = container.get(Storage)

# Configure logging
logging.basicConfig(
    filename="logs/my_log_file.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# Get the AgentManager instance
agent_manager = container.get(AgentManager)
agent_manager.load_agents()


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/ask", methods=["POST"])
def ask():
    """Main chat/agent interaction endpoint.

    This route is intentionally thin: it parses the JSON payload and delegates
    all business logic to AskRequestHandler, which is resolved via DI.
    """
    payload = request.get_json() or {}
    account_name = payload.get("accountName")

    if not account_name:
        return jsonify({"error": "accountName is required"}), 400

    user_profile = storage.get_user_profile(account_name)

    if user_profile is None:
        return jsonify({"error": f"Unknown account '{account_name}'"}), 403

    if not user_profile.active:
        return jsonify({"error": f"Account '{account_name}' is inactive"}), 403

    handler = container.get(AskRequestHandler)
    status, body = handler.handle(payload)
    return jsonify(body), status


@app.route("/agents", methods=["GET"])
def get_agents():
    try:
        my_list = agent_manager.get_available_agents()
        return jsonify(my_list)
    except Exception as e:
        logging.exception("Error in /agents")
        return jsonify({"error": str(e)}), 500


@app.route("/prompt_builder", methods=["POST"])
def build_prompt():
    payload = request.get_json() or {}

    question = payload.get("query", "")
    agentName = (payload.get("agentName", "") or "").lower()
    accountName = (payload.get("accountName", "") or "").lower()
    select_type = payload.get("selectType", "")
    conversationId = payload.get("conversationId", "")
    context_name = payload.get("contextName", "") or ""

    # allow optional list of extra system messages
    extra_system_messages = payload.get("extraSystemMessages") or []
    if not isinstance(extra_system_messages, list):
        extra_system_messages = [str(extra_system_messages)]

    if not question or not agentName or not accountName:
        return jsonify({"error": "Missing query, agentName, or accountName"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    my_agent = agent_manager.get_agent(agentName)
    if not select_type:
        select_type = my_agent.get("select_type", "hybrid")

    prompt_builder = PromptBuilder()

    prompt = prompt_builder.build_prompt(
        content_text=question,
        conversationId=conversationId,
        agent_name=agentName,
        account_name=accountName,
        context_type=select_type,
        max_prompt_chars=payload.get("maxPromptChars", 6000),
        max_prompt_conversations=payload.get("maxPromptConversations", 20),
        context_name=context_name,
        extra_system_messages=extra_system_messages,
    )

    return jsonify(prompt)


@app.route("/chats", methods=["POST"])
def post_chat():
    agentName = (request.json.get("agentName", "") or "").lower()
    accountName = (request.json.get("accountName", "") or "").lower()
    friendly_name = request.json.get("friendlyName")
    tags = request.json.get("tags")

    if not agentName or not accountName:
        return jsonify({"error": "Missing agentName or accountName"}), 400
    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    session = storage.create_chat_session(
        account_name=accountName,
        agent_name=agentName,
        friendly_name=friendly_name,
        tags=tags,
    )

    return jsonify(
        {
            "id": session.id,
            "account_name": session.account_name,
            "agent_name": session.agent_name,
            "friendly_name": session.friendly_name,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "tags": session.tags,
            "summary": session.summary,
            "importance_score": session.importance_score,
            "include_in_context": session.include_in_context,
            "metadata": session.metadata,
            "messages": [],
        }
    )


@app.route("/chats", methods=["GET"])
def get_chats():
    agentName = (request.args.get("agentName", "") or "").lower()
    accountName = (request.args.get("accountName", "") or "").lower()
    limit = int(request.args.get("limit", "50"))

    if not accountName:
        return jsonify({"error": "Missing accountName"}), 400
    if agentName and not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    sessions = storage.list_chat_sessions(
        account_name=accountName,
        agent_name=agentName or None,
        limit=limit,
        before=None,
    )

    return jsonify(
        [
            {
                "id": s.id,
                "account_name": s.account_name,
                "agent_name": s.agent_name,
                "friendly_name": s.friendly_name,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "tags": s.tags,
                "summary": s.summary,
                "importance_score": s.importance_score,
                "include_in_context": s.include_in_context,
                "metadata": s.metadata,
                "messages": [],
            }
            for s in sessions
        ]
    )


@app.route("/chats/<session_id>", methods=["GET"])
def get_chat(session_id: str):
    session = storage.get_chat_session(session_id)
    if not session:
        return jsonify({"error": "Chat not found"}), 404

    return jsonify(
        {
            "id": session.id,
            "account_name": session.account_name,
            "agent_name": session.agent_name,
            "friendly_name": session.friendly_name,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "tags": session.tags,
            "summary": session.summary,
            "importance_score": session.importance_score,
            "include_in_context": session.include_in_context,
            "metadata": session.metadata,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "utc_timestamp": m.utc_timestamp.isoformat() if m.utc_timestamp else None,
                    "metadata": m.metadata,
                }
                for m in session.messages
            ],
        }
    )


@app.route("/chats/<session_id>/messages", methods=["POST"])
def post_chat_message(session_id: str):
    data = request.get_json() or {}
    role = data.get("role")
    content = data.get("content")
    metadata = data.get("metadata") or {}

    if not role or content is None:
        return jsonify({"error": "Missing role or content"}), 400

    msg = ChatMessage(role=role, content=content, metadata=metadata)

    try:
        storage.append_chat_message(session_id, msg)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify({"status": "ok"})


# New stubs for future chat management
@app.route("/chats/<session_id>", methods=["DELETE"])
def delete_chat(session_id: str):
    """Delete a chat session."""
    try:
        session = storage.get_chat_session(session_id)
        if not session:
            return jsonify({"error": "Chat not found"}), 404

        storage.delete_chat_session(session_id)
        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("Failed to delete chat %s", session_id)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/chats/<session_id>", methods=["PATCH"])
def update_chat(session_id: str):
    """Update chat metadata such as friendly_name or tags."""
    payload = request.get_json(silent=True) or {}

    # Map JSON field names to storage method args
    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")
    include_in_context = payload.get("include_in_context")
    metadata = payload.get("metadata")

    try:
        session = storage.get_chat_session(session_id)
        if not session:
            return jsonify({"error": "Chat not found"}), 404

        storage.update_chat_session(
            session_id,
            friendly_name=friendly_name,
            tags=tags,
            include_in_context=include_in_context,
            metadata=metadata,
        )
        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("Failed to update chat %s", session_id)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/documents/search", methods=["GET"])
def search_documents():
    """Search documents (e.g., Obsidian notes) using simple keyword matching."""
    account_name = (request.args.get("accountName", "") or "").lower()
    query = request.args.get("q", "") or ""
    kind = request.args.get("kind") or None
    limit = int(request.args.get("limit", "10"))

    if not account_name:
        return jsonify({"error": "Missing accountName"}), 400
    if not query.strip():
        return jsonify({"error": "Missing q (query)"}), 400

    try:
        # We currently only have the implementation on JsonFileStorage,
        # but this can be promoted to the Storage interface later.
        if not hasattr(storage, "search_documents_poor_man"):
            return jsonify({"error": "Document search not supported by this storage backend"}), 501

        results = storage.search_documents_poor_man(
            account_name=account_name,
            query=query,
            kind=kind,
            limit=limit,
        )

        return jsonify(
            [
                {
                    "id": d.id,
                    "account_name": d.account_name,
                    "path": d.path,
                    "kind": d.kind,
                    "title": d.title,
                    "tags": d.tags,
                    "metadata": d.metadata,
                }
                for d in results
            ]
        )
    except Exception as e:
        logging.exception("Error in /documents/search")
        return jsonify({"error": str(e)}), 500


# NOTE:
# /completions and /conversationIds endpoints removed (they are gone).
# The OpenAPI file was updated accordingly.


def get_complete_path(base_path, agent_name, account_name):
    full_path = base_path + "/" + agent_name + "_" + account_name
    return full_path


def get_processor_name(agent_name, account_name):
    processor_name = agent_name + "_" + account_name
    return processor_name


if __name__ == "__main__":
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(
        config.get("ssl_cert", "192.168.1.245.pem"),
        config.get("ssl_key", "192.168.1.245-key.pem"),
    )
    app.run(
        host=config.get("host", "0.0.0.0"),
        port=config.get("port", 5000),
        ssl_context=context,
        debug=config.get("debug", True),
    )
