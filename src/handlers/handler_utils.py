
def get_base_path(config, account_name:str, relative_path: str = '')-> str:

    relative_path = relative_path.replace('~', '')   # we wlays use the the config to determine the base path
    base_path = config.get('code_sandbox_path')
    base_path = base_path + '/' + account_name + '/' + relative_path + '/'
    return base_path
