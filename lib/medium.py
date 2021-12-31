import os, json
from requests import Session
import logging 
from dataclasses import dataclass, asdict
from typing import List


MEDIUM_TOKEN = os.environ['MEDIUM_TOKEN']

@dataclass()
class MediumUser:
    id :         str
    username :   str
    name :       str
    url :        str
    imageUrl :   str

@dataclass()
class MediumPublication:
    id:	        str     #	A unique identifier for the publication.
    name:	    str     #	The publication’s name on Medium.
    description:str	    #   Short description of the publication
    url:        str     #	The URL to the publication’s homepage
    imageUrl:   str 	#	The URL to the publication’s image/logo

class MediumStats():
    token = MEDIUM_TOKEN
    protocol = "https://"
    host_url = "medium.com"
    base_url = protocol + host_url
    url = base_url
    session = Session()
    session.headers.update({
        "Authorization": "Bearer " + token,
        "Content-Type" :  "application/json",
        "Accept" : "application/json",
        "Accept-Charset": "utf-8"
     })

    def __init__(self,logger=""):
        self.logger = logging.getLogger(logger)

    def _request(self, path):
        r = self.session.get(self.url + path)
        if r.status_code != 200:
            self.logger.warn("Request Failed", r.request.headers)
        print(r.content)
        json_data = json.loads(r.content)
        return json_data

class MediumClient():
    token = MEDIUM_TOKEN
    protocol = "https://"
    host_url = "api.medium.com"
    base_url = protocol + host_url
    api_version  = "v1"
    url = base_url + "/" + api_version
    session = Session()
    session.headers.update({
        "Authorization": "Bearer " + token,
        "Content-Type" :  "application/json",
        "Accept" : "application/json",
        "Accept-Charset": "utf-8"
     })


    def __init__(self,logger=""):
        self.logger = logging.getLogger(logger)
    def _request(self,path):
        r = self.session.get(self.url + path)
        if r.status_code != 200:
            self.logger.warn("Request Failed", r.request.headers)
        json_data = json.loads(r.content)
        return json_data

    def me(self) -> MediumUser:
        resp = self._request("/me")
        return MediumUser(**resp['data'])

    def publications(self,user_id = "") -> List[MediumPublication] :
        resp = self._request(f"/users/{user_id}/publications")
        data = resp["data"]
        publications = [MediumPublication(**pub) for pub in data]
        return publications

from selenium import webdriver
import shutil
import uuid

class MediumCrawler():

    def __init__(self):
        self.__id = uuid.uuid4()
        self.__setup()
        self.options = self.__get_default_chrome_options()
        self.options.add_argument('--window-size={}x{}'.format(1280, 1024))

        self.driver = webdriver.Chrome(chrome_options = self.options)
    
    def __setup(self):    
        self._tmp_folder = '/tmp/{}'.format(self.__id)

        if not os.path.exists(self._tmp_folder):
            os.makedirs(self._tmp_folder)

        if not os.path.exists(self._tmp_folder + '/user-data'):
            os.makedirs(self._tmp_folder + '/user-data')

        if not os.path.exists(self._tmp_folder + '/data-path'):
            os.makedirs(self._tmp_folder + '/data-path')

        if not os.path.exists(self._tmp_folder + '/cache-dir'):
            os.makedirs(self._tmp_folder + '/cache-dir')

    def __get_default_chrome_options(self):
        chrome_options = webdriver.ChromeOptions()

        # chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--user-data-dir={}'.format(self._tmp_folder + '/user-data'))
        chrome_options.add_argument('--enable-logging')
        chrome_options.add_argument('--log-level=0')
        chrome_options.add_argument('--v=99')
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--data-path={}'.format(self._tmp_folder + '/data-path'))
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--homedir={}'.format(self._tmp_folder))
        chrome_options.add_argument('--disk-cache-dir={}'.format(self._tmp_folder + '/cache-dir'))
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36')

        chrome_options.binary_location = os.getcwd() + "/chromedriver" 

        return chrome_options    

    def close(self):
        # Remove specific tmp dir of this "run"
        shutil.rmtree(self._tmp_folder)

        # Remove possible core dumps
        folder = '/tmp'
        for the_file in os.listdir(folder):
            file_path = os.path.join(folder, the_file)
            try:
                if 'core.headless-chromi' in file_path and os.path.exists(file_path) and os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(e)
    

if __name__ == "__main__": 
    mc = MediumClient()
    me = mc.me()
    pubs = mc.publications(me.id)
    ms = MediumStats()
    r = ms._request("/me/stats?format=json")
