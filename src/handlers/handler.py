

class Handler:  # Abstract handler
    def handle(self, request, account_name:str = "auto"):
        pass
    def get_function_calling_definition(self) -> str:
        pass
