
import logging
import json

from pprint import pprint
import requests

from typing import List, Tuple
from src.handlers.handler import Handler
from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager
from src.handlers.quokka_loki import QuokkaLoki

endpoint = 'https://api.bing.microsoft.com/'+ "v7.0/search"

with open("G:/My Drive/credential/bing.json", "r") as config_file:
    config_data = json.load(config_file)

subscription_key = config_data["subscription_key"]

class WebSearchHandler(Handler):  # Concrete handler


    def handle(self, action: dict, account_name:str = "auto") -> List[dict]:
        action_name = action['action_name']
        if action_name != "action_websearch":
            return None
        
        print(action)
        logging.info(self.__class__.__name__ )
        
        query = action['query']
        result_type = 'webpages'
        if 'result_type' in action:
            node_type = action['result_type']

        result = self.bing_search(query, result_type)

        temp = [{"result": result},{ "handler": self.__class__.__name__} ]
        temp.append(action)
        return temp


    def bing_search(self, query: str, result_type: str) -> str:
        try:
          # Construct a request
            mkt = 'en-US'
            params = { 'q': query, 'mkt': mkt }
            headers = { 'Ocp-Apim-Subscription-Key': subscription_key }

            # Call the API
            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            result = self.get_results(data, result_type)
            return result


        except Exception as e:
            print(f"Error occurred while reading file: {e}")
            return str(e)

    def get_results(self, data, result_type):
    
        result = []
        result_type = result_type.lower()
        if result_type == 'webpages':
            result_type = 'webPages'
        if result_type in data:
            for item in data[result_type]['value']:
                result.append({
                    'url': item['url'],
                    'name': item['name'],
                    'description': item['snippet'] if result_type == 'webPages' else item['description']
                })
        return result
  

