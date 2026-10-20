"""
City configuration loader.
Add or remove cities by editing config/cities.json only.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# Resolves to <project_root>/config/cities.json regardless of where the script runs
_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "cities.json"


def load_cities(config_path: Path = _DEFAULT_CONFIG) -> List[Dict]:
    """Load active cities from the JSON config file."""
    if not config_path.exists():
        raise FileNotFoundError(f"City config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        cities = json.load(f)
    active = [c for c in cities if c.get("active", True)]
    logger.info(f"Loaded {len(active)} active cities from {config_path.name}")
    return active


def get_locations(config_path: Path = _DEFAULT_CONFIG) -> List[Tuple[str, float, float]]:
    """Return list of (city, latitude, longitude) tuples."""
    cities = load_cities(config_path)
    return [(c["city"], c["latitude"], c["longitude"]) for c in cities]
