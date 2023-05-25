
def get_base_path(config, account_name:str, relative_path: str = '')-> str:

    base_path = config.get('code_sandbox_path')
    base_path = base_path + '/' + 'account_name' + '/' + relative_path + '/'
    return base_path
