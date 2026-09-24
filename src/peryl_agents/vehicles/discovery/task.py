import subprocess
import sys
import tempfile
import json

from pathlib import Path
from peryl_agents.vehicles.discovery.reader import get_existing_vehicles
from sqlalchemy.orm import Session
from peryl_db.engine import engine
from peryl_agents.config import PROFILE_MEDIUM
from peryl_agents.vehicles.discovery.validator import VehicleDiscoveryBatch
from peryl_agents.vehicles.discovery.writer import save_vehicle_batch


TASK_NAME = "vehicle research"

def run_task():
    prompt_path = Path(__file__).parent / "task_prompt.md"
    if prompt_path.exists():
        with open(prompt_path, "r") as f:
            task_prompt = f.read()
    else:
        raise FileNotFoundError(f"Task: {TASK_NAME} missing task prompt file.")

    with Session(engine) as session:
        vehicles = get_existing_vehicles(session)

        vehicle_context = "\n".join(f"{vehicle.make}, "
                                    f"{vehicle.model}, "
                                    f"{vehicle.model_year_start}, "
                                    f"{vehicle.model_year_end}, "
                                    f"{vehicle.trim}"
                                    for vehicle in vehicles)
        if not vehicle_context:
            vehicle_context = "None"
        print(vehicle_context)
        agent_prompt = f"""
        {task_prompt}
    
        Current vehicles in the Peryl database:
    
        {vehicle_context}
        """

        schema = VehicleDiscoveryBatch.model_json_schema()

        with tempfile.TemporaryDirectory() as temp_dir:
            schema_path = Path(temp_dir) / "schema.json"
            with open(schema_path, "w") as f:
                json.dump(schema, f)

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

        batch = VehicleDiscoveryBatch.model_validate_json(result.stdout)
        save_vehicle_batch(session, batch)
