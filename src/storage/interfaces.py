from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional

from .models import Context, Skill


class ContextStore(ABC):
    @abstractmethod
    def get_context(self, account_name: str, context_id: str) -> Optional[Context]:
        """Load a context, resolve imports, and return a fully-resolved Context."""
        pass

    @abstractmethod
    def get_or_create_context(
        self,
        account_name: str,
        context_id: str,
    ) -> Context:
        """Fetch a context, creating + saving it if missing."""
        pass

    @abstractmethod
    def save_context(self, context: Context) -> None:
        """Insert or update a context (persisted fields only; derived fields ignored)."""
        pass

    def list_context_names(self, account_name: str) -> List[str]:
        """List context names for an account.

        Minimal contract:
        - Return the filename stem for each "*.json" file under
          "contexts/<account_name>/" in storage.
        - Return an empty list if the account has no contexts or does not exist.
        - Results should be stable and deterministic (implementations should
          sort by name ascending).

        This is intentionally non-abstract for backward compatibility with
        older/custom Storage implementations.
        """

        return []

    def get_skill(self, account_name: str, skill_name: str) -> Optional[Skill]:
        """Return a skill (frontmatter + body), or None if missing.

        Skills are stored as Markdown files at skills/<account>/<name>.md.
        This is non-abstract so custom Storage implementations can opt in
        without breaking (default: no skills).
        """
        return None

    def get_skill_text(self, account_name: str, skill_name: str) -> Optional[str]:
        """Return the body text of a skill file, or None if missing.

        Backward-compat wrapper: delegates to get_skill().text so custom
        Storage implementations only need to implement get_skill().
        """
        skill = self.get_skill(account_name, skill_name)
        if skill is None:
            return None
        return skill.text


class HealthCheckable(ABC):
    @abstractmethod
    def health_check(self) -> bool:
        """Quick check that storage is reachable."""
        pass
