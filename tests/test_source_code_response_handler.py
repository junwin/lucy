import os
import re
import json
from typing import Dict, Any
from response_handler import ResponseHandler
from source_code_response_handler import SourceCodeResponseHandler


class TestSourceCodeResponseHandler:
    def test_extract_json_object(self):
        handler = SourceCodeResponseHandler("")
        text = "some text {\"key\": \"value\"} some more text"
        expected = {"key": "value"}
        assert handler.extract_json_object(text) == expected

    def test_extract_source_code(self):
        handler = SourceCodeResponseHandler("")
        text = "{\"output_file_path\": \"zz.py\"}\nimport os\nprint (\"hello world\")"
        expected = "import os\nprint (\"hello world\")"
        assert handler.extract_source_code(text) == expected


    def test_save_test_code_no_filename(self, tmpdir):
        handler = SourceCodeResponseHandler(str(tmpdir))
        response = "{\"output_file_path\": null}\nimport os\nprint (\"hello world\")"
        expected = "Error: Filename not found."
        assert handler.save_test_code(response, str(tmpdir)) == expected

    def test_save_test_code_no_source_code(self, tmpdir):
        handler = SourceCodeResponseHandler(str(tmpdir))
        response = "{\"output_file_path\": \"test_file.py\"}\n"
        expected = "Error: Source code not found."
        assert handler.save_test_code(response, str(tmpdir)) == expected