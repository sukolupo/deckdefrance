import json
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

DEFAULT_CONFIG = {
    "tacx_mac_address": "XX:XX:XX:XX:XX:XX",
    "max_target_watts": 300,
    "cadence_threshold": 95,
    "power_threshold_race": 150,
    "power_threshold_button_a": 250,
    "gear_multiplier": 2.0,
    "mappings": [
        {"source": "power", "target": "right_trigger"},
        {"source": "power", "target": "left_stick_y"},
    ],
}


def load_config() -> Dict[str, Any]:
    """Load configuration from file or return defaults."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_config() -> Dict[str, Any]:
    """Get current configuration."""
    return load_config()


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update configuration with new values."""
    config = load_config()
    config.update(updates)
    save_config(config)
    return config
