"""
Synchronize versioned chart definitions after Superset's idempotent import.
Skips charts not found in the DB (warns instead of crashing).
"""

import json
import logging
from pathlib import Path
from uuid import UUID

import yaml

from superset import db
from superset.app import create_app

logger = logging.getLogger(__name__)

app = create_app()
charts_dir = Path("/app/docker/dashboard/charts")

with app.app_context():
    from superset.models.slice import Slice

    for chart_file in charts_dir.glob("*.yaml"):
        config = yaml.safe_load(chart_file.read_text())
        try:
            chart = db.session.query(Slice).filter_by(uuid=UUID(config["uuid"])).one_or_none()
            if chart is None:
                logger.warning(
                    "Chart UUID %s not found in DB — skipping sync for %s",
                    config["uuid"],
                    chart_file.name,
                )
                continue
            chart.slice_name = config["slice_name"]
            chart.viz_type = config["viz_type"]
            chart.params = json.dumps(config["params"])
        except Exception as exc:
            logger.warning("Could not sync chart %s: %s", chart_file.name, exc)

    db.session.commit()

print("Dashboard chart definitions synchronized successfully")
