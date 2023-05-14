import time
def get_id() -> str:
        return str(time.time_ns())
    
def get_complete_path(base_path, agent_name, account_name):
        full_path = base_path + "/" + agent_name + "_" + account_name + "_conv.json"
        return full_path  