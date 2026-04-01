from app import main, routes
from app.auth import get_current_user
from app.config import AppMode, settings


class TestHealthAndConfig:
    def test_it_returns_ok_health_status(self, test_client):
        response = test_client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["queue_mode"] == "celery-with-inline-fallback"

    def test_it_exposes_runtime_and_public_app_config(self, test_client):
        settings.app_mode = AppMode.DEMO
        settings.public_demo_mode = True
        settings.auto_seed_demo = True
        settings.public_app_url = "https://example.com"
        settings.public_api_url = "https://api.example.com"

        diagnostics = test_client.get("/diagnostics/runtime")
        config = test_client.get("/app-config")

        assert diagnostics.status_code == 200
        assert diagnostics.json()["runtime"]["python_version"]

        assert config.status_code == 200
        payload = config.json()
        assert payload["demo_mode"] is True
        assert payload["auth_required"] is False
        assert payload["demo_seed_enabled"] is True


class TestOverviewAndTaskFlows:
    def test_it_returns_seeded_overview_data(self, test_client):
        test_client.post("/seed-demo")

        response = test_client.get("/overview")

        assert response.status_code == 200
        payload = response.json()
        assert payload["metrics"]["workflows"] >= 3
        assert len(payload["workflows"]) >= 3
        assert len(payload["recent_tasks"]) >= 1

    def test_it_assigns_queue_name_from_workflow_priority(self, test_client, monkeypatch):
        monkeypatch.setattr(routes, "queue_task", lambda task_id, queue_name: "inline")

        workflow_response = test_client.post(
            "/workflows",
            json={
                "name": "Incident Response Pipeline",
                "description": "Create a workflow for incident triage and customer follow-up handling.",
                "owner": "support",
                "priority": "high",
                "target_model": "gpt-4.1",
            },
        )

        task_response = test_client.post(
            f"/workflows/{workflow_response.json()['id']}/tasks",
            json={
                "name": "Draft response brief",
                "input": "Summarize the outage and generate a customer-ready incident brief.",
                "agent": "researcher",
            },
        )

        assert task_response.status_code == 202
        assert task_response.json()["queue_name"] == "high_priority"

    def test_it_retries_failed_tasks_and_preserves_lineage(self, test_client, monkeypatch):
        monkeypatch.setattr(routes, "queue_task", lambda task_id, queue_name: "inline")
        test_client.post("/seed-demo")

        workflows = test_client.get("/overview").json()["workflows"]
        workflow_id = next(workflow["id"] for workflow in workflows if workflow["failed_tasks"] > 0)
        detail = test_client.get(f"/workflows/{workflow_id}").json()
        failed_task = next(task for task in detail["tasks"] if task["status"] == "failed")

        retry_response = test_client.post(f"/tasks/{failed_task['id']}/retry")

        assert retry_response.status_code == 202
        payload = retry_response.json()
        assert payload["workflow_id"] == failed_task["workflow_id"]
        assert payload["source_task_id"] == failed_task["id"]
        assert payload["status"] == "pending"

    def test_it_auto_seeds_demo_data_on_startup_when_demo_mode_is_enabled(self, test_client):
        settings.app_mode = AppMode.DEMO
        settings.public_demo_mode = True
        settings.auto_seed_demo = True

        main.on_startup()
        response = test_client.get("/overview")

        assert response.status_code == 200
        assert response.json()["metrics"]["workflows"] >= 3


class TestAuditLogsAndOpsMetrics:
    def test_it_records_audit_logs_for_demo_seed_and_task_dispatch(self, test_client, monkeypatch):
        monkeypatch.setattr(routes, "queue_task", lambda task_id, queue_name: "inline")
        test_client.post("/seed-demo")

        workflow_id = test_client.get("/overview").json()["workflows"][0]["id"]
        test_client.post(
            f"/workflows/{workflow_id}/tasks",
            json={
                "name": "Investigate outage",
                "input": "Create an incident brief and recommend the next response step.",
                "agent": "planner",
            },
        )

        logs_response = test_client.get("/ops/audit-logs")

        assert logs_response.status_code == 200
        events = [entry["event"] for entry in logs_response.json()]
        assert "demo_reseeded" in events
        assert "task_dispatched" in events

    def test_it_aggregates_platform_ops_metrics(self, test_client):
        test_client.post("/seed-demo")

        response = test_client.get("/ops/metrics")

        assert response.status_code == 200
        payload = response.json()
        assert payload["workflows_total"] >= 3
        assert payload["tasks_total"] >= 4
        assert payload["failed_tasks"] >= 1
        assert payload["execution_lanes"]


class TestModeAndAuthorizationBehavior:
    def test_it_allows_seed_demo_in_public_demo_mode_without_auth(self, test_client):
        settings.app_mode = AppMode.DEMO
        settings.public_demo_mode = True
        settings.auto_seed_demo = True

        response = test_client.post("/seed-demo")

        assert response.status_code == 200

    def test_it_rejects_demo_reseed_for_non_admin_when_secured(self, test_client):
        settings.app_mode = AppMode.PRODUCTION
        settings.public_demo_mode = False
        settings.auto_seed_demo = False
        settings.api_token = "secret-token"
        test_client.app.dependency_overrides.pop(get_current_user, None)

        response = test_client.post("/seed-demo")

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AIORCH-VAL-001"
