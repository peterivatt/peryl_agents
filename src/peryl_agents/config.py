from pathlib import Path
import tomllib

config_path = Path(__file__).parent / "agent_config.toml"

with open(config_path, "rb") as f:
    config = tomllib.load(f)

PROFILE_HIGH = config["profiles"]["high"]
PROFILE_MEDIUM = config["profiles"]["medium"]
PROFILE_LOW = config["profiles"]["low"]