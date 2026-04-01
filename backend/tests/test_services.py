from app import models, services


class TestOverviewService:
    def test_it_returns_only_accessible_workflows_for_non_admin_users(self, tmp_path):
        engine = models.build_engine(f"sqlite:///{tmp_path / 'services.db'}")
        session_factory = models.build_session_factory(engine)
        models.init_db(engine)

        db = session_factory()
        db.add_all(
            [
                models.Workflow(
                    name="Ops Workflow",
                    description="Workflow owned by ops user for authorized access tests.",
                    owner="ops",
                    priority="high",
                    target_model="gpt-4.1",
                ),
                models.Workflow(
                    name="Growth Workflow",
                    description="Workflow owned by growth user for filtering behavior tests.",
                    owner="growth",
                    priority="medium",
                    target_model="gpt-4.1-mini",
                ),
            ]
        )
        db.commit()

        payload = services.get_overview(db, {"sub": "ops", "scopes": ["orchestrator:access"]})

        assert len(payload["workflows"]) == 1
        assert payload["workflows"][0].owner == "ops"
        db.close()

    def test_it_returns_all_workflows_for_admin_users(self, tmp_path):
        engine = models.build_engine(f"sqlite:///{tmp_path / 'admin-services.db'}")
        session_factory = models.build_session_factory(engine)
        models.init_db(engine)

        db = session_factory()
        db.add_all(
            [
                models.Workflow(
                    name="Ops Workflow",
                    description="Workflow owned by ops user for authorized access tests.",
                    owner="ops",
                    priority="high",
                    target_model="gpt-4.1",
                ),
                models.Workflow(
                    name="Growth Workflow",
                    description="Workflow owned by growth user for filtering behavior tests.",
                    owner="growth",
                    priority="medium",
                    target_model="gpt-4.1-mini",
                ),
            ]
        )
        db.commit()

        payload = services.get_overview(db, {"sub": "admin", "scopes": ["orchestrator:admin"]})

        assert len(payload["workflows"]) == 2
        db.close()


class TestAuthorizationService:
    def test_it_allows_admin_to_access_any_workflow(self):
        workflow = models.Workflow(id=1, name="w", description="d" * 10, owner="ops", priority="high", target_model="gpt-4.1")

        services.assert_workflow_owner(workflow, {"sub": "admin", "scopes": ["orchestrator:admin"]})

    def test_it_rejects_non_owners(self):
        workflow = models.Workflow(id=1, name="w", description="d" * 10, owner="ops", priority="high", target_model="gpt-4.1")

        try:
            services.assert_workflow_owner(workflow, {"sub": "growth", "scopes": ["orchestrator:access"]})
            raised = None
        except Exception as exc:
            raised = exc

        assert raised is not None
        assert getattr(raised, "status_code", None) == 403
