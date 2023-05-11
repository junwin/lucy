
import json

class ConfigManager:
    def __init__(self, file_name):
        self.config = self.load_config(file_name)

    def load_config(self, file_name):
        try:
            with open(file_name, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file '{file_name}' not found.")
            return {}

    def get(self, key, default=None):
        return self.config.get(key, default)