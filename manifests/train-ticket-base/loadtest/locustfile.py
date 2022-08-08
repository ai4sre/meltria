import json
import logging
import os
import random
import string
import sys
import time
from datetime import datetime, timedelta
from random import randint, uniform

import locust
import locust.stats
from locust import (HttpUser, between, constant, constant_throughput, events,
                    task)
from locust.env import Environment
from requests.adapters import HTTPAdapter

from locustfile_dataset import TRIP_DATA, USER_CREDETIALS

HTTP_REQUEST_TIMEOUT = 5
state_data = []  # for debugging purposes


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument(
        "--verbose-logging", action='store_true', env_var="LOCUST_VERBOSE_LOGGING",
        help="Enable verbose logging output")


def random_string_generator():
    len = randint(8, 16)
    prob = randint(0, 100)
    if prob < 25:
        random_string = ''.join([random.choice(string.ascii_letters) for n in range(len)])
    elif prob < 50:
        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(len)])
    elif prob < 75:
        random_string = ''.join(
            [random.choice(string.ascii_letters + string.digits + string.punctuation) for n in range(len)])
    else:
        random_string = ''
    return random_string


def random_date_generator():
    temp = randint(0, 4)
    random_y = 2000 + temp * 10 + randint(0, 9)
    random_m = randint(1, 12)
    random_d = randint(1, 31)  # assumendo che la data possa essere non sensata (e.g. 30 Febbraio)
    return str(random_y) + '-' + str(random_m) + '-' + str(random_d)


def postfix(expected=True):
    if expected:
        return '_expected'
    return '_unexpected'


def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days_ahead)


def get_departure_date(before_date: str = ''):
    if before_date == '':
        tomorrow = datetime.now() + timedelta(1)
        return tomorrow.strftime("%Y-%m-%d")
    next_day = datetime.strptime(before_date, "%Y-%m-%d") + timedelta(days=1)
    return next_day.strftime("%Y-%m-%d")


class Requests:

    def __init__(self, client, verbose_logging: bool = False):
        self.client = client
        user = random.choice(USER_CREDETIALS)
        self.user_name = user
        self.password = user
        self.trip_detail = random.choice(TRIP_DATA)
        self.food_detail = {}
        self.departure_date = get_departure_date()

        if verbose_logging:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s:%(message)s'))
            handler.setLevel(logging.DEBUG)
            logger = logging.getLogger("Debugging logger")
            logger.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            self.debugging_logger = logger
        else:
            self.debugging_logger = None

    def log_verbose(self, to_log):
        if self.debugging_logger is not None:
            self.debugging_logger.debug(json.dumps(to_log))

    def home(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get('/index.html', name=req_label) as response:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time}
            self.log_verbose(to_log)

    def try_to_read_response_as_json(self, response):
        try:
            return response.json()
        except:
            try:
                return response.content.decode('utf-8')
            except:
                return response.content

    def search_ticket(self, expected):
        logging.debug("search ticket")
        stations = ["Shang Hai", "Tai Yuan", "Nan Jing", "Wu Xi", "Su Zhou", "Shang Hai Hong Qiao", "Bei Jing",
                    "Shi Jia Zhuang", "Xu Zhou", "Ji Nan", "Hang Zhou", "Jia Xing Nan", "Zhen Jiang"]
        from_station, to_station = random.sample(stations, 2)
        departure_date = self.departure_date
        head = {"Accept": "application/json",
                "Content-Type": "application/json"}
        body_start = {
            "startingPlace": from_station,
            "endPlace": to_station,
            "departureTime": departure_date
        }
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        response = self.client.post(
            url="/api/v1/travelservice/trips/left",
            headers=head,
            json=body_start,
            name=req_label)
        if not response.json()["data"]:
            response = self.client.post(
                url="/api/v1/travel2service/trips/left",
                headers=head,
                json=body_start,
                name=req_label)
        to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                  'response_time': time.time() - start_time,
                  'response': self.try_to_read_response_as_json(response)}
        self.log_verbose(to_log)

    # def search_departure(self, expected):
    #     logging.info("search_departure")
    #     stations = ["Shang Hai", "Tai Yuan", "Nan Jing", "Wu Xi", "Su Zhou", "Shang Hai Hong Qiao", "Bei Jing",
    #                 "Shi Jia Zhuang", "Xu Zhou", "Ji Nan", "Hang Zhou", "Jia Xing Nan", "Zhen Jiang"]
    #     from_station, to_station = random.sample(stations, 2)
    #     if expected:
    #         self.search_ticket(date.today().strftime(random_date_generator()), from_station, to_station, expected)
    #     else:
    #         self.search_ticket(date.today().strftime(random_date_generator()), random_string_generator(), "Su Zhou",
    #                            expected)

    def _login_as_admin(self) -> str:
        req_label = sys._getframe().f_code.co_name
        response = self.client.post(
            url="/api/v1/users/login",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"username": "admin", "password": "222222"},
            name=req_label,
        )
        response_as_json = response.json()["data"]
        if response_as_json is not None:
            token = response_as_json["token"]
            return token
        return ""

    def _create_user(self, expected):
        admin_token: str = self._login_as_admin()

        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        document_num = random.randint(1, 5)  # added by me
        with self.client.post(
            url="/api/v1/adminuserservice/users",
            headers={
                "Authorization": f"Bearer {admin_token}", "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json={
                "documentNum": document_num, "documentType": 0, "email": "string", "gender": 0,
                "password": self.password, "userName": self.user_name,
            },
            name=req_label,
        ) as response2:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response2.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response2)}
            self.log_verbose(to_log)

    def _navigate_to_client_login(self, expected=True):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get('/client_login.html', name=req_label) as response:
            to_log = {'name': req_label, 'expected': True, 'status_code': response.status_code,
                      'response_time': time.time() - start_time}
            self.log_verbose(to_log)

    def login(self, expected):
        self._create_user(expected=expected)
        self._navigate_to_client_login()
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        head = {"Accept": "application/json",
                "Content-Type": "application/json"}
        if (expected):
            response = self.client.post(url="/api/v1/users/login",
                                        headers=head,
                                        json={
                                            "username": self.user_name,
                                            "password": self.password
                                        }, name=req_label)
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)
        else:
            response = self.client.post(url="/api/v1/users/login",
                                        headers=head,
                                        json={
                                            "username": self.user_name,
                                            # wrong password
                                            "password": random_string_generator()
                                        }, name=req_label)
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

        response_as_json = response.json()["data"]
        if response_as_json is not None:
            token = response_as_json["token"]
            self.bearer = "Bearer " + token
            self.user_id = response_as_json["userId"]

    # purchase ticket

    def start_booking(self, expected):
        departure_date = self.departure_date
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get(
                url="/client_ticket_book.html?tripId=" + self.trip_detail["trip_id"] + "&from=" + self.trip_detail[
                    "from"] +
                    "&to=" + self.trip_detail["to"] + "&seatType=" + self.trip_detail["seat_type"] + "&seat_price=" +
                    self.trip_detail["seat_price"] +
                    "&date=" + departure_date,
                headers=head,
                name=req_label) as response:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time}
            self.log_verbose(to_log)

    def get_assurance_types(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get(
                url="/api/v1/assuranceservice/assurances/types",
                headers=head,
                name=req_label) as response:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

    def get_foods(self, expected):
        departure_date = self.departure_date
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        with self.client.get(
                url="/api/v1/foodservice/foods/" + departure_date + "/" + self.trip_detail["from"] + "/" +
                    self.trip_detail["to"] + "/" + self.trip_detail["trip_id"],
                headers=head,
                name=req_label) as response:
            # resp_data = response.json()
            # if resp_data["data"]:
            #     if random.uniform(0, 1) <= 0.5:
            #         self.food_detail = {"foodType": 2,
            #                             "foodName": resp_data["data"]["trainFoodList"][0]["foodList"][0]["foodName"],
            #                             "foodPrice": resp_data["data"]["trainFoodList"][0]["foodList"][0]["price"]}
            #     else:
            #         self.food_detail = {"foodType": 1,
            #                             "foodName": resp_data["data"]["foodStoreListMap"][self.trip_detail["from"]][0][
            #                                 "foodList"][0]["foodName"],
            #                             "foodPrice": resp_data["data"]["foodStoreListMap"][self.trip_detail["from"]][0][
            #                                 "foodList"][0]["price"]}
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

    def select_contact(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        response_contacts = self.client.get(
            url="/api/v1/contactservice/contacts/account/" + self.user_id,
            headers=head,
            name=req_label)
        to_log = {'name': req_label, 'expected': expected, 'status_code': response_contacts.status_code,
                  'response_time': time.time() - start_time,
                  'response': self.try_to_read_response_as_json(response_contacts)}
        self.log_verbose(to_log)

        response_as_json_contacts = response_contacts.json()["data"]

        if len(response_as_json_contacts) == 0:
            req_label = 'set_new_contact' + postfix(expected)
            response_contacts = self.client.post(
                url="/api/v1/contactservice/contacts",
                headers=head,
                json={
                    "name": self.user_id, "accountId": self.user_id, "documentType": "1",
                    "documentNumber": self.user_id, "phoneNumber": "123456"},
                name=req_label)

            response_as_json_contacts = response_contacts.json()["data"]
            self.contactid = response_as_json_contacts["id"]
        else:
            self.contactid = response_as_json_contacts[0]["id"]

    def finish_booking(self, expected):
        departure_date = self.departure_date
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        if (expected):
            body_for_reservation = {
                "accountId": self.user_id,
                "contactsId": self.contactid,
                "tripId": self.trip_detail["trip_id"],
                "seatType": self.trip_detail["seat_type"],
                "date": departure_date,
                "from": self.trip_detail["from"],
                "to": self.trip_detail["to"],
                "assurance": random.choice(["0", "1"]),
                "foodType": 1,
                "foodName": "Bone Soup",
                "foodPrice": 2.5,
                "stationName": "",
                "storeName": ""
            }
            if self.food_detail:
                body_for_reservation["foodType"] = self.food_detail["foodType"]
                body_for_reservation["foodName"] = self.food_detail["foodName"]
                body_for_reservation["foodPrice"] = self.food_detail["foodPrice"]
        else:
            body_for_reservation = {
                "accountId": self.user_id,
                "contactsId": self.contactid,
                "tripId": random_string_generator(),
                "seatType": "2",
                "date": departure_date,
                "from": "Shang Hai",
                "to": "Su Zhou",
                "assurance": "0",
                "foodType": 1,
                "foodName": "Bone Soup",
                "foodPrice": 2.5,
                "stationName": "",
                "storeName": ""
            }
        start_time = time.time()
        with self.client.post(
                url="/api/v1/preserveservice/preserve",
                headers=head,
                json=body_for_reservation,
                catch_response=True,
                name=req_label) as response:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

    def select_order(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        response_order_refresh = self.client.post(
            url="/api/v1/orderservice/order/refresh",
            name=req_label,
            headers=head,
            json={
                "loginId": self.user_id, "enableStateQuery": "false", "enableTravelDateQuery": "false",
                "enableBoughtDateQuery": "false", "travelDateStart": "null", "travelDateEnd": "null",
                "boughtDateStart": "null", "boughtDateEnd": "null"})

        to_log = {'name': req_label, 'expected': expected, 'status_code': response_order_refresh.status_code,
                  'response_time': time.time() - start_time,
                  'response': self.try_to_read_response_as_json(response_order_refresh)}
        self.log_verbose(to_log)

        response_as_json = response_order_refresh.json()["data"]
        if response_as_json:
            self.order_id = response_as_json[0]["id"]  # first order with paid or not paid
            self.paid_order_id = response_as_json[0]["id"]  # default first order with paid or unpaid.
        else:
            self.order_id = "sdasdasd"  # no orders, set a random number
            self.paid_order_id = "asdasdasn"
        # selecting order with payment status - not paid.
        for orders in response_as_json:
            if orders["status"] == 0:
                self.order_id = orders["id"]
                break
        for orders in response_as_json:
            if orders["status"] == 1:
                self.paid_order_id = orders["id"]
                break

    def pay(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if not self.order_id:
            to_log = {'name': req_label, 'expected': expected, 'status_code': "N/A",
                      'response_time': time.time() - start_time,
                      'response': "Place an order first!"}
            self.log_verbose(to_log)
            return
        if (expected):
            with self.client.post(
                    url="/api/v1/inside_pay_service/inside_payment",
                    headers=head,
                    json={"orderId": self.order_id, "tripId": "D1345"},
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)
        else:
            with self.client.post(
                    url="/api/v1/inside_pay_service/inside_payment",
                    headers=head,
                    json={"orderId": random_string_generator(), "tripId": "D1345"},
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)

    # cancelNoRefund

    def cancel_with_no_refund(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if (expected):
            with self.client.get(
                    url="/api/v1/cancelservice/cancel/" + self.order_id + "/" + self.user_id,
                    headers=head,
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)

        else:
            with self.client.get(
                    url="/api/v1/cancelservice/cancel/" + self.order_id + "/" + random_string_generator(),
                    headers=head,
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)

    # user refund with voucher

    def get_voucher(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if (expected):
            with self.client.post(
                    url="/getVoucher",
                    headers=head,
                    json={"orderId": self.order_id, "type": 1},
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time,
                          'response': self.try_to_read_response_as_json(response)}
                self.log_verbose(to_log)

        else:
            with self.client.post(
                    url="/getVoucher",
                    headers=head,
                    json={"orderId": random_string_generator(), "type": 1},
                    name=req_label) as response:
                to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                          'response_time': time.time() - start_time}
                self.log_verbose(to_log)

    # consign ticket

    def get_consigns(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        with self.client.get(
                url="/api/v1/consignservice/consigns/order/" + self.order_id,
                headers=head,
                name=req_label) as response:
            to_log = {'name': req_label, 'expected': expected, 'status_code': response.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response)}
            self.log_verbose(to_log)

    def confirm_consign(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if (expected):
            response_as_json_consign = self.client.put(
                url="/api/v1/consignservice/consigns",
                name=req_label,
                json={
                    "accountId": self.user_id,
                    "handleDate": self.departure_date,
                    "from": self.trip_detail["from"],
                    "to": self.trip_detail["to"],
                    "orderId": self.order_id,
                    "consignee": self.order_id,
                    "phone": ''.join([random.choice(string.digits) for n in range(8)]),
                    "weight": "1",
                    "id": "",
                    "isWithin": "false"},
                headers=head)
            to_log = {'name': req_label, 'expected': expected, 'status_code': response_as_json_consign.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response_as_json_consign)}
            self.log_verbose(to_log)
        else:
            response_as_json_consign = self.client.put(
                url="/api/v1/consignservice/consigns",
                name=req_label,
                json={
                    "accountId": self.user_id,
                    "handleDate": self.departure_date,
                    "from": "Shang Hai",
                    "to": "Su Zhou",
                    "orderId": self.order_id,
                    "consignee": random_string_generator(),
                    "phone": random_string_generator(),
                    "weight": "1",
                    "id": "",
                    "isWithin": "false"}, headers=head)
            to_log = {'name': req_label, 'expected': expected, 'status_code': response_as_json_consign.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response_as_json_consign)}
            self.log_verbose(to_log)

    def collect_ticket(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if expected:
            response_as_json_collect_ticket = self.client.get(
                url="/api/v1/executeservice/execute/collected/" + self.paid_order_id,
                name=req_label,
                headers=head)
            to_log = {'name': req_label, 'expected': expected,
                      'status_code': response_as_json_collect_ticket.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response_as_json_collect_ticket)}
            self.log_verbose(to_log)

    def enter_station(self, expected):
        head = {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": self.bearer}
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        start_time = time.time()
        if expected:
            response_as_json_enter_station = self.client.get(
                url="/api/v1/executeservice/execute/execute/" + self.paid_order_id,
                name=req_label,
                headers=head)
            to_log = {'name': req_label, 'expected': expected,
                      'status_code': response_as_json_enter_station.status_code,
                      'response_time': time.time() - start_time,
                      'response': self.try_to_read_response_as_json(response_as_json_enter_station)}
            self.log_verbose(to_log)

    def perform_task(self, name):
        name_without_suffix = name.replace("_expected", "").replace("_unexpected", "")
        task = getattr(self, name_without_suffix)
        task(name.endswith('_expected'))


class UserOnlyLogin(HttpUser):
    weight = 1
    # wait_function = random.expovariate(1) * 1000
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount("https://", HTTPAdapter(pool_maxsize=50))
        self.client.mount("http://", HTTPAdapter(pool_maxsize=50))

    @task()
    def perform_task(self):
        logging.debug("User home -> login")
        request = Requests(self.client, verbose_logging=self.environment.parsed_options.verbose_logging)
        number = uniform(0.0, 1.0)
        if number < 0.98:
            tasks_sequence = ["login_expected"]
        else:
            tasks_sequence = ["login_unexpected"]
        for tasks in tasks_sequence:
            request.perform_task(tasks)


class UserNoLogin(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))

    @task
    def perfom_task(self):
        logging.debug("Running user 'only search'...")

        task_sequence = ["home_expected", "search_ticket_expected"]

        requests = Requests(self.client, verbose_logging=self.environment.parsed_options.verbose_logging)
        for task in task_sequence:
            requests.perform_task(task)


class UserBooking(HttpUser):
    weight = 1
    # wait_function = random.expovariate(1)
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))

    @task
    def perform_task(self):
        logging.debug("Running user 'booking'...")

        task_sequence = ["home_expected",
                         "login_expected",
                         "search_ticket_expected",
                         "start_booking_expected",
                         "get_assurance_types_expected",
                         "get_foods_expected",
                         "select_contact_expected",
                         "finish_booking_expected"]
        # task_sequence = ["login_expected", "select_contact_expected", "finish_booking_expected"]

        requests = Requests(self.client, verbose_logging=self.environment.parsed_options.verbose_logging)
        for task in task_sequence:
            requests.perform_task(task)


class UserConsignTicket(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))

    @task
    def perform_task(self):
        logging.debug("Running user 'consign ticket'...")
        task_sequence = [
            "home_expected",
            "login_expected",
            "select_contact_expected",
            "finish_booking_expected",
            "select_order_expected",
            "get_consigns_expected",
            "confirm_consign_expected",
        ]

        requests = Requests(self.client, verbose_logging=self.environment.parsed_options.verbose_logging)
        for task in task_sequence:
            requests.perform_task(task)


class UserPay(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))

    @task
    def perform_task(self):
        logging.debug("Running user 'booking'...")

        task_sequence = ["home_expected",
                         "login_expected",
                         "select_contact_expected",
                         "finish_booking_expected",
                         "select_order_expected",
                         "pay_expected"]

        requests = Requests(self.client, verbose_logging=self.environment.parsed_options.verbose_logging)
        for task in task_sequence:
            requests.perform_task(task)


class UserCancelNoRefund(HttpUser):
    weight = 0
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))

    @task
    def perform_task(self):
        logging.debug("Running user 'cancel no refund'...")

        task_sequence = [
            "home_expected",
            "login_expected",
            "select_order_expected",
            "cancel_with_no_refund_expected",
        ]

        requests = Requests(self.client, verbose_logging=self.environment.parsed_options.verbose_logging)
        for task in task_sequence:
            requests.perform_task(task)


class UserCollectTicket(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))

    @task
    def perform_task(self):
        logging.debug("Running user 'collect ticket'...")

        task_sequence = [
            "home_expected",
            "login_expected",
            "select_order_expected",
            "pay_expected",
            "collect_ticket_expected",
        ]

        requests = Requests(self.client, verbose_logging=self.environment.parsed_options.verbose_logging)
        for task in task_sequence:
            requests.perform_task(task)


"""
Events for printing all requests into a file.
"""


class Print:  # pylint: disable=R0902
    """
    Record every response (useful when debugging a single locust)
    """

    def __init__(self, env: locust.env.Environment, include_length=False, include_time=False):
        self.env = env
        self.env.events.request_success.add_listener(self.request_success)

    def request_success(self, request_type, name, response_time, response_length, **_kwargs):
        users = self.env.runner.user_count
        data = [datetime.now(), request_type, name, response_time, users]
        state_data.append(data)


@events.init.add_listener
def locust_init_listener(environment, **kwargs):
    Print(env=environment)
