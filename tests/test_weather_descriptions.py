"""
Tests for insert_records.py — unit tests that do NOT require a live database.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from insert_records import WEATHER_DESCRIPTIONS


class TestWeatherDescriptions:
    def test_clear_sky_code_exists(self):
        assert 0 in WEATHER_DESCRIPTIONS
        assert WEATHER_DESCRIPTIONS[0] == "Clear sky"

    def test_thunderstorm_code_exists(self):
        assert 95 in WEATHER_DESCRIPTIONS

    def test_all_values_are_non_empty_strings(self):
        for code, desc in WEATHER_DESCRIPTIONS.items():
            assert isinstance(code, int), f"Key {code!r} is not int"
            assert isinstance(desc, str) and len(desc) > 0, f"Code {code}: empty description"

    def test_key_wmo_codes_present(self):
        expected = {0, 1, 2, 3, 45, 48, 61, 63, 65, 71, 73, 75, 80, 81, 82, 95}
        missing = expected - set(WEATHER_DESCRIPTIONS.keys())
        assert not missing, f"Missing WMO codes: {missing}"

    def test_unknown_code_falls_back_gracefully(self):
        unknown = 999
        result = WEATHER_DESCRIPTIONS.get(unknown, f"WMO code {unknown}")
        assert result == "WMO code 999"
