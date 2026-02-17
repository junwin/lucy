import inspect

from src.storage.json_file_storage import JsonFileStorage


def test_json_file_storage_chat_methods_delegate_to_chats_module():
    # Guardrail: if someone later inlines logic back into JsonFileStorage,
    # this test should fail.
    expected_method_names = [
        "create_chat_session",
        "find_chat_sessions_by_friendly_name",
        "get_chat_session",
        "list_chat_sessions",
        "rename_chat_session",
        "update_chat_session",
        "append_chat_message",
        "delete_chat_session",
        "_chat_dict_to_session",
    ]

    for method_name in expected_method_names:
        method = getattr(JsonFileStorage, method_name)
        assert inspect.isfunction(method)

        src = inspect.getsource(method)
        assert f"return chats.{method_name}" in src
