from injector import Module, provider, singleton

from src.config_manager import ConfigManager
from src.agent_manager import AgentManager
from src.storage.base import Storage

from src.tasklists.store import TaskListStore
from src.tasklists.orchestrator import TaskListOrchestrator
from src.tasklists.summary import TaskListSummarizer
from src.tasklists.service import TaskListService


class TaskListsModule(Module):
    @provider
    @singleton
    def provide_tasklist_store(self, storage: Storage, config: ConfigManager) -> TaskListStore:
        return TaskListStore(storage=storage, config=config)

    @provider
    @singleton
    def provide_tasklist_summarizer(self) -> TaskListSummarizer:
        return TaskListSummarizer()

    @provider
    @singleton
    def provide_tasklist_orchestrator(
        self,
        agent_manager: AgentManager,
        store: TaskListStore,
        config: ConfigManager,
    ) -> TaskListOrchestrator:
        return TaskListOrchestrator(agent_manager=agent_manager, store=store, config=config)

    @provider
    @singleton
    def provide_tasklist_service(
        self,
        store: TaskListStore,
        orchestrator: TaskListOrchestrator,
        summarizer: TaskListSummarizer,
    ) -> TaskListService:
        return TaskListService(store=store, orchestrator=orchestrator, summarizer=summarizer)
