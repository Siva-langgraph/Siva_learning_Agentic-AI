"""settings.py — the failures students hit when starting the backend.

    "SESSION_SECRET (local) or SESSION_SECRET_ID (AWS) must be set" at the first sign-in
        local, no key            -> a random key, the app works
        local, SESSION_SECRET    -> that key
        AWS (ECS), no key        -> refuses, naming SESSION_SECRET_ID
    .env read only by run.py     -> read by settings.py, so `uvicorn app.main:app` reads it too
    another account's ARN in .env.example -> ARN read from agent/supervisor/deployment.json

Each case imports settings.py afresh in a clean environment.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SETTINGS = Path(__file__).resolve().parents[1] / "app" / "settings.py"
VARS = ("SESSION_SECRET", "SESSION_SECRET_ID", "ECS_CONTAINER_METADATA_URI_V4", "ECS_CONTAINER_METADATA_URI",
        "SUPERVISOR_ARN", "SUPERVISOR_URL", "APP_ENV_FILE", "APP_TABLE")


def fresh(monkeypatch, **env):
    for v in VARS:
        monkeypatch.delenv(v, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("settings_under_test", SETTINGS)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)     # a dataclass looks its module up while defined
    spec.loader.exec_module(module)
    return module


def test_local_without_a_key_uses_a_random_one(monkeypatch):
    s = fresh(monkeypatch, APP_ENV_FILE="none")
    key = s.session_secret()
    assert len(key) == 32 and key == s.session_secret()          # one key for the process


def test_local_with_a_key_uses_it(monkeypatch):
    assert fresh(monkeypatch, APP_ENV_FILE="none", SESSION_SECRET="k" * 40).session_secret() == b"k" * 40


def test_aws_without_a_key_refuses_and_says_which_variable(monkeypatch):
    s = fresh(monkeypatch, APP_ENV_FILE="none", ECS_CONTAINER_METADATA_URI_V4="http://169.254.170.2/v4/x")
    with pytest.raises(RuntimeError, match="SESSION_SECRET_ID"):
        s.session_secret()


def test_the_env_file_is_read_by_settings_itself(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text('# comment\nSESSION_SECRET="from-the-file"\nAPP_TABLE=ecom-webapp-test\n', encoding="utf-8")
    s = fresh(monkeypatch, APP_ENV_FILE=str(env))
    assert s.ENV_FILE == str(env) and s.session_secret() == b"from-the-file" and s.S.table == "ecom-webapp-test"


def test_a_variable_already_set_wins_over_the_env_file(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("SESSION_SECRET=from-the-file\n", encoding="utf-8")
    assert fresh(monkeypatch, APP_ENV_FILE=str(env), SESSION_SECRET="from-the-shell").session_secret() == b"from-the-shell"


def test_the_supervisor_arn_comes_from_the_deployment_file(monkeypatch, tmp_path):
    dep = tmp_path / "deployment.json"
    dep.write_text(json.dumps({"runtime_arn": "arn:aws:bedrock-agentcore:us-east-1:111:runtime/ecom_supervisor-x"}))
    s = fresh(monkeypatch, APP_ENV_FILE="none")
    monkeypatch.setattr(s, "SUPERVISOR_DEPLOYMENT", dep)
    assert s._supervisor_arn() == ("arn:aws:bedrock-agentcore:us-east-1:111:runtime/ecom_supervisor-x", str(dep))


def test_a_local_supervisor_url_wins_over_the_deployment_file(monkeypatch, tmp_path):
    dep = tmp_path / "deployment.json"
    dep.write_text(json.dumps({"runtime_arn": "arn:x"}))
    s = fresh(monkeypatch, APP_ENV_FILE="none", SUPERVISOR_URL="http://localhost:9000/")
    monkeypatch.setattr(s, "SUPERVISOR_DEPLOYMENT", dep)
    assert s._supervisor_arn() == ("", "")


def test_the_example_env_holds_no_account_and_no_key():
    text = (SETTINGS.parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "arn:aws:bedrock-agentcore:us-east-1:<your-account>" in text
    assert not any(line.startswith(("SUPERVISOR_ARN=", "SESSION_SECRET=")) for line in text.splitlines())
