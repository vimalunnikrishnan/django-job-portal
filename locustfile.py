import os
from locust import HttpUser, task, between


class JobPortalUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        self.token = os.getenv("LOCUST_ACCESS_TOKEN")

        if not self.token:
            raise RuntimeError(
                "Set LOCUST_ACCESS_TOKEN before starting Locust."
            )

    @task
    def list_jobs(self):
        self.client.get(
            "/api/jobs/list/",
            headers={
                "Authorization": f"Bearer {self.token}"
            },
            name="GET /api/jobs/list/",
        )