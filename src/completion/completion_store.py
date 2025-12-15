import logging
from injector import inject
from src.completion.completion_manager import CompletionManager
from src.storage.base import Storage


class CompletionStore:
    """
    Simple cache of CompletionManager instances, now backed by the shared
    Storage abstraction instead of a raw base_path.
    """

    @inject
    def __init__(self, storage: Storage):
        self.storage = storage
        self.completion_managers = dict()

    def get_manager_id(self, agent_name: str, account_name: str) -> str:
        return f"{agent_name}_{account_name}"

    def get_completion_manager(
        self,
        agent_name: str,
        account_name: str,
        language_code: str = "en",
    ) -> CompletionManager:
        manager_id = self.get_manager_id(agent_name, account_name)
        logging.info(f"CompletionStore get: {manager_id}")

        manager = self.completion_managers.get(manager_id)
        if manager is None:
            manager = CompletionManager(
                storage=self.storage,
                agent_name=agent_name,
                account_name=account_name,
                language_code=language_code,
            )
            # Warm the cache from Storage (mirrors old load() behaviour)
            manager.load()
            self.completion_managers[manager_id] = manager

        return manager
