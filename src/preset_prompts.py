import json


class PresetPrompts:

    def __init__(self, file_name: str = 'prompts.json'):
        self.file_name = file_name
        self.prompts = []
        self.load()

    def load(self):
        try:
            with open(self.file_name, 'r') as f:
                self.prompts = json.load(f)
        except FileNotFoundError:
            return {}

    def save(self):
        with open(self.file_name, 'w') as f:
            json.dump(self.prompts, f, indent=2)

    def add_prompt(self, name, prompt):
        self.prompts[name] = prompt

    def get_prompt(self, name: str):
        return self.prompts.get(name)

    def remove_prompt(self, name):
        if name in self.prompts:
            del self.prompts[name]
