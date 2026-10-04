"""Load test: API reads under concurrent users plus a trickle of new analyses.

    docker compose --profile load up      # UI at http://localhost:8089
    locust -f tests/load/locustfile.py --host http://localhost:8000 --headless -u 50 -r 10 -t 2m

Run with LLM_MODE=mock and LANGFUSE disabled so the test measures the platform, not
LLM latency, and does not consume the Langfuse Hobby quota (plan.md §4.3a).
"""

import os
import random

from locust import HttpUser, between, task

TOKEN = os.getenv("APP_ACCESS_TOKEN", "")
HEADERS = {"X-Access-Token": TOKEN} if TOKEN and not TOKEN.startswith("REPLACE_ME") else {}
QUERIES = [
    "Analyse employment trends in the technology sector from 2020-2024",
    "Compare employment growth across sectors from 2019 to 2024",
    "Forecast technology sector employment for the next two years",
]


class Researcher(HttpUser):
    wait_time = between(1, 3)
    ids: list[str] = []

    @task(6)
    def list_history(self):
        resp = self.client.get("/api/v1/analyses?limit=20", headers=HEADERS, name="GET /analyses")
        if resp.ok:
            Researcher.ids = [a["id"] for a in resp.json()][:20]

    @task(4)
    def view_analysis(self):
        if Researcher.ids:
            self.client.get(f"/api/v1/analyses/{random.choice(Researcher.ids)}", headers=HEADERS,
                            name="GET /analyses/{id}")

    @task(2)
    def replay_events(self):
        if Researcher.ids:
            self.client.get(f"/api/v1/analyses/{random.choice(Researcher.ids)}/events", headers=HEADERS,
                            name="GET /analyses/{id}/events")

    @task(1)
    def health(self):
        self.client.get("/readyz", name="GET /readyz")

    @task(1)
    def create_analysis(self):
        self.client.post("/api/v1/analyses", json={"query": random.choice(QUERIES)}, headers=HEADERS,
                         name="POST /analyses")
