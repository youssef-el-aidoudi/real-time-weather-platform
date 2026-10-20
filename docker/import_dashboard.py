"""Create a Superset import archive and import the versioned demo dashboard."""

import shutil
import subprocess
from pathlib import Path


source = Path("/app/docker/dashboard")
archive = Path("/tmp/france_live_weather")
zip_path = shutil.make_archive(
    str(archive),
    "zip",
    root_dir=source.parent,
    base_dir=source.name,
)

subprocess.run(
    ["superset", "import-dashboards", "--path", zip_path, "--username", "admin"],
    check=True,
)
print("France Live Weather dashboard imported successfully")
