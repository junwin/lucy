from flask import Flask, request, jsonify, send_file, make_response
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
import ssl
import logging
from logging.handlers import RotatingFileHandler
import os
import time
import uuid

from src.request_context import request_id_var

from src.storage.base import Storage
from src.storage.models import ChatMessage

from src.agent import AgentManager
from src.container_config import container
from src.config_manager import ConfigManager
from src.prompt_builders.prompt_builder import PromptBuilder
from src.message_endpoints.ask_request_handler import AskRequestHandler


# -----------------------------------------------------------------------------
# request_id correlation
# -----------------------------------------------------------------------------


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Inject request_id into every LogRecord
        record.request_id = request_id_var.get("-")
        return True


def _ensure_logs_dir_exists() -> None:
    # Ensure logs/ directory exists
    os.makedirs("logs", exist_ok=True)


def configure_logging() -> None:
    """Configure app logging once.

    Rotates logs in logs/my_log_file.log.

    Grep tip across rotated logs:
      grep -R "<text>" logs/my_log_file.log*
    """

    _ensure_logs_dir_exists()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Replace any existing handlers (e.g., Flask default, basicConfig, etc.)
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = RotatingFileHandler(
        filename="logs/my_log_file.log",
        maxBytes=1_000_000,  # ~1MB
        backupCount=10,
        encoding="utf-8",
    )

    handler.addFilter(RequestIdFilter())
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - request_id=%(request_id)s - %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)


app = Flask(__name__)
CORS(app)

config = ConfigManager("config.json")

# Configure logging (initialized once in app.py and used throughout the app)
configure_logging()


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
agents_path = config.get("agents_path", "static/data/agents.json")


storage = container.get(Storage)


# Get the AgentManager instance
agent_manager = container.get(AgentManager)


# -----------------------------------------------------------------------------
# Request lifecycle hooks
# -----------------------------------------------------------------------------
@app.before_request
def _set_request_id() -> None:
    # Accept X-Request-Id (case-insensitive) or generate a UUID.
    rid = (request.headers.get("X-Request-Id") or "").strip() or str(uuid.uuid4())
    request_id_var.set(rid)
    request._lucy_start_ts = time.perf_counter()  # type: ignore[attr-defined]


@app.after_request
def _clear_request_id(response):
    # Clear request_id at end of request to avoid leaking between requests.
    request_id_var.set("-")
    return response


@app.teardown_request
def _teardown_request_id(exc):
    # Also clear on teardown (covers exceptions).
    request_id_var.set("-")


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

    try:
        user_profile = storage.get_user_profile(account_name)
    except Exception:
        # This can happen during migrations or when storage is misconfigured.
        # Keep the client response generic, but log the unusual exit.
        logging.exception("/ask: failed to load user profile for user_id=%s", account_name)
        return jsonify({"error": "An error occurred"}), 500

    if user_profile is None:
        # Expected during migrations: user exists in auth/UI but not in storage yet.
        logging.info("/ask: user profile not found for user_id=%s", account_name)
        return jsonify({"error": f"Unknown account '{account_name}'"}), 403

    if not user_profile.active:
        logging.info("/ask: inactive account for user_id=%s", account_name)
        return jsonify({"error": f"Account '{account_name}' is inactive"}), 403

    # New behavior: support friendlyName-based session resume/creation when
    # conversationId is missing or blank in the payload.
    conv_id = (payload.get("conversationId") or "").strip()
    if not conv_id:
        friendly_name = payload.get("friendlyName")
        if friendly_name:
            agent_name = (payload.get("agentName") or "").lower()
            if not agent_name:
                logging.info("/ask: friendlyName provided but agentName missing; skipping session lookup")
            else:
                try:
                    # Try to find existing session by friendly name
                    matches = []
                    if hasattr(storage, "find_chat_sessions_by_friendly_name"):
                        matches = storage.find_chat_sessions_by_friendly_name(
                            account_name, agent_name, friendly_name, limit=1
                        )
                    if matches:
                        session = matches[0]
                        conv_id = session.id
                        payload["conversationId"] = conv_id
                        logging.info(
                            "/ask: resumed session id=%s for friendlyName=%s account=%s agent=%s",
                            conv_id,
                            friendly_name,
                            account_name,
                            agent_name,
                        )
                    else:
                        # No existing session — create one so the conversationId is stable
                        try:
                            session = storage.create_chat_session(
                                account_name=account_name,
                                agent_name=agent_name,
                                friendly_name=friendly_name,
                            )
                            conv_id = session.id
                            payload["conversationId"] = conv_id
                            logging.info(
                                "/ask: created new session id=%s for friendlyName=%s account=%s agent=%s",
                                conv_id,
                                friendly_name,
                                account_name,
                                agent_name,
                            )
                        except Exception:
                            logging.exception(
                                "/ask: failed to create chat session for friendlyName=%s account=%s agent=%s",
                                friendly_name,
                                account_name,
                                agent_name,
                            )
                except Exception:
                    logging.exception(
                        "/ask: failed to lookup chat session for friendlyName=%s account=%s agent=%s",
                        friendly_name,
                        account_name,
                        agent_name,
                    )

    handler = container.get(AskRequestHandler)
    status, body = handler.handle(payload)

    # Ensure response body includes conversation_id for client convenience.
    try:
        # Prefer the conversationId we set on the payload, fallback to any
        # value returned by the handler.
        returned_conv = (payload.get("conversationId") or payload.get("conversation_id") or conv_id)
        if isinstance(body, dict) and returned_conv:
            body["conversation_id"] = returned_conv
    except Exception:
        logging.exception("/ask: failed to attach conversation_id to response body")

    return jsonify(body), status


@app.route("/context/names", methods=["GET"])
def list_context_names():
    """Return a JSON list of context names for the given account.

    Query param:
      accountName: required

    Response:
      ["lucy_client", "lucy_gptchum", "lucyproject"]
    """

    account_name = (request.args.get("accountName") or "").strip()
    if not account_name:
        return jsonify({"error": "Missing accountName"}), 400

    try:
        return jsonify(storage.list_context_names(account_name)), 200
    except Exception:
        logging.exception(
            "/context/names: failed to list context names for account=%s", account_name
        )
        return jsonify({"error": "An error occurred"}), 500


@app.route("/agents", methods=["GET"])
def get_agents():
    try:
        agents = agent_manager.get_available_agents()
        return jsonify([a.to_dict() for a in agents])
    except Exception as e:
        logging.exception("Error in /agents")
        return jsonify({"error": str(e)}), 500


@app.route("/prompt_builder", methods=["POST"])
def build_prompt():
    payload = request.get_json() or {}

    question = payload.get("query", "")
    agentName = (payload.get("agentName", "") or "").lower()
    accountName = (payload.get("accountName", "") or "").lower()
    # keep request field name for now, but map to context_type
    context_type = payload.get("selectType", "") or payload.get("contextType", "")
    conversationId = payload.get("conversationId", "")

    # Optional: None means "no storage-based context"
    context_name = payload.get("contextName") or payload.get("context_name")
    if context_name is not None:
        context_name = str(context_name).strip() or None

    # allow optional list of extra system messages
    extra_system_messages = payload.get("extraSystemMessages") or []
    if not isinstance(extra_system_messages, list):
        extra_system_messages = [str(extra_system_messages)]

    if not question or not agentName or not accountName:
        return jsonify({"error": "Missing query, agentName, or accountName"}), 400

    if not agent_manager.is_valid(agentName):
        return jsonify({"error": "Invalid agentName"}), 400

    my_agent = agent_manager.get_agent(agentName)
    if not context_type:
        # default from agent config
        context_type = my_agent.context_type if my_agent else "hybrid"

    prompt_builder = PromptBuilder()

    prompt = prompt_builder.build_prompt(
        content_text=question,
        conversation_id=conversationId,
        agent_name=agentName,
        account_name=accountName,
        context_type=context_type,
        max_prompt_chars=payload.get("maxPromptChars", 6000),
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


@app.route("/documents/search", methods=["POST"])
def search_documents():
    """Search documents (e.g., Obsidian notes) using simple keyword matching."""
    data = request.get_json(silent=True) or {}

    account_name = (data.get("account_name", "") or "").lower()
    query = data.get("question") or data.get("q") or ""
    kind = data.get("kind")
    tag = data.get("tag")
    limit = int(data.get("limit", 10))

    if not account_name:
        return jsonify({"error": "Missing account_name"}), 400
    if not query.strip():
        return jsonify({"error": "Missing query"}), 400

    try:
        if not hasattr(storage, "search_documents_poor_man"):
            return jsonify(
                {"error": "Document search not supported by this storage backend"}
            ), 501

        results = storage.search_documents_poor_man(
            account_name=account_name,
            query=query,
            kind=kind,
            limit=limit,
            tag=tag,
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
