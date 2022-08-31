import json
import logging
import random
import string
import sys
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

ORDER_STATUS_BOOKED = 0
ORDER_STATUS_PAID = 1
ORDER_STATUS_COLLECTED = 2
ORDER_STATUS_CANCELLED = 4
ORDER_STATUS_EXECUTED = 6


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument(
        "--verbose-logging", action='store_true', env_var="LOCUST_VERBOSE_LOGGING",
        help="Enable verbose logging output")
    parser.add_argument(
        "--num-tasks-per-signup", type=int, env_var="LOCUST_NUM_TASKS_PER_SIGNUP", default=10,
        help="The number of tasks per signup")


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


def random_date_after_today():
    today = datetime.now()
    random_date = today + timedelta(days=randint(1, 180))
    return random_date.strftime("%Y-%m-%d")


def next_day_from_date(date):
    date = datetime.strptime(date, "%Y-%m-%d")
    next_day = date + timedelta(days=1)
    return next_day.strftime("%Y-%m-%d")


class TrainTicketError(Exception):
    "Base class for Train Ticket"
    def __init__(self, msg: str = ''):
        self.msg = msg


class TrainTicketNotFoundDataError(TrainTicketError):
    "Error if response has no data"
    def __str__(self):
        return f"Response has no 'data' key: {self.msg}"


class TrainTicketNoOrderError(TrainTicketError):
    "Error with no order in train ticket"
    def __str__(self):
        return f"Train Ticket has no order: {self.msg}"


class Requests:

    def __init__(self, client, user: str = '', signup: bool = True, verbose_logging: bool = False):
        self.client = client
        if user == '':
            user = random.choice(USER_CREDETIALS)
        self.user_name = user
        self.password = user
        self.user_signup = signup
        self.trip_detail = random.choice(TRIP_DATA)
        self.food_detail = {}
        # Order records retrieved in the backend (ts-order-service) gradually increases
        # if deprature_date is a static value.
        self.departure_date = random_date_after_today()

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

    def log_request(self, req_label: str, expected: bool, response, json: bool = False):
        to_log = {
            'name': req_label, 'expected': expected, 'status_code': response.status_code,
            'response_time': response.elapsed.total_seconds(),
        }
        if json:
            to_log['response'] = self.try_to_read_response_as_json(response)
        self.log_verbose(to_log)

    def log_request_as_json(self, req_label: str, expected: bool, response):
        self.log_request(req_label, expected, response, json=True)

    def json_header(self) -> dict[str, str]:
        return {"Accept": "application/json", "Content-Type": "application/json"}

    def json_header_with_auth(self, bearer: str = '') -> dict[str, str]:
        if bearer == '':
            bearer = self.bearer
        return {"Accept": "application/json",
                "Content-Type": "application/json", "Authorization": bearer}

    def home(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        with self.client.get('/index.html', name=req_label) as response:
            self.log_request(req_label, expected, response)

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
        body_start = {
            "startingPlace": from_station,
            "endPlace": to_station,
            "departureTime": departure_date
        }
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        response = self.client.post(
            url="/api/v1/travelservice/trips/left",
            headers=self.json_header(),
            json=body_start,
            name=req_label)
        if not response.json().get('data'):
            response = self.client.post(
                url="/api/v1/travel2service/trips/left",
                headers=self.json_header(),
                json=body_start,
                name=req_label)
        self.log_request_as_json(req_label, expected, response)

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
        with self.client.post(
            url="/api/v1/users/login",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"username": "admin", "password": "222222"},
            name=req_label,
        ) as response:
            self.log_request_as_json(req_label, True, response)
            response_as_json = response.json().get('data')
            if response_as_json is not None:
                token = response_as_json["token"]
                return token
        return ""

    def _create_user(self, expected):
        admin_token: str = self._login_as_admin()

        req_label = sys._getframe().f_code.co_name + postfix(expected)
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
            self.log_request_as_json(req_label, expected, response2)

    def _navigate_to_client_login(self, expected=True):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        with self.client.get('/client_login.html', name=req_label) as response:
            self.log_request(req_label, expected, response)

    def verify_code(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        with self.client.get(url='/api/v1/verifycode/generate', name=req_label) as response:
            self.log_request_as_json(req_label, expected, response)

    def login(self, expected):
        if self.user_signup:
            self._create_user(expected=expected)
        self._navigate_to_client_login()
        self.verify_code(expected)

        req_label = sys._getframe().f_code.co_name + postfix(expected)
        headers = {
            'Origin': self.client.base_url,
            'Referer': f"{self.client.base_url}/client_login.html",
        }
        headers.update(self.json_header())
        if (expected):
            response = self.client.post(url="/api/v1/users/login",
                                        verify=False,
                                        headers=headers,
                                        json={
                                            "username": self.user_name,
                                            "password": self.password,
                                            "verificationCode": "1234",
                                        }, name=req_label)
            self.log_request_as_json(req_label, expected, response)
        else:
            response = self.client.post(url="/api/v1/users/login",
                                        verify=False,
                                        headers=headers,
                                        json={
                                            "username": self.user_name,
                                            # wrong password
                                            "password": random_string_generator(),
                                            "verificationCode": "1234",
                                        }, name=req_label)
            self.log_request_as_json(req_label, expected, response)

        response_as_json = response.json().get('data')
        if response_as_json is None:
            raise TrainTicketNotFoundDataError(req_label)
        token = response_as_json["token"]
        self.bearer = "Bearer " + token
        self.user_id = response_as_json["userId"]

    # purchase ticket

    def start_booking(self, expected):
        departure_date = self.departure_date
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        with self.client.get(
                url="/client_ticket_book.html?tripId=" + self.trip_detail["trip_id"] +
                    "&from=" + self.trip_detail["from"] +
                    "&to=" + self.trip_detail["to"] + "&seatType=" + self.trip_detail["seat_type"] +
                    "&seat_price=" + self.trip_detail["seat_price"] +
                    "&date=" + departure_date,
                headers=self.json_header_with_auth(),
                name=req_label) as response:
            self.log_request(req_label, expected, response)

    def get_assurance_types(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        with self.client.get(
                url="/api/v1/assuranceservice/assurances/types",
                headers=self.json_header_with_auth(),
                name=req_label) as response:
            self.log_request_as_json(req_label, expected, response)

    def get_foods(self, expected):
        departure_date = self.departure_date
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        with self.client.get(
                url="/api/v1/foodservice/foods/" + departure_date + "/" + self.trip_detail["from"] + "/" +
                    self.trip_detail["to"] + "/" + self.trip_detail["trip_id"],
                headers=self.json_header_with_auth(),
                name=req_label) as response:
            self.log_request_as_json(req_label, expected, response)
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

    def select_contact(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        response_contacts = self.client.get(
            url="/api/v1/contactservice/contacts/account/" + self.user_id,
            headers=self.json_header_with_auth(),
            name=req_label)
        self.log_request_as_json(req_label, expected, response_contacts)

        response_as_json_contacts = response_contacts.json().get('data')
        if response_as_json_contacts is None:
            raise TrainTicketNotFoundDataError(req_label)

        if len(response_as_json_contacts) == 0:
            req_label = 'set_new_contact' + postfix(expected)
            response_contacts = self.client.post(
                url="/api/v1/contactservice/contacts",
                headers=self.json_header_with_auth(),
                json={
                    "name": self.user_id, "accountId": self.user_id, "documentType": "1",
                    "documentNumber": self.user_id, "phoneNumber": "123456"},
                name=req_label)
            self.log_request_as_json(req_label, expected, response_contacts)

            response_as_json_contacts = response_contacts.json().get('data')
            if response_as_json_contacts is None:
                raise TrainTicketNotFoundDataError(req_label)
            self.contactid = response_as_json_contacts["id"]
        else:
            self.contactid = response_as_json_contacts[0]["id"]

    def finish_booking(self, expected):
        departure_date = self.departure_date
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        if expected:
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
        with self.client.post(
                url="/api/v1/preserveservice/preserve",
                headers=self.json_header_with_auth(),
                json=body_for_reservation,
                catch_response=True,
                name=req_label) as response:
            self.log_request_as_json(req_label, expected, response)

    def select_order(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        response_order_refresh = self.client.post(
            url="/api/v1/orderservice/order/refresh",
            name=req_label,
            headers=self.json_header_with_auth(),
            json={
                "loginId": self.user_id, "enableStateQuery": "false", "enableTravelDateQuery": "false",
                "enableBoughtDateQuery": "false", "travelDateStart": "null", "travelDateEnd": "null",
                "boughtDateStart": "null", "boughtDateEnd": "null"})

        self.log_request_as_json(req_label, expected, response_order_refresh)

        response_as_json: dict | None = response_order_refresh.json().get("data")
        if response_as_json is None:
            raise TrainTicketNotFoundDataError(req_label)
        if response_as_json:
            self.order_id = response_as_json[0]["id"]  # first order with paid or not paid
            self.paid_order_id = response_as_json[0]["id"]  # default first order with paid or unpaid.
        else:
            raise TrainTicketNoOrderError()
        # selecting order with payment status - not paid.
        for orders in response_as_json:
            if orders["status"] == ORDER_STATUS_BOOKED:
                self.order_id = orders["id"]
                break
        for orders in response_as_json:
            if orders["status"] == ORDER_STATUS_PAID:
                self.paid_order_id = orders["id"]
                self.trip_id = orders["trainNumber"]
                break

    def pay(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        if not self.order_id:
            to_log = {
                'name': req_label, 'expected': expected, 'status_code': "N/A",
                'response_time': 0.0, 'response': "Place an order first!",
            }
            self.log_verbose(to_log)
            return None
        if (expected):
            with self.client.post(
                    url="/api/v1/inside_pay_service/inside_payment",
                    headers=self.json_header_with_auth(),
                    json={"orderId": self.order_id, "tripId": "D1345"},
                    name=req_label,
            ) as response:
                self.log_request_as_json(req_label, expected, response)
        else:
            with self.client.post(
                    url="/api/v1/inside_pay_service/inside_payment",
                    headers=self.json_header_with_auth(),
                    json={"orderId": random_string_generator(), "tripId": "D1345"},
                    name=req_label) as response:
                self.log_request_as_json(req_label, expected, response)

    # cancelNoRefund
    def cancel_with_no_refund(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        if (expected):
            with self.client.get(
                    url="/api/v1/cancelservice/cancel/" + self.order_id + "/" + self.user_id,
                    headers=self.json_header_with_auth(),
                    name=req_label) as response:
                self.log_request_as_json(req_label, expected, response)

        else:
            with self.client.get(
                    url="/api/v1/cancelservice/cancel/" + self.order_id + "/" + random_string_generator(),
                    headers=self.json_header_with_auth(),
                    name=req_label) as response:
                self.log_request_as_json(req_label, expected, response)

    # user refund with voucher

    def get_voucher(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        if (expected):
            with self.client.post(
                    url="/getVoucher",
                    headers=self.json_header_with_auth(),
                    json={"orderId": self.order_id, "type": 1},
                    name=req_label) as response:
                self.log_request_as_json(req_label, expected, response)
        else:
            with self.client.post(
                    url="/getVoucher",
                    headers=self.json_header_with_auth(),
                    json={"orderId": random_string_generator(), "type": 1},
                    name=req_label) as response:
                self.log_request(req_label, expected, response)

    # consign ticket
    def get_consigns(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        with self.client.get(
                url="/api/v1/consignservice/consigns/order/" + self.order_id,
                headers=self.json_header_with_auth(),
                name=req_label) as response:
            self.log_request_as_json(req_label, expected, response)

    def confirm_consign(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
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
                headers=self.json_header_with_auth())
            self.log_request_as_json(req_label, expected, response_as_json_consign)
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
                    "isWithin": "false"}, headers=self.json_header_with_auth())
            self.log_request_as_json(req_label, expected, response_as_json_consign)

    def collect_ticket(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        if expected:
            response_as_json_collect_ticket = self.client.get(
                url="/api/v1/executeservice/execute/collected/" + self.paid_order_id,
                name=req_label,
                headers=self.json_header_with_auth())
            self.log_request_as_json(req_label, expected, response_as_json_collect_ticket)

    def enter_station(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        if expected:
            response_as_json_enter_station = self.client.get(
                url="/api/v1/executeservice/execute/execute/" + self.paid_order_id,
                name=req_label,
                headers=self.json_header_with_auth())
            self.log_request_as_json(req_label, expected, response_as_json_enter_station)

    def rebook(self, expected):
        req_label = sys._getframe().f_code.co_name + postfix(expected)
        if expected:
            new_date = next_day_from_date(self.departure_date)
            with self.client.post(
                url="/api/v1/rebookservice/rebook",
                json={
                    "oldTripId": self.trip_detail['trip_id'],
                    "orderId": self.order_id,
                    "tripId": self.trip_detail['trip_id'],
                    "date": new_date,
                    "seatType": self.trip_detail['seat_type'],
                },
                name=req_label,
                headers=self.json_header_with_auth(),
            ) as response:
                self.log_request_as_json(req_label, expected, response)

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
        self.current_user: str = ''
        self.task_count: int = 0

    @task()
    def perform_task(self):
        logging.debug("User home -> login")

        if self.task_count % self.environment.parsed_options.num_tasks_per_signup == 0:
            self.current_user = random.choice(USER_CREDETIALS)
        self.task_count += 1

        request = Requests(
            self.client,
            user=self.current_user,
            verbose_logging=self.environment.parsed_options.verbose_logging,
        )
        number = uniform(0.0, 1.0)
        if number < 0.98:
            tasks_sequence = ["login_expected"]
        else:
            tasks_sequence = ["login_unexpected"]
        run_task_sequence(request, tasks_sequence)


class UserNoLogin(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))
        self.current_user: str = ''
        self.task_count: int = 0

    @task
    def perfom_task(self):
        logging.debug("Running user 'only search'...")

        if self.task_count % self.environment.parsed_options.num_tasks_per_signup == 0:
            self.current_user = random.choice(USER_CREDETIALS)
        self.task_count += 1

        request = Requests(
            self.client,
            user=self.current_user,
            verbose_logging=self.environment.parsed_options.verbose_logging,
        )

        run_task_sequence(request, [
            "home_expected",
            "search_ticket_expected",
        ])


class UserBooking(HttpUser):
    weight = 1
    # wait_function = random.expovariate(1)
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))
        self.current_user: str = ''
        self.task_count: int = 0

    @task
    def perform_task(self):
        logging.debug("Running user 'booking'...")

        user_signup: bool = False
        if self.task_count % self.environment.parsed_options.num_tasks_per_signup == 0:
            self.current_user = random.choice(USER_CREDETIALS)
            user_signup = True
        self.task_count += 1

        request = Requests(
            self.client,
            user=self.current_user,
            signup=user_signup,
            verbose_logging=self.environment.parsed_options.verbose_logging,
        )

        run_task_sequence(request, [
            "home_expected",
            "login_expected",
            "search_ticket_expected",
            "start_booking_expected",
            "get_assurance_types_expected",
            "get_foods_expected",
            "select_contact_expected",
            "finish_booking_expected",
        ])


class UserConsignTicket(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))
        self.current_user: str = ''
        self.task_count: int = 0

    @task
    def perform_task(self):
        logging.debug("Running user 'consign ticket'...")

        user_signup: bool = False
        if self.task_count % self.environment.parsed_options.num_tasks_per_signup == 0:
            self.current_user = random.choice(USER_CREDETIALS)
            user_signup = True
        self.task_count += 1

        request = Requests(
            self.client,
            user=self.current_user,
            signup=user_signup,
            verbose_logging=self.environment.parsed_options.verbose_logging,
        )

        run_task_sequence(request, [
            "home_expected",
            "login_expected",
            "select_contact_expected",
            "finish_booking_expected",
            "select_order_expected",
            "get_consigns_expected",
            "confirm_consign_expected",
        ])


class UserPay(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))
        self.current_user: str = ''
        self.task_count: int = 0

    @task
    def perform_task(self):
        logging.debug("Running user 'booking'...")

        user_signup: bool = False
        if self.task_count % self.environment.parsed_options.num_tasks_per_signup == 0:
            self.current_user = random.choice(USER_CREDETIALS)
            user_signup = True
        self.task_count += 1

        request = Requests(
            self.client,
            user=self.current_user,
            signup=user_signup,
            verbose_logging=self.environment.parsed_options.verbose_logging,
        )

        run_task_sequence(request, [
            "home_expected",
            "login_expected",
            "select_contact_expected",
            "finish_booking_expected",
            "select_order_expected",
            "pay_expected",
        ])


class UserCancelNoRefund(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))
        self.current_user: str = ''
        self.task_count: int = 0

    @task
    def perform_task(self):
        logging.debug("Running user 'cancel no refund'...")

        user_signup: bool = False
        if self.task_count % self.environment.parsed_options.num_tasks_per_signup == 0:
            self.current_user = random.choice(USER_CREDETIALS)
            user_signup = True
        self.task_count += 1

        request = Requests(
            self.client,
            user=self.current_user,
            signup=user_signup,
            verbose_logging=self.environment.parsed_options.verbose_logging,
        )

        run_task_sequence(request, [
            "home_expected",
            "login_expected",
            "select_contact_expected",
            "finish_booking_expected",
            "select_order_expected",
            "cancel_with_no_refund_expected",
        ])


class UserCollectTicket(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))
        self.current_user: str = ''
        self.task_count: int = 0

    @task
    def perform_task(self):
        logging.debug("Running user 'collect ticket'...")

        user_signup: bool = False
        if self.task_count % self.environment.parsed_options.num_tasks_per_signup == 0:
            self.current_user = random.choice(USER_CREDETIALS)
            user_signup = True
        self.task_count += 1

        request = Requests(
            self.client,
            user=self.current_user,
            signup=user_signup,
            verbose_logging=self.environment.parsed_options.verbose_logging,
        )

        run_task_sequence(request, [
            "home_expected",
            "login_expected",
            "select_contact_expected",
            "finish_booking_expected",
            "select_order_expected",
            "pay_expected",
            "collect_ticket_expected",
            "get_voucher_expected",
        ])


class UserRebook(HttpUser):
    weight = 1
    wait_time = constant(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.mount('https://', HTTPAdapter(pool_maxsize=50))
        self.client.mount('http://', HTTPAdapter(pool_maxsize=50))
        self.current_user: str = ''
        self.task_count: int = 0

    @task
    def perform_task(self):
        user_signup: bool = False
        if self.task_count % self.environment.parsed_options.num_tasks_per_signup == 0:
            self.current_user = random.choice(USER_CREDETIALS)
            user_signup = True
        self.task_count += 1

        request = Requests(
            self.client,
            user=self.current_user,
            signup=user_signup,
            verbose_logging=self.environment.parsed_options.verbose_logging,
        )

        run_task_sequence(request, [
            "home_expected",
            "login_expected",
            "select_contact_expected",
            "finish_booking_expected",
            "select_order_expected",
            "pay_expected",
            "rebook_expected",  # rebook requires the order with STATUS_PAYED(=1)
        ])


def run_task_sequence(request, sequence: list[str]):
    for seq in sequence:
        try:
            request.perform_task(seq)
        except TrainTicketError:
            logging.exception(f"{seq} raises an error of train ticket")
            break


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
