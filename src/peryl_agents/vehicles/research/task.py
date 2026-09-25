import subprocess
import sys
import tempfile
import json
import time
from dotenv import load_dotenv

from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from peryl_db.engine import engine
from peryl_db.models.vehicles import Vehicle, VehicleSpecs, VehicleSpecsMetadata
from peryl_agents.config import PROFILE_MEDIUM
from peryl_agents.batch_class import DataBatch
from peryl_agents.vehicles.research.validators import VehicleSpecCandidate, TIRE_CLASSES
from peryl_agents.utils import get_existing_records, get_task_prompt

env_path = Path(__file__).resolve().parents[5] / ".env"
load_dotenv(env_path)

TASK_NAME = "vehicle research"
BATCH_SIZE = 25
SPEC_FIELDS = ("width_mm",
               "length_mm",
               "height_mm",
               "curb_weight_kg",
               "stock_tire_class")

def run_task(max_duration_seconds=3600):
    """Research one pass, allowing an active batch to finish after the time limit."""
    deadline = time.monotonic() + max_duration_seconds
    if max_duration_seconds <= 0:
        return

    task_prompt = get_task_prompt(Path(__file__).parent, TASK_NAME)
    tire_class_context = "\n".join(f"{class_id}: {name}"
                                  for class_id, name in TIRE_CLASSES.items())

    with Session(engine) as session:
        vehicles = get_existing_records(session, Vehicle)
        vehicles_by_id = {vehicle.id: vehicle for vehicle in vehicles}
        pending = []

        for vehicle in vehicles:
            existing_specs = {}
            missing_fields = []
            for field in SPEC_FIELDS:
                value = None
                if vehicle.specs is not None:
                    value = getattr(vehicle.specs, field)
                existing_specs[field] = value
                if value is None:
                    missing_fields.append(field)

            if missing_fields:
                pending.append({"vehicle_id": vehicle.id,
                                "make": vehicle.make,
                                "model": vehicle.model,
                                "trim": vehicle.trim,
                                "model_year_start": vehicle.model_year_start,
                                "model_year_end": vehicle.model_year_end,
                                "existing_specs": existing_specs,
                                "missing_fields": missing_fields})

        if not pending:
            return

        schema = DataBatch[VehicleSpecCandidate].model_json_schema()

        with tempfile.TemporaryDirectory() as temp_dir:
            schema_path = Path(temp_dir) / "schema.json"
            with open(schema_path, "w") as f:
                json.dump(schema, f)

            for start in range(0, len(pending), BATCH_SIZE):
                batch_context = pending[start:start + BATCH_SIZE]
                requested_ids = {vehicle["vehicle_id"] for vehicle in batch_context}
                agent_prompt = f"""{task_prompt}

                Tire class IDs:
                {tire_class_context}
                
                Vehicles to research (JSON):
                {json.dumps(batch_context, indent=2)}
                """
                if time.monotonic() >= deadline:
                    break

                print(f"{TASK_NAME}: researching {len(batch_context)} vehicles")

                try:
                    result = subprocess.run(["codex",
                                            "exec",
                                            "--model", PROFILE_MEDIUM["model"],
                                            "--config", f'model_reasoning_effort="{PROFILE_MEDIUM["effort"]}"',
                                            "--config", 'web_search="live"',
                                            "--output-schema", schema_path,
                                            "--ephemeral",
                                            "-"],
                                            cwd=Path(__file__).resolve().parents[3],
                                            input=agent_prompt,
                                            capture_output=True,
                                            text=True,
                                            check=True)
                except subprocess.CalledProcessError as exc:
                    print(exc.stderr, file=sys.stderr)
                    raise
                print(result)
                batch = DataBatch[VehicleSpecCandidate].model_validate_json(result.stdout)
                returned_ids = set()
                for candidate in batch.data:
                    if candidate.vehicle_id not in requested_ids:
                        raise ValueError(f"Unexpected vehicle_id: {candidate.vehicle_id}")
                    if candidate.vehicle_id in returned_ids:
                        raise ValueError(f"Duplicate vehicle_id: {candidate.vehicle_id}")
                    returned_ids.add(candidate.vehicle_id)

                session.expire_all()
                # The database stores timestamps without a timezone; write them in UTC.
                date_set = datetime.now(timezone.utc).replace(tzinfo=None)
                for candidate in batch.data:
                    vehicle = vehicles_by_id[candidate.vehicle_id]
                    for field in SPEC_FIELDS:
                        sourced_value = getattr(candidate, field)
                        if sourced_value is None:
                            continue
                        if vehicle.specs is not None and getattr(vehicle.specs, field) is not None:
                            continue

                        if vehicle.specs is None:
                            vehicle.specs = VehicleSpecs()

                        setattr(vehicle.specs, field, sourced_value.value)
                        metadata = VehicleSpecsMetadata(variable=field,
                                                        source_url=str(sourced_value.source_url),
                                                        confidence=sourced_value.confidence,
                                                        date_set=date_set)
                        vehicle.specs.metadata_entries.append(metadata)

                for vehicle_id in requested_ids:
                    vehicle = vehicles_by_id[vehicle_id]
                    vehicle.research_status = _get_research_status(vehicle.specs)

                session.commit()


def _get_research_status(specs: VehicleSpecs | None) -> str:
    if specs is None:
        return "missing"

    missing_fields = [field for field in SPEC_FIELDS if getattr(specs, field) is None]
    if len(missing_fields) == len(SPEC_FIELDS):
        return "missing"
    if missing_fields:
        return "incomplete"

    metadata_entries = sorted(specs.metadata_entries,
                              key=lambda entry: (entry.date_set or datetime.min, entry.id or 0))
    metadata_by_field = {entry.variable: entry for entry in metadata_entries}
    for field in SPEC_FIELDS:
        metadata = metadata_by_field.get(field)
        if metadata is None or metadata.confidence is None or metadata.confidence < 4:
            return "unreliable"

    return "complete"

if __name__ == "__main__":
    run_task()
