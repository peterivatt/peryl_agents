"""
This is the api between the agents and the database.
For specific research they should be pointed at the appropriate subfolder
such as vehicles.
"""
from pathlib import Path
from dotenv import load_dotenv
from peryl_agents.vehicles.discovery.task import run_task

env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(env_path)

if __name__ == "__main__":
    env_path = Path(__file__).resolve().parents[3] / ".env"
    load_dotenv(env_path)

    run_task()
