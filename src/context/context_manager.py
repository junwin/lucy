import os
import yaml
import pickle
import datetime

class ContextManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.context_base_path = self.config_manager.get('context_base_path')
        self.contexts = dict()
        self.current_context = None

    def get_account_base_path(self, account_name):
        return f"{self.context_base_path}/{account_name}"

    def get_context(self, account_name, context_name):
        base_path = self.get_account_base_path(account_name)
        context_file = os.path.join(base_path, f"{context_name}.dat")
        if os.path.exists(context_file):
            with open(context_file, 'rb') as file:
                #context = yaml.load(file, Loader=yaml.FullLoader)
                context= pickle.load(file)
                return context
        else:
            return None

    def post_context(self, context):
        base_path = self.get_account_base_path(context.account_name)
        context.last_updated_timestamp = datetime.datetime.utcnow()
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        context_file = os.path.join(base_path, f"{context.name}.dat")
        with open(context_file, 'wb') as file:
            pickle.dump(context, file)
            #yaml.dump(context, file)
            #file.write(context.context_formated_text())

    def put_context(self, context):
        base_path = self.get_account_base_path(context.account_name)
        context.last_updated_timestamp = datetime.datetime.utcnow()
        context_file = os.path.join(base_path, f"{context.name}.dat")
        if os.path.exists(context_file):
            with open(context_file, 'wb') as file:
                pickle.dump(context, file)

    def delete_context(self, account_name, context_name):
        base_path = self.get_account_base_path(account_name)
        context_file = os.path.join(base_path, f"{context_name}.yaml")
        if os.path.exists(context_file):
            os.remove(context_file)

    def save_context(self):
        base_path = self.get_account_base_path(self.account_name)
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        context_file = os.path.join(base_path, f"{self.name}.yaml")
        with open(context_file, 'w') as file:
            file.write(self.context_formated_text())

    def load_context(self, account_name, context_name):
        base_path = self.get_account_base_path(account_name)
        context_file = os.path.join(base_path, f"{context_name}.yaml")
        if os.path.exists(context_file):
            with open(context_file, 'r') as file:
                self.update_from_results(yaml.load(file, Loader=yaml.FullLoader))

