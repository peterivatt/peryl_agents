import json
import subprocess
import sys

from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch
import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from peryl_agents.vehicles.research.validators import VehicleSpecCandidate
from peryl_db.models.vehicles import Vehicle, VehicleSpecs, VehicleSpecsMetadata


# Import the task without loading production database credentials or an engine.
engine_module = ModuleType("peryl_db.engine")
engine_module.engine = None
with patch.dict(sys.modules, {"peryl_db.engine": engine_module}):
    from peryl_agents.vehicles.research import task


SPEC_VALUES = {"width_mm": 1800,
               "length_mm": 4300,
               "height_mm": 1500,
               "curb_weight_kg": 1400,
               "stock_tire_class": 1}


@pytest.fixture
def engine(db_engine, monkeypatch):
    monkeypatch.setattr(task, "engine", db_engine)
    return db_engine


def _add_vehicle(engine, model, specs=None, research_status="missing"):
    with Session(engine) as session:
        vehicle = Vehicle(make="Example",
                          model=model,
                          trim="Base",
                          model_year_start=2020,
                          model_year_end=2022,
                          research_status=research_status,
                          specs=specs)
        session.add(vehicle)
        session.commit()
        return vehicle.id


def _candidate(vehicle_id, confidence=5, **values):
    candidate = {"vehicle_id": vehicle_id}
    for field in SPEC_VALUES:
        candidate[field] = None
        if field in values:
            candidate[field] = {"value": values[field],
                                "source_url": "https://example.com/specs",
                                "confidence": confidence}
    return candidate


def _result(candidates):
    return subprocess.CompletedProcess(args=[], returncode=0,
                                       stdout=json.dumps({"data": candidates}), stderr="")


def test_skips_empty_database_and_fully_populated_vehicles(engine, monkeypatch):
    research = Mock()
    monkeypatch.setattr(task.subprocess, "run", research)

    task.run_task()
    _add_vehicle(engine, "Complete", VehicleSpecs(**SPEC_VALUES), "complete")
    task.run_task()

    research.assert_not_called()


@pytest.mark.parametrize("duration", [0, -1, 5])
def test_skips_research_when_time_budget_is_exhausted(engine, monkeypatch, duration):
    vehicle_id = _add_vehicle(engine, "Pending")
    research = Mock()
    monkeypatch.setattr(task.time, "monotonic", Mock(side_effect=[100, 105]))
    monkeypatch.setattr(task.subprocess, "run", research)

    task.run_task(max_duration_seconds=duration)

    research.assert_not_called()
    with Session(engine) as session:
        assert session.get(Vehicle, vehicle_id).specs is None


def test_saves_batch_finishing_after_deadline(engine, monkeypatch):
    for index in range(26):
        _add_vehicle(engine, f"Car {index}")
    clock = Mock(return_value=100)

    def research(args, **kwargs):
        assert "timeout" not in kwargs
        context = json.loads(kwargs["input"].split("Vehicles to research (JSON):\n")[1])
        clock.return_value = 3701
        return _result([_candidate(vehicle["vehicle_id"], **SPEC_VALUES) for vehicle in context])

    run = Mock(side_effect=research)
    monkeypatch.setattr(task.time, "monotonic", clock)
    monkeypatch.setattr(task.subprocess, "run", run)

    task.run_task()

    run.assert_called_once()
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(VehicleSpecs)) == 25
        assert session.scalar(select(func.count()).select_from(VehicleSpecsMetadata)) == 125
        statuses = list(session.scalars(select(Vehicle.research_status)))
        assert statuses.count("complete") == 25
        assert statuses.count("missing") == 1


def test_creates_specs_and_metadata_and_skips_them_on_repeat(engine, monkeypatch):
    vehicle_id = _add_vehicle(engine, "New")
    response = _result([_candidate(vehicle_id, confidence=4, **SPEC_VALUES)])
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    research = Mock(return_value=response)
    monkeypatch.setattr(task.subprocess, "run", research)

    task.run_task()
    research.assert_called_once()
    research.reset_mock()
    task.run_task()
    research.assert_not_called()

    with Session(engine) as session:
        vehicle = session.get(Vehicle, vehicle_id)
        assert vehicle.research_status == "complete"
        for field, value in SPEC_VALUES.items():
            assert getattr(vehicle.specs, field) == value
        metadata = vehicle.specs.metadata_entries
        assert {entry.variable for entry in metadata} == set(SPEC_VALUES)
        assert len(metadata) == 5
        for entry in metadata:
            assert entry.specs_id == vehicle.specs.id
            assert entry.source_url == "https://example.com/specs"
            assert entry.confidence == 4
            assert started <= entry.date_set <= datetime.now(timezone.utc).replace(tzinfo=None)
        assert session.scalar(select(func.count()).select_from(VehicleSpecs)) == 1


def test_preserves_existing_values_and_uses_latest_metadata(engine, monkeypatch):
    specs = VehicleSpecs(width_mm=1850)
    specs.metadata_entries = [VehicleSpecsMetadata(variable="width_mm", confidence=5,
                                                   source_url="https://example.com/latest",
                                                   date_set=datetime(2026, 1, 1)),
                              VehicleSpecsMetadata(variable="width_mm", confidence=1,
                                                   source_url="https://example.com/older",
                                                   date_set=datetime(2025, 1, 1))]
    vehicle_id = _add_vehicle(engine, "Partial", specs, "incomplete")
    response = _result([_candidate(vehicle_id, **SPEC_VALUES)])
    research = Mock(return_value=response)
    monkeypatch.setattr(task.subprocess, "run", research)

    task.run_task()

    context = json.loads(research.call_args.kwargs["input"].split("Vehicles to research (JSON):\n")[1])
    assert context[0]["existing_specs"]["width_mm"] == 1850
    assert "width_mm" not in context[0]["missing_fields"]
    with Session(engine) as session:
        vehicle = session.get(Vehicle, vehicle_id)
        assert vehicle.specs.width_mm == 1850
        assert vehicle.research_status == "complete"
        width_metadata = [entry for entry in vehicle.specs.metadata_entries if entry.variable == "width_mm"]
        assert len(width_metadata) == 2
        assert len(vehicle.specs.metadata_entries) == 6


def test_handles_unresolved_partial_and_low_confidence_results(engine, monkeypatch):
    missing_id = _add_vehicle(engine, "Unknown")
    empty_id = _add_vehicle(engine, "Empty", VehicleSpecs())
    partial_id = _add_vehicle(engine, "Partial")
    low_id = _add_vehicle(engine, "Low confidence")
    unknown_id = _add_vehicle(engine, "No metadata", VehicleSpecs(width_mm=1800))
    null_confidence_specs = VehicleSpecs(width_mm=1800)
    null_confidence_specs.metadata_entries.append(VehicleSpecsMetadata(variable="width_mm"))
    null_confidence_id = _add_vehicle(engine, "Unknown confidence", null_confidence_specs)
    omitted_id = _add_vehicle(engine, "Omitted")
    response = _result([_candidate(missing_id),
                        _candidate(empty_id),
                        _candidate(partial_id, width_mm=1800),
                        _candidate(low_id, confidence=3, **SPEC_VALUES),
                        _candidate(unknown_id, **SPEC_VALUES),
                        _candidate(null_confidence_id, **SPEC_VALUES)])
    research = Mock(side_effect=[response])
    monkeypatch.setattr(task.subprocess, "run", research)

    task.run_task()

    research.assert_called_once()
    with Session(engine) as session:
        for vehicle_id in (missing_id, empty_id, omitted_id):
            assert session.get(Vehicle, vehicle_id).research_status == "missing"
        assert session.get(Vehicle, missing_id).specs is None
        assert session.get(Vehicle, omitted_id).specs is None
        partial = session.get(Vehicle, partial_id)
        assert partial.research_status == "incomplete"
        assert partial.specs.length_mm is None
        assert len(partial.specs.metadata_entries) == 1
        for vehicle_id in (low_id, unknown_id, null_confidence_id):
            assert session.get(Vehicle, vehicle_id).research_status == "unreliable"


@pytest.mark.parametrize("field, value", [("value", 0),
                                         ("value", -1),
                                         ("value", 1.5),
                                         ("value", "1800"),
                                         ("value", True),
                                         ("confidence", 0),
                                         ("confidence", 6),
                                         ("source_url", "not a URL"),
                                         ("extra", "unexpected")])
def test_rejects_invalid_sourced_values(field, value):
    candidate = _candidate(1, width_mm=1800)
    candidate["width_mm"][field] = value

    with pytest.raises(ValidationError):
        VehicleSpecCandidate.model_validate(candidate)


@pytest.mark.parametrize("tire_id", range(1, 9))
def test_accepts_known_tire_classes(tire_id):
    VehicleSpecCandidate.model_validate(_candidate(1, stock_tire_class=tire_id))


def test_rejects_unknown_tire_class():
    with pytest.raises(ValidationError):
        VehicleSpecCandidate.model_validate(_candidate(1, stock_tire_class=9))


def test_requires_all_spec_keys():
    candidate = _candidate(1)
    del candidate["width_mm"]

    with pytest.raises(ValidationError):
        VehicleSpecCandidate.model_validate(candidate)


def test_rejects_extra_candidate_fields():
    candidate = _candidate(1)
    candidate["extra"] = True

    with pytest.raises(ValidationError):
        VehicleSpecCandidate.model_validate(candidate)


@pytest.mark.parametrize("response_type", ["duplicate_ids", "unexpected_id", "invalid_value", "invalid_json"])
def test_rejects_invalid_batches_before_writing(engine, monkeypatch, response_type):
    vehicle_id = _add_vehicle(engine, "Unchanged")
    valid = _candidate(vehicle_id, **SPEC_VALUES)
    responses = {"duplicate_ids": _result([valid, valid]),
                 "unexpected_id": _result([valid, _candidate(vehicle_id + 100)]),
                 "invalid_value": _result([_candidate(vehicle_id, width_mm=0)]),
                 "invalid_json": subprocess.CompletedProcess(args=[], returncode=0, stdout="not JSON")}
    research = Mock(return_value=responses[response_type])
    monkeypatch.setattr(task.subprocess, "run", research)

    with pytest.raises(ValueError):
        task.run_task()

    with Session(engine) as session:
        assert session.get(Vehicle, vehicle_id).specs is None
        assert session.scalar(select(func.count()).select_from(VehicleSpecsMetadata)) == 0


def test_batches_vehicles_and_uses_the_research_schema(engine, monkeypatch):
    vehicle_ids = {_add_vehicle(engine, f"Car {index}") for index in range(26)}
    contexts = []

    def research(args, **kwargs):
        context = json.loads(kwargs["input"].split("Vehicles to research (JSON):\n")[1])
        contexts.append(context)
        assert 'web_search="live"' in args
        schema_path = Path(args[args.index("--output-schema") + 1])
        schema = json.loads(schema_path.read_text())
        for definition in [schema, *schema["$defs"].values()]:
            assert definition["additionalProperties"] is False
            assert set(definition["required"]) == set(definition["properties"])
        assert "date_set" not in schema["$defs"]["SourcedValue"]["properties"]
        source_schema = schema["$defs"]["SourcedValue"]["properties"]["source_url"]
        assert source_schema["type"] == "string"
        assert "format" not in source_schema
        return _result([_candidate(vehicle["vehicle_id"], **SPEC_VALUES) for vehicle in context])

    monkeypatch.setattr(task.subprocess, "run", Mock(side_effect=research))

    task.run_task()

    assert [len(context) for context in contexts] == [25, 1]
    assert {vehicle["vehicle_id"] for context in contexts for vehicle in context} == vehicle_ids
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(VehicleSpecs)) == 26
        assert session.scalar(select(func.count()).select_from(VehicleSpecsMetadata)) == 130
        assert all(vehicle.research_status == "complete" for vehicle in session.scalars(select(Vehicle)))


def test_later_research_failure_keeps_completed_batches(engine, monkeypatch):
    for index in range(26):
        _add_vehicle(engine, f"Car {index}")
    call_count = 0

    def research(args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise subprocess.CalledProcessError(1, args, stderr="research failed")
        context = json.loads(kwargs["input"].split("Vehicles to research (JSON):\n")[1])
        return _result([_candidate(vehicle["vehicle_id"], **SPEC_VALUES) for vehicle in context])

    monkeypatch.setattr(task.subprocess, "run", Mock(side_effect=research))

    with pytest.raises(subprocess.CalledProcessError):
        task.run_task()

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(VehicleSpecs)) == 25
        assert session.scalar(select(func.count()).select_from(VehicleSpecsMetadata)) == 125
        statuses = list(session.scalars(select(Vehicle.research_status)))
        assert statuses.count("complete") == 25
        assert statuses.count("missing") == 1


def test_database_failure_rolls_back_specs_and_metadata(engine, monkeypatch):
    vehicle_id = _add_vehicle(engine, "Rollback")

    def fail_metadata_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO") and "vehicle_specs_metadata" in statement:
            raise RuntimeError("metadata write failed")

    response = _result([_candidate(vehicle_id, **SPEC_VALUES)])
    monkeypatch.setattr(task.subprocess, "run", Mock(return_value=response))
    event.listen(engine, "before_cursor_execute", fail_metadata_insert)
    try:
        with pytest.raises(RuntimeError, match="metadata write failed"):
            task.run_task()
    finally:
        event.remove(engine, "before_cursor_execute", fail_metadata_insert)

    with Session(engine) as session:
        vehicle = session.get(Vehicle, vehicle_id)
        assert vehicle.specs is None
        assert vehicle.research_status == "missing"
        assert session.scalar(select(func.count()).select_from(VehicleSpecsMetadata)) == 0
