import subprocess
import sys
import tempfile
import json
import time
from dotenv import load_dotenv

from pathlib import Path
from sqlalchemy.orm import Session
from peryl_db.engine import engine
from peryl_db.models.vehicles import Vehicle
from peryl_agents.config import PROFILE_MEDIUM
from peryl_agents.batch_class import DataBatch
from peryl_agents.vehicles.discovery.validators import VehicleDiscovery
from peryl_agents.utils import get_existing_records, save_batch, get_task_prompt

env_path = Path(__file__).resolve().parents[5] / ".env"
load_dotenv(env_path)

TASK_NAME = "vehicle discovery"

def run_task(max_duration_seconds=3600):
    """Discover until the time limit, allowing an active batch to finish."""
    deadline = time.monotonic() + max_duration_seconds
    if max_duration_seconds <= 0:
        return

    task_prompt = get_task_prompt(Path(__file__).parent, TASK_NAME)

    with Session(engine) as session:
        schema = DataBatch[VehicleDiscovery].model_json_schema()

        with tempfile.TemporaryDirectory() as temp_dir:
            schema_path = Path(temp_dir) / "schema.json"
            with open(schema_path, "w") as f:
                json.dump(schema, f)

            while time.monotonic() < deadline:
                vehicles = get_existing_records(session, Vehicle)

                vehicle_context = "\n".join(f"{vehicle.make}, "
                                            f"{vehicle.model}, "
                                            f"{vehicle.model_year_start}, "
                                            f"{vehicle.model_year_end}, "
                                            f"{vehicle.trim}"
                                            for vehicle in vehicles)
                if not vehicle_context:
                    vehicle_context = "None"
                agent_prompt = f"""
                {task_prompt}

                Current vehicles in the Peryl database:

                {vehicle_context}
                """
                if time.monotonic() >= deadline:
                    break

                print(vehicle_context)
                try:
                    result = subprocess.run(["codex",
                                            "exec",
                                            "--model", PROFILE_MEDIUM["model"],
                                            "--config", f'model_reasoning_effort="{PROFILE_MEDIUM["effort"]}"',
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

                batch = DataBatch[VehicleDiscovery].model_validate_json(result.stdout)
                save_batch(session, batch, Vehicle)

if __name__ == "__main__":
    run_task()
