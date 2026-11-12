import json
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

FTP_PRESETS = {
    "beginner": {
        "label": "Beginner (~75W FTP)",
        "max_target_watts": 150,
        "cadence_threshold": 80,
        "power_threshold_race": 90,
        "power_threshold_button_a": 130,
    },
    "average": {
        "label": "Average (~125W FTP)",
        "max_target_watts": 250,
        "cadence_threshold": 90,
        "power_threshold_race": 120,
        "power_threshold_button_a": 200,
    },
    "competitive": {
        "label": "Competitive (~200W FTP)",
        "max_target_watts": 350,
        "cadence_threshold": 95,
        "power_threshold_race": 180,
        "power_threshold_button_a": 280,
    },
    "pro": {
        "label": "Pro (~300W FTP)",
        "max_target_watts": 500,
        "cadence_threshold": 100,
        "power_threshold_race": 250,
        "power_threshold_button_a": 400,
    },
}

DEFAULT_CONFIG = {
    "trainer_mac_address": "XX:XX:XX:XX:XX:XX",
    "max_target_watts": 250,
    "cadence_threshold": 90,
    "power_threshold_race": 120,
    "power_threshold_button_a": 200,
    "gear_multiplier": 2.0,
    "auto_merge_device": "",
    "mappings": [
        {"source": "power", "target": "right_trigger"},
        {"source": "power", "target": "btn_a", "threshold": 200},
    ],
    "obc_transport": "",
    "obc_address": "",
    "obc_auto_connect": False,
    "obc_mappings": [
        {"source": "shift_up", "target": "btn_rb"},
        {"source": "shift_down", "target": "btn_lb"},
        {"source": "increase_difficulty", "target": "btn_rb"},
        {"source": "decrease_difficulty", "target": "btn_lb"},
        {"source": "nav_up", "target": "dpad_up"},
        {"source": "nav_down", "target": "dpad_down"},
        {"source": "nav_left", "target": "dpad_left"},
        {"source": "nav_right", "target": "dpad_right"},
        {"source": "select", "target": "btn_a"},
        {"source": "back", "target": "btn_b"},
        {"source": "menu", "target": "btn_start"},
        {"source": "camera_view", "target": "btn_r3"},
        {"source": "steer_left", "target": "left_stick_x"},
        {"source": "steer_right", "target": "left_stick_x"},
        {"source": "steering_angle", "target": "left_stick_x", "max_angle": 30},
        {"source": "brake", "target": "left_trigger"},
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
