import json
import os
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


class Config:
    def __init__(self):
        self.mta_api_key = os.getenv("MTA_API_KEY", "")
        self.update_interval = int(os.getenv("UPDATE_INTERVAL", "30"))
        self.routes_config = self._load_json("routes.json", {})
        self.display_config = self._load_json("display_config.json", self._default_display_config())
    
    def _load_json(self, filename: str, default: Any) -> Any:
        config_path = CONFIG_DIR / filename
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        return default
    
    def _default_display_config(self) -> Dict:
        return {
            "matrix_width": 64,
            "matrix_height": 32,
            "chain_length": 1,
            "parallel": 1,
            "brightness": 50,
            "led_rgb_sequence": "RGB",
            "pixel_mapper": "",
            "row_address_type": 0,
            "multiplexing": 0,
            "pwm_bits": 11,
            "show_refresh_rate": False,
            "gpio_slowdown": 1,
            "disable_hardware_pulsing": False
        }
    
    def get_routes(self) -> List[Dict]:
        return self.routes_config.get("routes", [])
    
    def get_display_settings(self) -> Dict:
        return self.display_config

