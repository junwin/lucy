
from typing import List,  Tuple
from src.handlers.handler import Handler
from src.handlers.file_save_handler import FileSaveHandler
from src.handlers.command_execution_handler import CommandExecutionHandler
from src.handlers.task_update_handler import TaskUpdateHandler
from src.handlers.user_action_required_handler import UserActionRequiredHandler
from src.handlers.file_load_handler import FileLoadHandler

class QuokkaLoki:
    def __init__(self):
        self.handlers = [FileSaveHandler(), CommandExecutionHandler(), TaskUpdateHandler(), UserActionRequiredHandler(), FileLoadHandler()]  

    def process_request(self, request:str)-> List[Tuple[str, str]]:
        results = []
        for handler in self.handlers:
            try:
                result = handler.handle(request)
                if result is not None:
                    results.append( result)
            except Exception as e:
                results +=f"An error occurred while processing the request with {handler.__class__.__name__}: {e}"
        
        return (self.__class__.__name__, results)