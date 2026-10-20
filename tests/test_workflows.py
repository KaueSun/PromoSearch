import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_production_workflow_security_and_schedule():
    text = (ROOT / ".github/workflows/monitor.yml").read_text(encoding="utf-8")
    config = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(config["on"]) == {"schedule", "workflow_dispatch"}
    assert config["on"]["schedule"][0]["cron"] == "7,37 * * * *"
    assert config["permissions"] == {"contents": "read"}
    job = config["jobs"]["monitor"]
    assert job["environment"] == "production"
    assert "default_branch" in job["if"]
    for step in job["steps"]:
        if "uses" in step:
            assert re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", step["uses"])
        assert "${{ inputs." not in step.get("run", "")
    assert "pull_request_target" not in text
    assert "--require-hashes" in text
    assert "vars.MONITOR_ENABLED == 'true'" in job["if"]
    assert "github.event_name == 'workflow_dispatch'" in job["if"]


def test_ci_has_no_production_credentials():
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "secrets." not in text and "environment: production" not in text
    config = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(config["on"]) == {"push", "pull_request"}
    assert "postgres" in config["jobs"]["test"]["services"]


def test_database_check_only_receives_database_secret():
    text = (ROOT / ".github/workflows/database.yml").read_text(encoding="utf-8")
    config = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(config["on"]) == {"workflow_dispatch"}
    assert config["permissions"] == {"contents": "read"}
    job = config["jobs"]["database"]
    assert job["environment"] == "production" and "default_branch" in job["if"]
    secret_names = re.findall(r"secrets\.([A-Z_]+)", text)
    assert secret_names == ["DATABASE_URL"]
    assert "python radar.py status" in text and "--send" not in text
