import json

from bs4 import BeautifulSoup
import requests
import selenium.webdriver.support.ui as ui

from constants.csx_terminals import terminals_dict
from database import get_containers_from_db, get_mbl_from_container
from utilities import start_headless_driver


containers_by_rail_dict = get_containers_from_db('Tracing View')
data_sources = json.load(open('data_config.json'))["data_sources"]
user_agent_header = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_1) AppleWebKit'
                                   '/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36'}


class BNSFScraper:
    def __init__(self):
        self.data_source = data_sources["bnsf"]
        self.containers_list = containers_by_rail_dict['BNSF']

    def get_formatted_containers_list(self):
        formatted_containers_list = []
        self.containers_list.sort()
        for container in self.containers_list:
            formatted_container = container[:4] + container[4:].lstrip('0')[:-1]
            formatted_containers_list.append(formatted_container)
        return formatted_containers_list

    def get_tracing_results_html(self):
        if self.containers_list:
            formatted_containers_list = self.get_formatted_containers_list()
            self.data_source['payload']['equipment'] = ','.join(formatted_containers_list)
            response = requests.post(self.data_source['api_url'], data=self.data_source['payload'])
            if response.status_code == 200:
                html = BeautifulSoup(response.content, 'html.parser')
                return html
            else:
                print('Response status code: {}'.format(response.status_code))
        else:
            print('No containers traveling on BNSF')


class CanadianNationalScraper:
    def __init__(self):
        self.data_source = data_sources["canadian_national"]
        self.containers_list = containers_by_rail_dict['CN']
        self.session = requests.Session()

    def __format_containers_list(self):
        return ''.join([container[:-1] for container in self.containers_list])

    def __get_html_dict(self):
        # Two different formats of API url are needed to collect all required data points
        formatted_containers_list = self.__format_containers_list()
        location_response = self.session.get(self.data_source['api_url'].format('HL', formatted_containers_list))
        eta_response = self.session.get(self.data_source['api_url'].format('HH', formatted_containers_list))
        location_html = BeautifulSoup(location_response.content, 'lxml')
        eta_html = BeautifulSoup(eta_response.content, 'lxml')
        return dict(location_html=location_html, eta_html=eta_html)

    def get_tracing_results_dict(self):
        tracing_results_dict = {}
        if self.containers_list:
            for container in self.containers_list:
                tracing_results_dict.update({container: []})
            containers_html_dict = self.__get_html_dict()
            for k, v in containers_html_dict.items():
                tracing_results_rows_list = v.text.split('\n')[5:5 + len(self.containers_list)]
                for i, container in enumerate(tracing_results_dict.keys()):
                    tracing_results_dict[container].append(tracing_results_rows_list[i])
            return tracing_results_dict
        else:
            print('No containers traveling on CN')


class CanadianPacificScraper:
    def __init__(self):
        self.data_source = data_sources["canadian_pacific"]
        self.driver = start_headless_driver()
        self.containers_list = containers_by_rail_dict['CP']

    def __format_containers_list(self):
        return '\n'.join(self.containers_list)

    def __login(self):
        self.driver.get(self.data_source['api_url']['login'])
        username_box = self.driver.find_element_by_id('username')
        password_box = self.driver.find_element_by_id('password')
        username_box.send_keys(self.data_source['credentials']['username'])
        password_box.send_keys(self.data_source['credentials']['password'])
        login_button = self.driver.find_element_by_class_name('login_button')
        login_button.click()

    def __input_containers_to_trace(self):
        self.driver.get(self.data_source['api_url']['tracing'])
        search_box_element = self.driver.find_element_by_name('paramValue3470')
        search_box_element.send_keys(self.__format_containers_list())
        lfd_button_element = self.driver.find_element_by_name('paramValue3478')
        lfd_button_element.click()
        tracing_submit_button = self.driver.find_element_by_xpath(
            '/html/body/table[2]/tbody/tr/td[2]/form/table/tbody/tr[15]/td/input[3]')
        tracing_submit_button.click()

    def get_tracing_results_html(self):
        if self.containers_list:
            self.__login()
            self.__input_containers_to_trace()
            wait = ui.WebDriverWait(self.driver, 10)
            wait.until(lambda driver: driver.find_element_by_id('rowTable'))
            return BeautifulSoup(self.driver.page_source, 'html.parser')
        else:
            print('No containers traveling on CP')


class CSXScraper:
    def __init__(self):
        self.data_source = data_sources["csx"]

    @staticmethod
    def get_containers_dict():
        containers_dict = {}
        for k, v in containers_by_rail_dict.items():
            if 'CSX' in k:
                for container in v:
                    containers_dict.update({container[:-1]: container})
        return containers_dict

    @staticmethod
    def __get_request_payload():
        payload = []

        for k, v in containers_by_rail_dict.items():
            if 'CSX' in k:
                payload_by_terminals = {
                    "terminal": {},
                    "shipmentData": []
                }
                terminal_key = k.split(' - ')[1]
                terminal_payload = terminals_dict[terminal_key]
                payload_by_terminals['terminal'].update(terminal_payload)
                for container in v:
                    mbl = get_mbl_from_container(container)
                    if 'CMDU' in mbl:
                        mbl = mbl[4:]
                    shipment_data_template = {
                        "equipmentID": {
                            "equipmentInitial": container[:4],
                            "equipmentNumber": container[4:-1]
                        },
                        "referenceNumber": mbl
                    }
                    payload_by_terminals['shipmentData'].append(shipment_data_template)
                payload.append(payload_by_terminals)

        return payload

    def get_tracing_results_list(self):
        payload = self.__get_request_payload()
        if payload:
            response = requests.post(self.data_source['api_url'], json=payload, headers=self.data_source['headers'])
            if response.status_code == 200:
                results_list = response.json()['shipments']
                for result in response.json()['failedSearchCriteria']:
                    results_list.append(result)
                return results_list
            else:
                print('Response status code: {}'.format(response.status_code))
        else:
            print('No containers traveling on CSX')


class NorfolkSouthernScraper:
    def __init__(self):
        self.session = requests.Session()
        self.data_source = data_sources["norfolk_southern"]
        self.containers_list = containers_by_rail_dict['NORFOLK SOUTHERN']

    def __login(self):
        self.session.headers.update(user_agent_header)
        self.session.headers.update({'Content-Type': 'application/json'})
        return self.session.post(self.data_source['api_url']['login'], json=self.data_source['credentials'])

    def __get_csrf_token(self):
        login_response = self.__login()
        if login_response.status_code == 200:
            login_results_dict = login_response.json()
            return login_results_dict['result']['token']
        else:
            print('Response status code: {}'.format(login_response.status_code))

    def get_tracing_results_list(self):
        if self.containers_list:
            tracing_results_list = []
            csrf_token = self.__get_csrf_token()
            self.session.headers.update({'CSRFTOKEN': csrf_token})
            for container in self.containers_list:
                response = self.session.post(self.data_source['api_url']['tracing'],
                                             json={"searchList": container})
                if response.status_code == 200:
                    tracing_results_list.append(response.json())
                else:
                    print('Response status code: {}'.format(response.status_code))

            return tracing_results_list
        else:
            print('No containers traveling on NS')


class UnionPacificScraper:
    def __init__(self):
        self.session = requests.Session()
        self.data_source = data_sources["union_pacific"]
        self.containers_list = containers_by_rail_dict['UP']

    def __get_request_token(self):
        response = self.session.post(self.data_source['token_url'],
                                     headers=self.data_source['headers'],
                                     data=self.data_source['payload'])
        if response.status_code == 200:
            token_dict = response.json()
            return token_dict['access_token']
        else:
            print('Response status code: {}'.format(response.status_code))

    def get_tracing_results_dict(self):
        if self.containers_list:
            request_token = self.__get_request_token()
            headers = {'Authorization': 'Bearer {}'.format(request_token)}
            url = self.data_source['api_url'].format(','.join(self.containers_list))
            response = self.session.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                print('Response status code: {}'.format(response.status_code))
        else:
            print('No containers traveling on UP')


