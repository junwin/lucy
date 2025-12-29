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
args = parser.parse_args()


# Configure logging (same file as app.py for consistency)
logging.basicConfig(
    filename="logs/my_log_file.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Ensure agents are loaded (mirrors app.py behavior)
agent_manager = container.get(AgentManager)
agent_manager.load_agents()

# Reuse the same handler as the /ask endpoint
ask_handler = container.get(AskRequestHandler)


def role_play(agent_name: str, account_name: str):
    """Simple REPL for chatting with Lucy via the same logic as /ask.

    - On first message, we open a new chat session with a friendly name
      like "cli-YYYY-MM-DD".
    - We then reuse the returned conversation_id (UUID) for the rest of
      the REPL so messages are appended to the same session.

    Type 'exit', 'bye', 'quit', or 'adiós' to leave.
    """

    exit_words = ["adiós", "bye", "quit", "exit"]

    # Friendly name for this CLI run (visible in storage / UI)
    today = _dt.date.today().isoformat()
    default_friendly = f"cli-{today}"

    print(f"Lucy CLI - agent={agent_name}, account={account_name}")
    print("Type your message, or 'exit' to quit.")
    print(f"(This session will be stored as friendly_name='{default_friendly}')")

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
        # AskRequestHandler will create a new ChatSession.
        response, conversation_id = ask(
            message=user_input,
            agent_name=agent_name,
            account_name=account_name,
            conversation_id=conversation_id,
            friendly_name=default_friendly if conversation_id is None else None,
        )
        print(response)


def ask(
    message: str,
    agent_name: str,
    account_name: str,
    conversation_id: str | None = None,
    friendly_name: str | None = None,
) -> tuple[str, str | None]:
    """Call the same AskRequestHandler used by the /ask HTTP endpoint.

    - If conversation_id is None, a new chat session will be created.
    - If friendly_name is provided on that first call, it will be stored
      as ChatSession.friendly_name.

    Returns (answer_text, conversation_id).
    """

    payload = {
        # new snake_case API
        "message": message,
        "agent_name": agent_name,
        "account_name": account_name,
    }

    if conversation_id:
        payload["conversation_id"] = conversation_id
    if friendly_name:
        payload["friendly_name"] = friendly_name

    status, body = ask_handler.handle(payload)

    if status != 200 or not body.get("ok"):
        # Return a simple error string for CLI use; keep conversation_id
        # unchanged so the caller can decide what to do.
        return f"[error {status}] {body.get('error', 'Unknown error')}", conversation_id

    # AskRequestHandler returns {"ok": True, "answer": ..., "conversation_id": ...}
    return body.get("answer", ""), body.get("conversation_id")


# Use command line arguments for agentName and accountName
if __name__ == "__main__":
    role_play(args.agentName[0], args.accountName[0])
