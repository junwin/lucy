from flask import Flask, request, jsonify, send_file, make_response, Response
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
from src.message_processors.sse_events import SSEEvent
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.http_endpoints.agents_endpoints import (
    get_agents_impl,
)
from src.http_endpoints.context_endpoints import (
    list_context_names_impl,
)
from src.http_endpoints.tasklist_endpoints import (
    list_tasklists_impl,
    get_tasklist_impl,
    put_tasklist_impl,
    delete_tasklist_impl,
)
from src.http_endpoints.prompt_builder_endpoints import build_prompt_impl
from src.http_endpoints.prompt_builder_debug_endpoints import prompt_builder_debug_impl
from src.http_endpoints.prompt_builder_metrics_endpoints import prompt_builder_metrics_impl
from src.http_endpoints.documents_endpoints import search_documents_impl
from src.http_endpoints.chats_endpoints import (
    post_chat_impl,
    get_chats_impl,
    get_chat_impl,
    post_chat_message_impl,
    delete_chat_impl,
    update_chat_impl,
)
from src.http_endpoints.upload_endpoints import post_upload_image_impl
from src.chat2.facade import Chat2Store
from src.api_key import validate_api_key


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
        maxBytes=5_000_000,  # ~5MB
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
chat2_store = container.get(Chat2Store)


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


@app.before_request
def _check_api_key() -> None:
    """Validate API key on every request (except Swagger UI static routes and OPTIONS preflight).

    Reads X-API-Key header and checks against config. If validation fails,
    the request is aborted with a 401 response.
    """
    # Skip API key check for Swagger UI static assets, the spec file, and CORS preflight
    if request.path.startswith("/api/docs") or request.path == "/swagger.json":
        return
    if request.method == "OPTIONS":
        return

    # Admin reload endpoint is special — it always uses the live config for key checking
    # so that after a reload, the next request uses the new keys.

    # Extract key from X-API-Key header, fallback to Authorization: Bearer
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]

    valid, key_name = validate_api_key(config, api_key)
    if not valid:
        logging.warning(
            "API key rejected for path=%s method=%s",
            request.path,
            request.method,
        )
        # Store the rejection flag so after_request can set the status
        request._api_key_rejected = True  # type: ignore[attr-defined]


@app.after_request
def _enforce_api_key(response):
    """If the API key check failed, override the response to 401."""
    if getattr(request, "_api_key_rejected", False):
        response = jsonify({"error": "Unauthorized. Provide a valid API key via X-API-Key header."})
        response.status_code = 401
    return response


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

    Supports two code paths:
      - stream=true: SSE streaming via AskRequestHandler.handle_streaming()
      - default:     existing JSON response via AskRequestHandler.handle()
    """
    payload = request.get_json() or {}
    account_name = payload.get("accountName")

    if not account_name:
        return jsonify({"error": "accountName is required"}), 400

    try:
        user_profile = storage.get_user_profile(account_name)
    except Exception:
        logging.exception("/ask: failed to load user profile for user_id=%s", account_name)
        return jsonify({"error": "An error occurred"}), 500

    if user_profile is None:
        logging.info("/ask: user profile not found for user_id=%s", account_name)
        return jsonify({"error": f"Unknown account '{account_name}'"}), 403

    if not user_profile.active:
        logging.info("/ask: inactive account for user_id=%s", account_name)
        return jsonify({"error": f"Account '{account_name}' is inactive"}), 403

    ask_handler = container.get(AskRequestHandler)

    # ── Streaming path (new) ──
    if payload.get("stream"):
        def generate():
            try:
                for sse_line in ask_handler.handle_streaming(payload):
                    yield sse_line.encode("utf-8") if isinstance(sse_line, str) else sse_line
            except Exception as e:
                logging.exception("/ask(streaming): unhandled error in generator")
                error_event = SSEEvent(type="error", message=str(e))
                yield f"data: {error_event.model_dump_json()}\n\n".encode("utf-8")

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # ── Existing non-streaming path ──
    # conversation/session resolution: if no conversationId was provided,
    # try to resolve using a friendlyName (payload: friendlyName) or create
    # a new chat session.
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

                            # Also create chat2 session with the same session_id
                            if chat2_store is not None:
                                try:
                                    chat2_store.create_session(
                                        user_id=account_name,
                                        account_name=account_name,
                                        agent_name=agent_name,
                                        session_id=conv_id,
                                        friendly_name=friendly_name,
                                    )
                                    logging.info(
                                        "/ask: created chat2 session id=%s for friendlyName=%s account=%s agent=%s",
                                        conv_id,
                                        friendly_name,
                                        account_name,
                                        agent_name,
                                    )
                                except Exception:
                                    logging.exception(
                                        "/ask: failed to create chat2 session for friendlyName=%s account=%s agent=%s",
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

    status, body = ask_handler.handle(payload)

    # Ensure response body includes conversation_id for client convenience.
    try:
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
    body, status = list_context_names_impl(storage, account_name)
    return jsonify(body), status




# -----------------------------------------------------------------------------
# TaskLists CRUD (Span 3)
# -----------------------------------------------------------------------------


@app.route("/tasklists", methods=["GET"])
def list_tasklists():
    account_name = (request.args.get("accountName") or "").strip()
    body, status = list_tasklists_impl(storage, account_name)
    return jsonify(body), status


@app.route("/tasklists/<tasklist_name>", methods=["GET"])
def get_tasklist(tasklist_name: str):
    account_name = (request.args.get("accountName") or "").strip()
    body, status = get_tasklist_impl(storage, account_name, tasklist_name)
    return jsonify(body), status


@app.route("/tasklists/<tasklist_name>", methods=["PUT"])
def put_tasklist(tasklist_name: str):
    account_name = (request.args.get("accountName") or "").strip()
    payload = request.get_json(silent=True)
    body, status = put_tasklist_impl(storage, account_name, tasklist_name, payload)
    return jsonify(body), status


@app.route("/tasklists/<tasklist_name>", methods=["DELETE"])
def delete_tasklist(tasklist_name: str):
    account_name = (request.args.get("accountName") or "").strip()
    body, status = delete_tasklist_impl(storage, account_name, tasklist_name)
    return jsonify(body), status


@app.route("/agents", methods=["GET"])
def get_agents():
    body, status = get_agents_impl(agent_manager)
    return jsonify(body), status


@app.route("/prompt_builder", methods=["POST"])
def build_prompt():
    payload = request.get_json() or {}
    body, status = build_prompt_impl(agent_manager, storage, container, config, payload)
    return jsonify(body), status



@app.route("/prompt_builder/debug", methods=["POST"])
def prompt_builder_debug():
    payload = request.get_json() or {}
    body, status = prompt_builder_debug_impl(storage, config, payload)
    return jsonify(body), status


@app.route("/prompt_builder/metrics", methods=["POST"])
def prompt_builder_metrics():
    payload = request.get_json(force=True, silent=True) or {}
    body, status = prompt_builder_metrics_impl(agent_manager, storage, container, config, payload)
    return jsonify(body), status


@app.route("/chats", methods=["POST"])
def post_chat():
    body, status = post_chat_impl(chat2_store, agent_manager, request.json or {})
    return jsonify(body), status


@app.route("/chats", methods=["GET"])
def get_chats():
    agentName = (request.args.get("agentName", "") or "").lower()
    accountName = (request.args.get("accountName", "") or "").lower()
    limit = int(request.args.get("limit", "50"))

    body, status = get_chats_impl(chat2_store, agent_manager, agentName, accountName, limit)
    return jsonify(body), status


@app.route("/chats/<session_id>", methods=["GET"])
def get_chat(session_id: str):
    body, status = get_chat_impl(chat2_store, session_id)
    return jsonify(body), status


@app.route("/chats/<session_id>/messages", methods=["POST"])
def post_chat_message(session_id: str):
    data = request.get_json() or {}
    body, status = post_chat_message_impl(chat2_store, session_id, data)
    return jsonify(body), status


# New stubs for future chat management
@app.route("/chats/<session_id>", methods=["DELETE"])
def delete_chat(session_id: str):
    body, status = delete_chat_impl(chat2_store, session_id)
    return jsonify(body), status


@app.route("/chats/<session_id>", methods=["PATCH"])
def update_chat(session_id: str):
    payload = request.get_json(silent=True) or {}
    body, status = update_chat_impl(chat2_store, session_id, payload)
    return jsonify(body), status


@app.route("/documents/search", methods=["POST"])
def search_documents():
    data = request.get_json(silent=True) or {}
    body, status = search_documents_impl(storage, data)
    return jsonify(body), status


# -----------------------------------------------------------------------------
# Image upload
# -----------------------------------------------------------------------------
@app.route("/upload/image", methods=["POST"])
def upload_image():
    """Accept an image file via multipart form-data.

    Form fields:
      file:         the image (required)
      accountName:  account identifier (required)

    Returns:
      200: { ok, id, filename, mime_type }
      400: validation error
      413: file too large
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    account_name = (request.form.get("accountName") or "").strip()

    file_data = file.read()
    body, status = post_upload_image_impl(
        config=config,
        account_name=account_name,
        file_data=file_data,
        original_filename=file.filename or "unnamed",
        mime_type=file.content_type or "application/octet-stream",
    )
    return jsonify(body), status


# -----------------------------------------------------------------------------
# Admin endpoint: reload config and agents at runtime
# -----------------------------------------------------------------------------
@app.route("/admin/reload", methods=["POST"])
def admin_reload():
    """Reload config.json and agents.json without restarting the process.

    Returns:
        200 with summary: {config_reloaded, keys_added, keys_removed,
                           keys_changed, agents_loaded, agent_names}
        500 if config reload fails (old state kept).
    """
    # 1. Reload config in-place
    config_summary = config.reload()

    if not config_summary.get("config_reloaded"):
        # Config reload failed — old state is preserved
        return jsonify({
            "error": "Config reload failed. Old config preserved.",
            "detail": config_summary.get("error", "Unknown error"),
        }), 500

    # 2. Reload agents from the (potentially changed) agents_path
    strict = config.get("strict_agent_fields", True)
    old_agent_names = agent_manager.get_agent_names()
    agent_manager.load_agents(strict=strict)
    new_agent_names = agent_manager.get_agent_names()

    agents_added = sorted(set(new_agent_names) - set(old_agent_names))
    agents_removed = sorted(set(old_agent_names) - set(new_agent_names))

    logging.info(
        "/admin/reload: agents reloaded. added=%s, removed=%s, total=%d",
        agents_added, agents_removed, len(new_agent_names),
    )

    return jsonify({
        "config_reloaded": config_summary["config_reloaded"],
        "keys_added": config_summary.get("keys_added", []),
        "keys_removed": config_summary.get("keys_removed", []),
        "keys_changed": config_summary.get("keys_changed", []),
        "agents_loaded": len(new_agent_names),
        "agent_names": new_agent_names,
        "agents_added": agents_added,
        "agents_removed": agents_removed,
    }), 200


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
    app.run(
        host=config.get("host", "0.0.0.0"),
        port=config.get("port", 5000),
        debug=config.get("debug", True),
        use_reloader=False,
    )
