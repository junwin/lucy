import logging
import argparse
import datetime as _dt

from src.container_config import container
from src.agent_manager import AgentManager
from src.message_endpoints.ask_request_handler import AskRequestHandler


# Set up command line argument parsing
parser = argparse.ArgumentParser(description="Lucy CLI")
parser.add_argument(
    "--agentName",
    metavar="agent",
    type=str,
    nargs=1,
    default=["doug"],
    help="the name of the agent",
)
parser.add_argument(
    "--accountName",
    metavar="account",
    type=str,
    nargs=1,
    default=["user_id"],
    help="the name of the account",
)
parser.add_argument(
    "--friendlyName",
    metavar="friendlyName",
    type=str,
    nargs=1,
    default=["zzzzz"],
    help="the friendly name of the session",
)
parser.add_argument(
    "--contextName",
    metavar="contextName",
    type=str,
    nargs=1,
    default=None,
    help="optional context name for storage-based context (e.g. a project name)",
)
parser.add_argument(
    "--query",
    metavar="query",
    type=str,
    nargs=1,
    default=None,
    help="a single query to process and then exit (non-interactive mode)",
)
args = parser.parse_args()


# Configure logging (same file as app.py for consistency)
logging.basicConfig(
    filename="logs/my_log_file.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Ensure agents are loaded (mirrors app.py behavior)
agent_manager = container.get(AgentManager)
agent_manager.load_agents()

# Reuse the same handler as the /ask endpoint
ask_handler = container.get(AskRequestHandler)


def role_play(agent_name: str, account_name: str, friendly_name: str, context_name: str | None = None) -> None:
    """Simple REPL for chatting with Lucy via the same logic as /ask.

    - On first message, we open a new chat session with a friendly name
      like "cli-YYYY-MM-DD" unless a friendly_name is provided.
    - We then reuse the returned conversation_id (UUID) for the rest of
      the REPL so messages are appended to the same session.

    Type 'exit', 'bye', 'quit', or 'adiós' to leave.
    """

    # Basic validation for required identifiers
    if not agent_name or not agent_name.strip():
        logger.error("Missing agent_name; cannot start CLI session")
        print("Error: agentName is required. Provide --agentName on the command line.")
        return
    if not account_name or not account_name.strip():
        logger.error("Missing account_name; cannot start CLI session")
        print("Error: accountName is required. Provide --accountName on the command line.")
        return

    exit_words = ["adiós", "bye", "quit", "exit"]

    # Friendly name for this CLI run (visible in storage / UI)
    today = _dt.date.today().isoformat()
    default_friendly = f"cli-{today}"

    # Use provided friendly_name if present, otherwise use default
    initial_friendly = (friendly_name.strip() if friendly_name and friendly_name.strip() else default_friendly)

    logger.info("Starting CLI role_play: agent=%s account=%s friendly=%s context=%s", agent_name, account_name, initial_friendly, context_name)

    print(f"Lucy CLI - agent={agent_name}, account={account_name}, friendly_name={initial_friendly}")
    print("Type your message, or 'exit' to quit.")
    print(f"(This session will be stored as friendly_name='{initial_friendly}')")

    conversation_id = None  # storage-backed id (UUID) once created

    while True:
        try:
            user_input = input(">> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if user_input.strip().lower() in exit_words:
            break

        # On first message, pass friendly_name and no conversation_id so
        # AskRequestHandler will create or look up a new ChatSession.
        # Do not overwrite the friendly_name provided by the caller.
        response, new_conversation_id = ask(
            message=user_input,
            agent_name=agent_name,
            account_name=account_name,
            conversation_id=conversation_id,
            friendly_name=initial_friendly,
            context_name=context_name,
        )

        # If a new conversation_id was returned, store it for subsequent messages
        if new_conversation_id:
            logger.info("Storing conversation_id for session: %s", new_conversation_id)
            conversation_id = new_conversation_id

        print(response)


def ask(
    message: str,
    agent_name: str,
    account_name: str,
    conversation_id: str | None = None,
    friendly_name: str | None = None,
    context_name: str | None = None,
) -> tuple[str, str | None]:
    """Call the same AskRequestHandler used by the /ask HTTP endpoint.

    - If conversation_id is None, a new chat session will be created or
      looked up by friendlyName.
    - If friendly_name is provided on that first call, it will be sent as
      "friendlyName" (camelCase) to match the HTTP endpoint.

    Returns (answer_text, conversation_id).
    """

    # Match the /ask handler's expected request schema (camelCase)
    payload = {
        "question": message,
        "agentName": agent_name,
        "accountName": account_name,
    }

    if conversation_id:
        payload["conversationId"] = conversation_id
    if friendly_name:
        payload["friendlyName"] = friendly_name
    if context_name:
        payload["contextName"] = context_name

    logger.info("Sending /ask payload: agent=%s account=%s conversationId=%s friendlyName=%s contextName=%s", agent_name, account_name, conversation_id, friendly_name, context_name)

    status, body = ask_handler.handle(payload)

    if status != 200:
        logger.warning("/ask returned status %s body=%s", status, body)
        # Return a simple error string for CLI use; keep conversation_id
        # unchanged so the caller can decide what to do.
        return f"[error {status}] { (body or {}).get('error', 'Unknown error')}", conversation_id

    # The handler should return a dict containing the response text and the conversation id.
    # Be flexible about key names to tolerate small differences between implementations.
    response_text = None
    for key in ("response", "answer", "text", "message"):
        if isinstance(body.get(key), str):
            response_text = body.get(key)
            break

    if response_text is None:
        # Fallback: try nested structures or default to empty string
        response_text = str(body.get("answer") or body.get("response") or "")

    conversation_id_returned = body.get("conversation_id") or body.get("conversationId") or body.get("conversationID")

    logger.info("/ask response: conversation_id=%s", conversation_id_returned)

    return response_text, conversation_id_returned


# Use command line arguments for agentName and accountName
if __name__ == "__main__":
    agent_name = args.agentName[0]
    account_name = args.accountName[0]
    friendly_name = args.friendlyName[0]

    # Extract optional contextName
    context_name = None
    if args.contextName is not None:
        context_name = args.contextName[0]

    if args.query is not None:
        # Single-query mode: process one message and exit
        query = args.query[0]
        logger.info("Single-query mode: agent=%s account=%s context=%s query=%s", agent_name, account_name, context_name, query)
        response, _ = ask(
            message=query,
            agent_name=agent_name,
            account_name=account_name,
            friendly_name=friendly_name,
            context_name=context_name,
        )
        print(response)
    else:
        # Interactive REPL mode
        role_play(agent_name, account_name, friendly_name, context_name)
