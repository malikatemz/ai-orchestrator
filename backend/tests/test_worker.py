from app import models, worker


def test_run_task_completes_and_persists_output(tmp_path, monkeypatch):
    engine = models.build_engine(f"sqlite:///{tmp_path / 'worker.db'}")
    session_factory = models.build_session_factory(engine)
    models.init_db(engine)

    monkeypatch.setattr(models, "engine", engine)
    monkeypatch.setattr(models, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)

    db = session_factory()
    workflow = models.Workflow(
        name="Worker Flow",
        description="Test background execution path for tasks.",
        owner="qa",
        priority="medium",
        target_model="gpt-4.1-mini",
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    task = models.Task(
        workflow_id=workflow.id,
        name="Analyze issue",
        agent="planner",
        input_data="Investigate a blocked rollout and produce a summary.",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task_id = task.id
    db.close()

    result = worker.run_task.run(task_id)

    refreshed_db = session_factory()
    refreshed_task = refreshed_db.query(models.Task).filter(models.Task.id == task_id).first()
    assert result["status"] == "completed"
    assert refreshed_task.status == "completed"
    assert refreshed_task.output_data is not None
    refreshed_db.close()


def test_queue_task_falls_back_to_inline_execution(tmp_path, monkeypatch):
    engine = models.build_engine(f"sqlite:///{tmp_path / 'queue.db'}")
    session_factory = models.build_session_factory(engine)
    models.init_db(engine)

    monkeypatch.setattr(models, "engine", engine)
    monkeypatch.setattr(models, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)

    db = session_factory()
    workflow = models.Workflow(
        name="Inline Queue Flow",
        description="Test queue degradation path.",
        owner="qa",
        priority="high",
        target_model="gpt-4.1",
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    task = models.Task(
        workflow_id=workflow.id,
        name="Inline execute",
        agent="researcher",
        input_data="Urgent incident in production. Prepare a response summary.",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task_id = task.id
    db.close()

    monkeypatch.setattr(worker.run_task, "delay", lambda task_id: (_ for _ in ()).throw(RuntimeError("queue offline")))

    queue_mode = worker.queue_task(task_id)

    refreshed_db = session_factory()
    refreshed_task = refreshed_db.query(models.Task).filter(models.Task.id == task_id).first()
    assert queue_mode == "inline"
    assert refreshed_task.status == "completed"
    refreshed_db.close()
