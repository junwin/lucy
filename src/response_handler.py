import os
from abc import ABC, abstractmethod
import os
import re


class ResponseHandler(ABC):
    @abstractmethod
    def handle_response(self, agent_name:str, response) ->str:
        pass


class FileResponseHandler(ResponseHandler):
    def __init__(self, account_output_path:str, max_length=500):
        self.max_length = max_length
        self.output_folder = account_output_path

    def handle_response(self, agent_name:str, response: str) ->str:
        if len(response) > self.max_length:
            account_folder = os.path.join(self.output_folder, agent_name)
            #file_path = os.path.join( account_folder, f"{agent_name}.html")
            if not os.path.exists( account_folder):
                os.makedirs( account_folder)

            output_file_path = os.path.join(account_folder, f"response_{len(os.listdir(account_folder)) + 1}.txt")
            #self.text_to_html(response, output_file_path)

            with open(output_file_path, "w", encoding="utf-8") as output_file:
                output_file.write(response)

            url = self.generate_url(output_file_path)

            return f"Response is too long. It has been saved to {url}"
        else:
            return response
        


    def text_to_html(self, text, file_name="output.html"):
        html_template = """<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Simple HTML</title>
    </head>
    <body>
        <pre>{}</pre>
    </body>
    </html>
    """

        with open(file_name, "w", encoding="utf-8") as file:
            file.write(html_template.format(text))

    def generate_url(self, file_path: str, base_url: str = "http://127.0.0.1:5000") -> str:
        url = f"{base_url}/{file_path}"
        return url