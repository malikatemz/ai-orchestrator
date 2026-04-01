from app import routes


class TestHealthAndDiagnostics:
    def test_it_returns_ok_health_status(self, test_client):
        response = test_client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["queue_mode"] == "celery-with-inline-fallback"

    def test_it_exposes_a_runtime_fingerprint(self, test_client):
        response = test_client.get("/diagnostics/runtime")

        assert response.status_code == 200
        payload = response.json()["runtime"]
        assert payload["python_version"]
        assert payload["platform"]
        assert payload["database_driver"]


class TestOverviewAndWorkflowHappyPaths:
    def test_it_returns_seeded_overview_data(self, test_client):
        response = test_client.get("/overview")

        assert response.status_code == 200
        payload = response.json()
        assert payload["metrics"]["workflows"] >= 3
        assert len(payload["workflows"]) >= 3
        assert len(payload["recent_tasks"]) >= 1

    def test_it_lists_workflows_and_workflow_tasks(self, test_client):
        workflows_response = test_client.get("/workflows")

        assert workflows_response.status_code == 200
        workflows = workflows_response.json()
        assert len(workflows) >= 3

        workflow_id = workflows[0]["id"]
        workflow_detail_response = test_client.get(f"/workflows/{workflow_id}")
        tasks_response = test_client.get(f"/workflows/{workflow_id}/tasks")

        assert workflow_detail_response.status_code == 200
        assert tasks_response.status_code == 200
        assert workflow_detail_response.json()["id"] == workflow_id
        assert isinstance(tasks_response.json(), list)

    def test_it_creates_a_workflow_and_task(self, test_client, monkeypatch):
        monkeypatch.setattr(routes, "queue_task", lambda task_id: "inline")

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

        assert workflow_response.status_code == 201
        workflow_payload = workflow_response.json()
        assert workflow_payload["owner"] == "admin"

        task_response = test_client.post(
            f"/workflows/{workflow_payload['id']}/tasks",
            json={
                "name": "Draft response brief",
                "input": "Summarize the outage and generate a customer-ready incident brief.",
                "agent": "researcher",
            },
        )

        assert task_response.status_code == 202
        task_payload = task_response.json()
        assert task_payload["workflow_id"] == workflow_payload["id"]
        assert task_payload["status"] == "pending"
        assert task_payload["stage"] == "queued"


class TestApiErrorHandling:
    def test_it_returns_structured_not_found_errors_for_missing_workflows(self, test_client):
        response = test_client.get("/workflows/99999")

        assert response.status_code == 404
        payload = response.json()
        assert payload["error"]["code"] == "AIORCH-NOTFOUND-001"
        assert payload["error"]["retryable"] is False
        assert payload["request_id"]

    def test_it_returns_validation_errors_for_invalid_workflow_payloads(self, test_client):
        response = test_client.post(
            "/workflows",
            json={"name": "x", "description": "short"},
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["error"]["code"] == "AIORCH-VAL-001"
        assert "errors" in payload["error"]["details"]

    def test_it_rejects_boundary_task_payloads_that_are_too_short(self, test_client):
        response = test_client.post(
            "/workflows/1/tasks",
            json={"name": "no", "input": "bad", "agent": "planner"},
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["error"]["code"] == "AIORCH-VAL-001"

    def test_it_rejects_unknown_agent_values(self, test_client):
        response = test_client.post(
            "/workflows/1/tasks",
            json={"name": "Investigate production issue", "input": "Inspect the incident timeline carefully.", "agent": "unknown"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "AIORCH-VAL-001"


class TestDependencyAndBoundaryBehavior:
    def test_it_allows_model_name_at_maximum_supported_boundary(self, test_client):
        response = test_client.post(
            "/workflows",
            json={
                "name": "Boundary Workflow",
                "description": "A workflow that validates accepted maximum model identifier lengths safely.",
                "owner": "ops",
                "priority": "medium",
                "target_model": "m" * 80,
            },
        )

        assert response.status_code == 201
        assert response.json()["target_model"] == "m" * 80

    def test_it_returns_retryable_internal_errors_when_task_queueing_explodes(self, test_client, monkeypatch):
        monkeypatch.setattr(routes, "queue_task", lambda task_id: (_ for _ in ()).throw(RuntimeError("queue unavailable")))

        workflow_response = test_client.post(
            "/workflows",
            json={
                "name": "Queue Failure Workflow",
                "description": "A workflow used to validate how route-level exceptions are surfaced to clients.",
                "owner": "ops",
                "priority": "high",
                "target_model": "gpt-4.1",
            },
        )
        workflow_id = workflow_response.json()["id"]

        response = test_client.post(
            f"/workflows/{workflow_id}/tasks",
            json={
                "name": "Queue failure simulation",
                "input": "Trigger task queuing failure handling with a realistic incident payload.",
                "agent": "critic",
            },
        )

        assert response.status_code == 500
        payload = response.json()
        assert payload["error"]["code"] == "AIORCH-SYS-001"
        assert payload["error"]["retryable"] is True
