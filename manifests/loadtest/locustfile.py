import base64
from random import choice

from locust import HttpUser, constant, task


class SockShopLoadTest(HttpUser):
    wait_time = constant(1.0)

    @task
    def load(self):
        encoded = base64.b64encode(b'user:password')

        catalogue = self.client.get("/catalogue").json()
        category_item = choice(catalogue)
        item_id = category_item["id"]

        self.client.get("/")
        self.client.get("/login", headers={"Authorization": "Basic %s" % encoded.decode('ascii')})
        self.client.get("/category.html")
        self.client.get("/detail.html?id={}".format(item_id))
        self.client.delete("/cart")
        self.client.post("/cart", json={"id": item_id, "quantity": 1})
        self.client.get("/basket.html")
        self.client.post("/orders")
