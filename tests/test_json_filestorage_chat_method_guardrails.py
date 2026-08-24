from src.storage.json_file_storage import JsonFileStorage


def _v1_chat_method_names() -> list[str]:
    return [
        "create" + "_chat_session",
        "find" + "_chat_sessions_by_friendly_name",
        "get" + "_chat_session",
        "list" + "_chat_sessions",
        "rename" + "_chat_session",
        "update" + "_chat_session",
        "append" + "_chat_message",
        "delete" + "_chat_session",
        "_chat" + "_dict_to_session",
    ]


def test_json_file_storage_has_no_v1_chat_methods():
    # Guardrail: if someone later re-adds v1 chat methods to JsonFileStorage,
    # this test should fail.
    for method_name in _v1_chat_method_names():
        assert not hasattr(JsonFileStorage, method_name)
