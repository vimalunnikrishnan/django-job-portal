from locust import HttpUser, task, between


class JobPortalUser(HttpUser):

    wait_time = between(1, 2)

    def on_start(self):
        self.token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzkwNTA1ODgyLCJpYXQiOjE3OTA1MDQwODQsImp0aSI6IjhkMWZjMzNjNWFlMTQ1NGZiNjMyODhiYjQzNzVmNzg1IiwidXNlcl9pZCI6IjMifQ.nt5Huq_eadNBTZqCE25ok7kDusUagl9_ZcWCimTwhVo"

    @task
    def list_jobs(self):
        self.client.get(
            "/api/jobs/list/",
            headers={
                "Authorization": f"Bearer {self.token}"
            },
            name="GET /api/jobs/list/"
        )