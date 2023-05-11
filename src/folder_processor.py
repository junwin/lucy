import os
from typing import Optional

class FolderProcessor:
    def __init__(self, input_folder: str, file_type: Optional[str], handler):
        self.input_folder = input_folder
        self.file_type = file_type
        self.handler = handler

    def process_folder(self):
        # Check if the input folder exists
        if not os.path.exists(self.input_folder):
            print(f"Error: input folder does not exist: {self.input_folder}")
            return

        try:
            # Loop through all the files in the directory
            for file_name in os.listdir(self.input_folder):
                # If file_type is specified, skip files with different extensions
                if self.file_type and not file_name.endswith(self.file_type):
                    continue
                
                # Build the full file path
                file_path = os.path.join(self.input_folder, file_name)

                # Only process files, not subdirectories
                if not os.path.isfile(file_path):
                    continue
                
                # Open the file and read its content
                with open(file_path, 'r') as file:
                    content = file.read()
                
                # Pass the content and the file name to the handler
                self.handler.handle_response(content, file_name)

        except Exception as e:
            print(f"Error while processing folder: {str(e)}")
