import json
import subprocess
import sys

from types import ModuleType
from unittest.mock import Mock, patch
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from peryl_db.models.vehicles import Vehicle


# Import the task without loading production database credentials or an engine.
engine_module = ModuleType("peryl_db.engine")
engine_module.engine = None
with patch.dict(sys.modules, {"peryl_db.engine": engine_module}):
    from peryl_agents.vehicles.discovery import task


@pytest.fixture
def engine(db_engine, monkeypatch):
    monkeypatch.setattr(task, "engine", db_engine)
    return db_engine


def _candidate(model):
    return {"make": "Example",
            "model": model,
            "trim": "Base",
            "model_year_start": 2020,
            "model_year_end": 2022}


def _result(candidates):
    return subprocess.CompletedProcess(args=[], returncode=0,
                                       stdout=json.dumps({"data": candidates}), stderr="")


@pytest.mark.parametrize("duration", [0, -1, 5])
def test_skips_discovery_when_time_budget_is_exhausted(engine, monkeypatch, duration):
    discovery = Mock()
    monkeypatch.setattr(task.time, "monotonic", Mock(side_effect=[100, 104, 105]))
    monkeypatch.setattr(task.subprocess, "run", discovery)

    task.run_task(max_duration_seconds=duration)

    discovery.assert_not_called()


def test_reloads_vehicles_and_saves_batch_finishing_after_deadline(engine, monkeypatch):
    candidates = [_candidate("First"), _candidate("Second")]
    contexts = []
    clock = Mock(return_value=100)

    def discover(args, **kwargs):
        assert "timeout" not in kwargs
        contexts.append(kwargs["input"].split("Current vehicles in the Peryl database:\n")[1].strip())
        if len(contexts) == 2:
            clock.return_value = 3701
        return _result([candidates[len(contexts) - 1]])

    discovery = Mock(side_effect=discover)
    monkeypatch.setattr(task.time, "monotonic", clock)
    monkeypatch.setattr(task.subprocess, "run", discovery)

    task.run_task()

    assert discovery.call_count == 2
    assert contexts[0] == "None"
    assert "Example, First, 2020, 2022, Base" in contexts[1]
    with Session(engine) as session:
        assert set(session.scalars(select(Vehicle.model))) == {"First", "Second"}


def test_continues_after_empty_and_duplicate_batches(engine, monkeypatch):
    existing = _candidate("Existing")
    with Session(engine) as session:
        session.add(Vehicle(**existing))
        session.commit()

    responses = [[], [existing], [_candidate("New")]]
    call_count = 0
    clock = Mock(return_value=100)

    def discover(args, **kwargs):
        nonlocal call_count
        response = _result(responses[call_count])
        call_count += 1
        clock.return_value += 2
        return response

    discovery = Mock(side_effect=discover)
    monkeypatch.setattr(task.time, "monotonic", clock)
    monkeypatch.setattr(task.subprocess, "run", discovery)

    task.run_task(max_duration_seconds=5)

    assert discovery.call_count == 3
    with Session(engine) as session:
        models = list(session.scalars(select(Vehicle.model).order_by(Vehicle.model)))
        assert models == ["Existing", "New"]


def test_later_discovery_failure_keeps_completed_batches(engine, monkeypatch):
    response = _result([_candidate("Saved")])
    failure = subprocess.CalledProcessError(1, ["codex"], stderr="discovery failed")
    discovery = Mock(side_effect=[response, failure])
    monkeypatch.setattr(task.time, "monotonic", Mock(return_value=100))
    monkeypatch.setattr(task.subprocess, "run", discovery)

    with pytest.raises(subprocess.CalledProcessError):
        task.run_task()

    assert discovery.call_count == 2
    with Session(engine) as session:
        assert list(session.scalars(select(Vehicle.model))) == ["Saved"]
