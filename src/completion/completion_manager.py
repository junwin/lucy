import json
from typing import List, Dict, Set, Optional

from datetime import datetime
import logging

from src.keywords import Keywords
from src.completion.completion import Completion
from src.completion.message import Message
from src.storage.base import Storage
from src.storage.models import ChatMessage, ChatSession


class CompletionManager:
    """
    Adapter that keeps the old CompletionManager API, but persists data using
    the new Storage / ChatSession layer instead of a flat JSON file.
    """
    def __init__(self, storage: Storage, agent_name: str, account_name: str, language_code: str = "en"):
        self.language_code = language_code
        self.keywords_util = Keywords(language_code)
        self.agent_name = agent_name
        self.account_name = account_name
        self.storage = storage

        # In-memory cache of Completion wrappers built from ChatSession objects
        self.completions: List[Completion] = []
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _session_to_completion(self, session: ChatSession) -> Completion:
        """Convert a ChatSession from storage into the older Completion model."""
        messages = [Message(m.role, m.content) for m in session.messages]
        total_chars = sum(len(m.content) for m in session.messages)
        # We treat the session friendly_name as the "conversation_id" if present
        conversation_id = session.friendly_name or session.id

        return Completion(
            id=session.id,
            utc_timestamp=session.created_at.isoformat() + "Z",
            total_chars=total_chars,
            messages=messages,
            tags=session.tags,
            conversation_id=conversation_id,
        )

    def _upsert_completion_from_session(self, session: ChatSession) -> None:
        """Update or insert a Completion wrapper corresponding to a session."""
        comp = self._session_to_completion(session)
        for i, existing in enumerate(self.completions):
            if existing.id == comp.id:
                self.completions[i] = comp
                break
        else:
            self.completions.append(comp)

    def _find_session_by_conversation_id(self, conversation_id: str) -> Optional[ChatSession]:
        """
        Find an existing ChatSession that corresponds to the given conversation_id.
        We map conversation_id <-> ChatSession.friendly_name.
        """
        self._ensure_loaded()
        for completion in self.completions:
            if completion.conversation_id == conversation_id:
                return self.storage.get_chat_session(completion.id)
        return None

    def _get_or_create_session(
        self,
        conversation_id: str,
        tags: Optional[List[str]] = None,
    ) -> ChatSession:
        """
        Resolve a conversation_id to a ChatSession.
        If no session exists, create a new one with friendly_name = conversation_id.
        """
        session = self._find_session_by_conversation_id(conversation_id)
        if session:
            return session

        logging.info(
            f"CompletionManager: creating new chat session "
            f"for account={self.account_name}, agent={self.agent_name}, "
            f"conversation_id={conversation_id}"
        )
        session = self.storage.create_chat_session(
            account_name=self.account_name,
            agent_name=self.agent_name,
            friendly_name=conversation_id,
            tags=tags or [],
        )
        self._upsert_completion_from_session(session)
        return session

    # ------------------------------------------------------------------
    # Legacy load/save API – now mapped to Storage
    # ------------------------------------------------------------------
    def save(self) -> None:
        """
        Legacy API. With the Storage layer, chat data is written as we go,
        so this becomes a no-op kept only for backwards compatibility.
        """
        logging.info("CompletionManager.save() called – no-op with Storage backend")

    def load(self) -> None:
        """
        Populate the in-memory completion cache from Storage.
        """
        logging.info(
            f"CompletionManager.load() from Storage for "
            f"account={self.account_name}, agent={self.agent_name}"
        )
        sessions = self.storage.list_chat_sessions(
            account_name=self.account_name,
            agent_name=self.agent_name,
            limit=1000,
        )
        self.completions = [self._session_to_completion(s) for s in sessions]
        self._loaded = True

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def get_completion(self, id: str) -> Optional[Completion]:
        self._ensure_loaded()
        for completion in self.completions:
            if completion.id == id:
                return completion
        return None

    def get_completion_byId(self, ids: List[str]) -> List[Completion]:
        self._ensure_loaded()
        completion_list = [c for c in self.completions if c.id in ids]
        completion_list.sort(key=lambda x: x.id)
        return completion_list

    # ------------------------------------------------------------------
    # Creation / mutation
    # ------------------------------------------------------------------
    def store_completion(self, completion: Completion) -> bool:
        """
        Legacy method that used to push an already-constructed Completion into memory.
        We now use it as a thin wrapper around insert_new_completion_messages.
        """
        messages_dicts = Message.get_list_of_dicts(completion.messages)
        conversation_id = completion.conversation_id or completion.id
        self.insert_new_completion_messages(messages_dicts, conversation_id)
        return True

    def create_store_completion(self, conversation_id: str, request: str, response: str) -> bool:
        """
        Legacy helper that creates a two-message completion (user + assistant).
        """
        request_message = {"role": "user", "content": request}
        response_message = {"role": "assistant", "content": response}
        self.insert_new_completion_messages([request_message, response_message], conversation_id)
        return True

    def update_completion(self, updated_completion: Completion) -> bool:
        """
        Full in-place update of a completion is not supported with the Storage
        abstraction (we only have append semantics). For now we update the
        in-memory cache and log a warning.
        """
        self._ensure_loaded()
        for i, completion in enumerate(self.completions):
            if completion.id == updated_completion.id:
                self.completions[i] = updated_completion
                logging.warning(
                    "CompletionManager.update_completion updated in-memory only – "
                    "Storage does not currently support full session rewrite."
                )
                return True
        return False

    def delete_completion(self, completion_id: str) -> bool:
        """
        Deleting a completion is not supported by the Storage abstraction yet,
        so we only remove it from the in-memory cache.
        """
        self._ensure_loaded()
        for index, completion in enumerate(self.completions):
            if completion.id == completion_id:
                del self.completions[index]
                logging.warning(
                    "CompletionManager.delete_completion removed in-memory only – "
                    "Storage does not currently support chat deletion."
                )
                return True
        return False

    def insert_new_completion_messages(self, messages: List[Dict[str, str]], conversationId: str) -> None:
        """
        Main entry point used by the rest of the codebase to record a new
        batch of messages for a given conversation.

        We:
          • derive tags/keywords for the new content
          • ensure there is a ChatSession backing this conversation_id
          • append messages to that session via Storage
          • refresh the in-memory Completion wrapper
        """
        # Derive keywords for tagging the session on first creation
        keywords: Set[str] = set()
        for message in messages:
            content = message["content"]
            # This used to use extract_from_content; we'll keep that behaviour
            keywords |= set(self.keywords_util.extract_from_content(content))

        # Get or create session for this conversation_id
        session = self._get_or_create_session(conversationId, tags=list(keywords))

        # Append each message via Storage
        for message in messages:
            chat_msg = ChatMessage(
                role=message["role"],
                content=message["content"],
            )
            self.storage.append_chat_message(session.id, chat_msg)

        # Reload this session and update cache
        updated_session = self.storage.get_chat_session(session.id)
        if updated_session:
            self._upsert_completion_from_session(updated_session)

    # ------------------------------------------------------------------
    # Search / query utilities (unchanged, but now operate on cache
    # backed by Storage)
    # ------------------------------------------------------------------
    def find_closest_completion_Ids(
        self,
        input_text: str,
        number_to_return: int = 2,
        min_similarity_threshold: float = 0,
    ) -> List[str]:
        self._ensure_loaded()
        completion_similarities = []
        tokenized_input_text = self.keywords_util.extract_from_content(input_text)

        for completion in self.completions:
            similarity = self.keywords_util.compare_keyword_lists_semantic_similarity(
                tokenized_input_text,
                completion.tags,
            )
            if similarity > min_similarity_threshold:
                completion_similarities.append((completion.id, similarity))

        sorted_completion_ids = sorted(
            completion_similarities,
            key=lambda x: x[1],
            reverse=False,
        )

        return [id_ for (id_, _) in sorted_completion_ids[:number_to_return]]

    def find_latest_completion_Ids(self, number_to_return: int) -> List[str]:
        self._ensure_loaded()
        if not self.completions:
            return []
        sliced_list = self.completions[-number_to_return:]
        return [completion.id for completion in sliced_list]

    def find_keyword_promptIds(
        self,
        content_text: str,
        match_operator: str,
        number_to_return: Optional[int] = None,
    ) -> List[str]:
        self._ensure_loaded()
        keywords = self.keywords_util.extract_from_content(content_text)
        matched_completion_ids: Set[str] = set()

        for completion in self.completions:
            if self.keywords_util.compare_keywords(keywords, completion.tags, match_operator):
                matched_completion_ids.add(completion.id)

        matched_ids_list = list(matched_completion_ids)
        if number_to_return is not None:
            return matched_ids_list[:number_to_return]
        return matched_ids_list

    def get_Ids_with_conversation_id(self, conversation_id: str) -> List[str]:
        self._ensure_loaded()
        matching_ids: List[str] = []
        for completion in self.completions:
            if completion.conversation_id == conversation_id:
                matching_ids.append(completion.id)
        return matching_ids

    def get_completion_messages(
        self,
        completionIds: List[str],
        roles: Optional[List[str]] = None,
    ) -> List[Message]:
        self._ensure_loaded()
        if roles is None:
            roles = ["user", "assistant", "system"]

        completions = self.get_completion_byId(completionIds)
        messages: List[Message] = []
        for completion in completions:
            for message in completion.messages:
                if message.role in roles:
                    messages.append(message)
        return messages

    def get_default_roles(self) -> List[str]:
        return ["user", "assistant", "system"]

    def get_transcript(
        self,
        completionIds: List[str],
        roles: Optional[List[str]] = None,
        user_intro: str = "User: ",
        assistant_intro: str = "Assistant: ",
    ) -> str:
        if roles is None:
            roles = self.get_default_roles()
        response_text = ""
        for completion in self.get_completion_byId(completionIds):
            text = completion.format_completion_text(roles, user_intro, assistant_intro)
            if len(text) > 0:
                response_text += text + "\n"
        return response_text

    def get_formatted_conversations(
        self,
        completionIds: List[str],
        roles: Optional[List[str]] = None,
    ) -> str:
        if roles is None:
            roles = self.get_default_roles()
        response_text = ""
        user_intro = "User: "
        assistant_intro = "Assistant: "

        for completion in self.get_completion_byId(completionIds):
            text = completion.format_completion_text(roles, user_intro, assistant_intro)
            if len(text) > 0:
                response_text += text + "\n"
        return response_text

    def get_distinct_conversation_ids(self) -> List[str]:
        self._ensure_loaded()
        conversation_ids = set()
        for completion in self.completions:
            conversation_ids.add(completion.conversation_id)
        return list(conversation_ids)

    def change_conversation_id(self, old_id: str, new_id: str) -> None:
        """
        Update the conversation_id (which maps to ChatSession.friendly_name).
        This only updates the in-memory Completion wrappers; renaming the
        underlying chat is left to the storage layer if/when needed.
        """
        self._ensure_loaded()
        for completion in self.completions:
            if completion.conversation_id == old_id:
                completion.conversation_id = new_id
