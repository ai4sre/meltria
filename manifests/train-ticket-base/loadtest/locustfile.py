import logging
import time
import uuid
from datetime import datetime, timedelta

import locust.stats
from locust import HttpUser, between, constant, events, task
from requests.adapters import HTTPAdapter

locust.stats.PERCENTILES_TO_REPORT = [0.25, 0.50, 0.75, 0.80, 0.90, 0.95, 0.98, 0.99, 0.999, 0.9999, 1.0]
LOG_STATISTICS_IN_HALF_MINUTE_CHUNKS = (1 == 1)
RETRY_ON_ERROR = False
MAX_RETRIES = 3

STATUS_BOOKED = 0
STATUS_PAID = 1
STATUS_COLLECTED = 2
STATUS_CANCELLED = 4
STATUS_EXECUTED = 6

spawning_complete = False


class TrainTicketRequestException(Exception):
    def __init__(self, message):
        super().__init__(message)


@events.spawning_complete.add_listener
def on_spawning_complete(user_count, **kwargs):
    global spawning_complete
    spawning_complete = True


@events.request_failure.add_listener
def request_failure_handler(request_type, name, response_time, exception, **kwargs):
    logging.error(
        f"Request Failed! time:{datetime.now()}, response_time:{response_time} name:{name}, exception:{exception}")


def request_get_to_api(client, url, name):
    with client.get(url=url, catch_response=True, name=get_name_suffix(name)) as response:
        if response.status_code not in [200, 201, 404]:
            response.failure(
                f"failed to request status:{response.status_code} body:{response.content.decode('UTF-8')[0:10]}")
    response_as_json = response.json()
    return response_as_json, response_as_json["status"]


def request_post_to_api(client, url, body, name, headers={}):
    with client.post(
        url=url, headers=headers, json=body, catch_response=True,
        name=get_name_suffix(name),
    ) as response:
        if response.status_code not in [200, 201, 404]:
            response.failure(
                f"failed to request status:{response.status_code} body:{response.content.decode('UTF-8')[0:10]}")
    response_as_json = response.json()
    if 'status' in response_as_json:
        return response_as_json, response_as_json["status"]
    else:
        return response_as_json, 1


def try_until_success(f):
    for attempt in range(MAX_RETRIES):
        logging.debug(f"Calling function {f.__name__}, attempt {attempt}...")

        # try:
        result, status = f()
        result_as_string = str(result)
        logging.debug(f"Result of calling function {f.__name__} was: {result_as_string}.")
        if status == 1:
            return result
        else:
            logging.debug(f"Failed calling function {f.__name__}, response was {result_as_string}, trying again:")
            time.sleep(1)
        # except Exception as e:
        #     exception_as_text = str(e)
        #     logging.debug(f"Failed calling function {f.__name__}, exception was: {exception_as_text}, trying again.")
        #     time.sleep(1)

        if not RETRY_ON_ERROR:
            break

    raise TrainTicketRequestException(f"Weird... Cannot call endpoint {f.__name__}")


def login(client):
    user_name = str(uuid.uuid4())
    password = "12345678"

    def api_call_admin_login():
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        body = {"username": "admin", "password": "222222"}
        return request_post_to_api(
            client, url="/api/v1/users/login", headers=headers, body=body, name="admin_login")

    response_as_json = try_until_success(api_call_admin_login)
    data = response_as_json["data"]
    token = data["token"]

    def api_call_admin_create_user():
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
        body = {
            "documentNum": None, "documentType": 0, "email": "string", "gender": 0,
            "password": password, "userName": user_name,
        }
        return request_post_to_api(
            client, url="/api/v1/adminuserservice/users", headers=headers, body=body, name="admin_create_user")

    response_as_json = try_until_success(api_call_admin_create_user)

    def api_call_login():
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        body = {"username": user_name, "password": password}
        return request_post_to_api(
            client, url="/api/v1/users/login", headers=headers, body=body, name="admin_create_user")

    response_as_json = try_until_success(api_call_login)
    data = response_as_json["data"]
    user_id = data["userId"]
    token = data["token"]

    def api_call_create_contact_for_user():
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
        body = {
            "name": user_name, "accountId": user_id, "documentType": "1",
            "documentNumber": "123456", "phoneNumber": "123456",
        }
        return request_post_to_api(
            client, url="/api/v1/contactservice/contacts", headers=headers, body=body, name="admin_create_contact")

    try_until_success(api_call_create_contact_for_user)

    return user_id, token


def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days_ahead)


def get_name_suffix(name):
    global spawning_complete
    if not spawning_complete:
        name = name + "_spawning"

    if LOG_STATISTICS_IN_HALF_MINUTE_CHUNKS:
        now = datetime.now()
        now = datetime(now.year, now.month, now.day, now.hour, now.minute, 0 if now.second < 30 else 30, 0)
        now_as_timestamp = int(now.timestamp())
        return f"{name}@{now_as_timestamp}"
    else:
        return name


def home(client):
    # the response not to be JSON data
    return client.get(url="/index.html", name=get_name_suffix("home"))


def get_departure_date():
    # We always start next Monday because there a train from Shang Hai to Su Zhou starts.
    tomorrow = datetime.now() + timedelta(1)
    next_monday = next_weekday(tomorrow, 0)
    return next_monday.strftime("%Y-%m-%d")


def get_trip_information(client, from_station, to_station):
    departure_date = get_departure_date()

    def api_call_get_trip_information():
        body = {"startingPlace": from_station, "endPlace": to_station, "departureTime": departure_date}
        return request_post_to_api(
            client, url="/api/v1/travelservice/trips/left", headers={}, body=body, name="get_trip_information")

    try_until_success(api_call_get_trip_information)


def search_departure(client):
    get_trip_information(client, "Shang Hai", "Su Zhou")


def search_return(client):
    get_trip_information(client, "Su Zhou", "Shang Hai")


def book(client, user_id):
    # we always start next Monday
    tomorrow = datetime.now() + timedelta(1)
    next_monday = next_weekday(tomorrow, 0)
    departure_date = next_monday.strftime("%Y-%m-%d")

    def api_call_insurance():
        return request_get_to_api(
            client, url="/api/v1/assuranceservice/assurances/types", name="get_assurance_types",
        )

    def api_call_food():
        return request_get_to_api(
            client,
            url=f"/api/v1/foodservice/foods/{departure_date}/Shang%20Hai/Su%20Zhou/D1345",
            name="get_food_types",
        )

    def api_call_contacts():
        return request_get_to_api(
            client,
            url=f"/api/v1/contactservice/contacts/account/{user_id}",
            name="query_contacts",
        )

    try_until_success(api_call_insurance)
    try_until_success(api_call_food)
    response_as_json = try_until_success(api_call_contacts)
    data = response_as_json["data"]
    contact_id = data[0]["id"]

    def api_call_ticket():
        body = {
            "accountId": user_id, "contactsId": contact_id, "tripId": "D1345", "seatType": "2",
            "date": departure_date, "from": "Shang Hai", "to": "Su Zhou", "assurance": "0",
            "foodType": 1, "foodName": "Bone Soup", "foodPrice": 2.5, "stationName": "", "storeName": "",
        }
        return request_post_to_api(client, url="/api/v1/preserveservice/preserve", body=body, name="preserve_ticket")

    try_until_success(api_call_ticket)


def get_last_order(client, user_id, expected_status):
    def api_call_query():
        body = {
            "loginId": user_id, "enableStateQuery": "false", "enableTravelDateQuery": "false",
            "enableBoughtDateQuery": "false", "travelDateStart": "null", "travelDateEnd": "null",
            "boughtDateStart": "null", "boughtDateEnd": "null",
        }
        return request_post_to_api(
            client,
            url="/api/v1/orderservice/order/refresh", body=body, name="get_order_information",
        )

    response_as_json = try_until_success(api_call_query)
    data = response_as_json["data"]

    for entry in data:
        if entry["status"] == expected_status:
            return entry

    return None


def get_last_order_id(client, user_id, expected_status):
    order = get_last_order(client, user_id, expected_status)

    if order is not None:
        order_id = order["id"]
        return order_id

    return None


def pay(client, user_id):
    order_id = get_last_order_id(client, user_id, STATUS_BOOKED)
    if order_id is None:
        raise Exception("Weird... There is no order to pay.")

    def api_call_pay():
        body = {"orderId": order_id, "tripId": "D1345"}
        return request_post_to_api(
            client,
            url="/api/v1/inside_pay_service/inside_payment", body=body, name="pay_order",
        )

    try_until_success(api_call_pay)


def cancel(client, user_id):
    order_id = get_last_order_id(client, user_id, STATUS_BOOKED)
    if order_id is None:
        raise Exception("Weird... There is no order to cancel.")

    def api_call_cancel():
        return request_get_to_api(
            client,
            url=f"/api/v1/cancelservice/cancel/{order_id}/{user_id}", name="cancel_order",
        )

    try_until_success(api_call_cancel)


def consign(client, user_id):
    order_id = get_last_order_id(client, user_id, STATUS_BOOKED)
    if order_id is None:
        raise Exception("Weird... There is no order to consign.")

    departure_date = get_departure_date()

    def api_call_consign():
        body = {
            "accountId": user_id, "handleDate": departure_date, "from": "Shang Hai", "to": "Su Zhou",
            "orderId": order_id, "consignee": order_id, "phone": "123", "weight": "1", "id": "", "isWithin": "false",
        }
        return request_post_to_api(
            client,
            url="/api/v1/consignservice/consigns", body=body, name="create_consign",
        )

    try_until_success(api_call_consign)


def collect_and_use(client, user_id):
    order_id = get_last_order_id(client, user_id, STATUS_PAID)
    if order_id is None:
        raise Exception("Weird... There is no order to collect.")

    def api_call_collect_ticket():
        return request_get_to_api(
            client,
            url=f"/api/v1/executeservice/execute/collected/{order_id}", name="collect_ticket",
        )

    try_until_success(api_call_collect_ticket)

    order_id = get_last_order_id(client, user_id, STATUS_COLLECTED)
    if order_id is None:
        raise Exception("Weird... There is no order to execute.")

    def api_call_enter_station():
        return request_get_to_api(
            client,
            url=f"/api/v1/executeservice/execute/execute/{order_id}", name="enter_station",
        )

    try_until_success(api_call_enter_station)


def get_voucher(client, user_id):
    order_id = get_last_order_id(client, user_id, STATUS_EXECUTED)
    if order_id is None:
        raise Exception("Weird... There is no order that was used.")

    def api_call_get_voucher():
        body = {"orderId": order_id, "type": 1}
        return request_post_to_api(
            client, url="/getVoucher", body=body, name="get_voucher",
        )

    try_until_success(api_call_get_voucher)

# class MyHttpUser(HttpUser):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.client.mount("https://", HTTPAdapter(pool_maxsize=50))
#         self.client.mount("http://", HTTPAdapter(pool_maxsize=50))


class UserNoLogin(HttpUser):
    weight = 2

    def on_start(self):
        self.client.headers.update({"Content-Type": "application/json"})
        self.client.headers.update({"Accept": "application/json"})

    @task
    def perfom_task(self):
        request_id = str(uuid.uuid4())
        logging.debug(f'Running user "no login" with request id {request_id}...')

        home(self.client)
        search_departure(self.client)
        search_return(self.client)


class UserBooking(HttpUser):
    weight = 1

    def on_start(self):
        user_id, token = login(self.client)
        self.client.headers.update({"Authorization": f"Bearer {token}"})
        self.client.headers.update({"Content-Type": "application/json"})
        self.client.headers.update({"Accept": "application/json"})
        self.user_id = user_id

    @task
    def perform_task(self):
        request_id = str(uuid.uuid4())
        logging.debug(f'Running user "booking" with request id {request_id}...')

        home(self.client)
        search_departure(self.client)
        search_return(self.client)
        book(self.client, self.user_id)
        pay(self.client, self.user_id)
        collect_and_use(self.client, self.user_id)


class UserConsignTicket(HttpUser):
    weight = 1

    def on_start(self):
        user_id, token = login(self.client)
        self.client.headers.update({"Authorization": f"Bearer {token}"})
        self.client.headers.update({"Content-Type": "application/json"})
        self.client.headers.update({"Accept": "application/json"})
        self.user_id = user_id

    @task
    def perform_task(self):
        request_id = str(uuid.uuid4())
        logging.debug(f'Running user "consign ticket" with request id {request_id}...')

        home(self.client)
        search_departure(self.client)
        search_return(self.client)
        book(self.client, self.user_id)
        consign(self.client, self.user_id)


class UserCancelNoRefund(HttpUser):
    weight = 1

    def on_start(self):
        user_id, token = login(self.client)
        self.client.headers.update({"Authorization": f"Bearer {token}"})
        self.client.headers.update({"Content-Type": "application/json"})
        self.client.headers.update({"Accept": "application/json"})
        self.user_id = user_id

    @task
    def perform_task(self):
        request_id = str(uuid.uuid4())
        logging.debug(f'Running user "cancel no refund" with request id {request_id}...')

        home(self.client)
        search_departure(self.client)
        search_return(self.client)
        book(self.client, self.user_id)
        cancel(self.client, self.user_id)


class UserRefundVoucher(HttpUser):
    weight = 1

    def on_start(self):
        user_id, token = login(self.client)
        self.client.headers.update({"Authorization": f"Bearer {token}"})
        self.client.headers.update({"Content-Type": "application/json"})
        self.client.headers.update({"Accept": "application/json"})
        self.user_id = user_id

    @task
    def perform_task(self):
        request_id = str(uuid.uuid4())
        logging.debug(f'Running user "cancel no refund" with request id {request_id}...')

        home(self.client)
        search_departure(self.client)
        search_return(self.client)
        book(self.client, self.user_id)
        pay(self.client, self.user_id)
        collect_and_use(self.client, self.user_id)
        get_voucher(self.client, self.user_id)

# class StagesShape(LoadTestShape):
#     """
#     A simply load test shape class that has different user and spawn_rate at
#     different stages.
#     Keyword arguments:
#         stages -- A list of dicts, each representing a stage with the following keys:
#             duration -- When this many seconds pass the test is advanced to the next stage
#             users -- Total user count
#             spawn_rate -- Number of users to start/stop per second
#             stop -- A boolean that can stop that test at a specific stage
#         stop_at_end -- Can be set to stop once all stages have run.
#     """

#     stages = [
#         {"duration": 5, "users": 10, "spawn_rate": 10},
#         {"duration": 15, "users": 50, "spawn_rate": 10},
#         {"duration": 25, "users": 100, "spawn_rate": 10}
#     ]

#     def tick(self):
#         run_time = self.get_run_time()

#         for stage in self.stages:
#             if run_time < stage["duration"]:
#                 tick_data = (stage["users"], stage["spawn_rate"])
#                 return tick_data

#         return None
