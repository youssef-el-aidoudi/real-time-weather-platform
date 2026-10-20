"""
Tests for scripts/cities.py
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from cities import get_locations, load_cities


class TestLoadCities:
    def test_returns_only_active_cities(self):
        data = [
            {"city": "Paris", "latitude": 48.8566, "longitude": 2.3522, "active": True},
            {"city": "InactiveCity", "latitude": 0.0, "longitude": 0.0, "active": False},
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(data, f)
            tmp = Path(f.name)

        result = load_cities(tmp)
        assert len(result) == 1
        assert result[0]["city"] == "Paris"

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_cities(Path("/nonexistent/cities.json"))

    def test_cities_without_active_field_are_included(self):
        data = [{"city": "Lyon", "latitude": 45.764, "longitude": 4.835}]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(data, f)
            tmp = Path(f.name)

        result = load_cities(tmp)
        assert len(result) == 1


class TestGetLocations:
    def test_returns_five_french_cities(self):
        locations = get_locations()
        assert len(locations) == 5

    def test_all_french_cities_present(self):
        cities = {name for name, _, _ in get_locations()}
        assert cities == {"Paris", "Lyon", "Marseille", "Toulouse", "Dijon"}

    def test_coordinates_are_valid(self):
        for name, lat, lon in get_locations():
            assert -90.0 <= lat <= 90.0, f"{name}: invalid latitude {lat}"
            assert -180.0 <= lon <= 180.0, f"{name}: invalid longitude {lon}"

    def test_french_cities_in_france_latitude_range(self):
        """France metropolitan: latitudes roughly 42°N–51°N."""
        for name, lat, _ in get_locations():
            assert 41.0 <= lat <= 52.0, f"{name}: latitude {lat} is outside France"

    def test_french_cities_in_france_longitude_range(self):
        """France metropolitan: longitudes roughly -5°W to +8°E."""
        for name, _, lon in get_locations():
            assert -6.0 <= lon <= 9.0, f"{name}: longitude {lon} is outside France"
