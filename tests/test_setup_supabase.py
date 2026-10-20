from argparse import Namespace
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from tools import configure_supabase as setup


def test_secret_values_only_travel_by_stdin(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(setup.subprocess, "run", fake_run)
    setup.set_secret("owner/repo", "DATABASE_URL", "TEST_ONLY_PRIVATE_VALUE")
    args, kwargs = calls[0]
    assert "TEST_ONLY_PRIVATE_VALUE" not in str(args)
    assert kwargs["input"] == "TEST_ONLY_PRIVATE_VALUE"
    assert kwargs["capture_output"] is True
    assert "shell" not in kwargs


def test_url_encodes_password_and_requires_certificate_verification():
    from urllib.parse import parse_qs, unquote, urlsplit

    url = setup.connection_url("a" * 20, "aws-1-ca-central-1.pooler.supabase.com", "TEST:/@?#% ONLY")
    parsed = urlsplit(url)
    assert unquote(parsed.password) == "TEST:/@?#% ONLY"
    assert parsed.hostname == "aws-1-ca-central-1.pooler.supabase.com"
    assert parse_qs(parsed.query) == {"sslmode": ["verify-full"], "sslrootcert": ["system"]}


def test_failed_command_does_not_leak_output(monkeypatch):
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            returncode=1, stdout="PRIVATE_TEST_OUTPUT", stderr="PRIVATE_TEST_SECRET"
        ),
    )
    with pytest.raises(setup.SetupError) as error:
        setup.run(["gh", "api", "user"])
    assert "PRIVATE_TEST" not in str(error.value)


def test_existing_reviewer_policy_is_preserved(monkeypatch):
    calls = []

    def api(*args, payload=None, **kwargs):
        calls.append((args, payload))
        if args == ("api", "repos/owner/repo/environments/production"):
            return {
                "deployment_branch_policy": None,
                "protection_rules": [
                    {"type": "wait_timer", "wait_timer": 5},
                    {
                        "type": "required_reviewers",
                        "prevent_self_review": True,
                        "reviewers": [{"type": "User", "reviewer": {"id": 1}}],
                    },
                ],
            }
        if args[-1].endswith("/deployment-branch-policies") and "POST" not in args:
            return {"branch_policies": []}
        return {}

    monkeypatch.setattr(setup, "gh_json", api)
    setup.configure_environment("owner/repo")
    import json

    payloads = [json.loads(p) for _, p in calls if p]
    assert payloads[0]["wait_timer"] == 5
    assert payloads[0]["reviewers"] == [{"type": "User", "id": 1}]
    assert payloads[0]["prevent_self_review"] is True
    assert payloads[1] == {"name": "main", "type": "branch"}


def test_stricter_protected_branch_policy_is_not_weakened(monkeypatch):
    calls = []
    monkeypatch.setattr(
        setup,
        "gh_json",
        lambda *a, **kw: calls.append(a) or {"deployment_branch_policy": {"protected_branches": True}},
    )
    setup.configure_environment("owner/repo")
    assert len(calls) == 1


@pytest.mark.parametrize(
    "repo,ref,host",
    [
        ("--evil", "a" * 20, "aws-1-ca-central-1.pooler.supabase.com"),
        ("owner/repo", "bad", "aws-1-ca-central-1.pooler.supabase.com"),
        ("owner/repo", "a" * 20, "pooler.supabase.com.evil.test"),
    ],
)
def test_rejects_unexpected_destinations_before_access(repo, ref, host, monkeypatch):
    monkeypatch.setattr(setup, "gh_json", lambda *a, **kw: pytest.fail("Should not contact GitHub"))
    with pytest.raises(setup.SetupError):
        setup.execute(Namespace(repo=repo, project_ref=ref, pooler_host=host))


def test_unexpected_library_error_is_sanitized(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "setup",
            "--repo",
            "owner/repo",
            "--project-ref",
            "a" * 20,
            "--pooler-host",
            "aws-1-ca-central-1.pooler.supabase.com",
        ],
    )

    def failed(_):
        raise RuntimeError("PRIVATE_TEST_PASSWORD_OR_URL")

    monkeypatch.setattr(setup, "execute", failed)
    assert setup.main() == 1
    out = capsys.readouterr()
    assert "PRIVATE_TEST" not in out.out + out.err


@pytest.fixture
def operator_flow(monkeypatch, tmp_path):
    args = Namespace(
        repo="owner/repo", project_ref="a" * 20, pooler_host="aws-1-ca-central-1.pooler.supabase.com"
    )
    journal = {
        "secret_names": [],
        "saved": {},
        "database": [],
        "commands": [],
        "passwords": [
            "TEST_ONLY_ADMIN_PRIVATE",
            "TEST_ONLY_APP_PASSWORD_123456789",
            "TEST_ONLY_APP_PASSWORD_123456789",
        ],
    }

    def command(argv, **kwargs):
        journal["commands"].append(argv)
        if argv[:4] == ["git", "remote", "get-url", "origin"]:
            return "https://github.com/owner/repo.git"
        if argv[:3] == ["git", "branch", "--show-current"]:
            return "main"
        return ""

    def api(*argv, **kwargs):
        if argv == ("api", "user"):
            return {"login": "owner"}
        return [{"name": n} for n in journal["secret_names"]]

    monkeypatch.setattr(setup, "run", command)
    monkeypatch.setattr(setup, "gh_json", api)
    monkeypatch.setattr(setup, "configure_environment", lambda _: None)
    monkeypatch.setattr(setup.getpass, "getpass", lambda _: journal["passwords"].pop(0))
    monkeypatch.setattr(setup, "configure_database", lambda *a: journal["database"].append(a))
    monkeypatch.setattr(setup, "set_secret", lambda repo, name, value: journal["saved"].update({name: value}))
    monkeypatch.setattr(setup.tempfile, "TemporaryDirectory", lambda **kw: nullcontext(str(tmp_path)))
    return args, journal


def test_operator_flow_never_sends_admin_password_to_github(operator_flow, capsys):
    import base64

    args, journal = operator_flow
    assert setup.execute(args) == 0
    assert journal["database"][0][2] == "TEST_ONLY_ADMIN_PRIVATE"
    assert "TEST_ONLY_APP_PASSWORD_123456789" in journal["saved"]["DATABASE_URL"]
    assert "TEST_ONLY_ADMIN_PRIVATE" not in str(journal["saved"])
    assert len(base64.urlsafe_b64decode(journal["saved"]["TOKEN_ENCRYPTION_KEY"])) == 32
    output = capsys.readouterr()
    assert "TEST_ONLY_ADMIN_PRIVATE" not in output.out + output.err
    assert "TEST_ONLY_APP_PASSWORD" not in output.out + output.err
    assert journal["commands"][-1] == [
        "gh",
        "workflow",
        "run",
        "database.yml",
        "--repo",
        "owner/repo",
        "--ref",
        "main",
    ]


def test_existing_database_and_encryption_key_are_not_rotated(operator_flow):
    args, journal = operator_flow
    journal["secret_names"] = ["DATABASE_URL", "TOKEN_ENCRYPTION_KEY"]
    assert setup.execute(args) == 0
    assert not journal["saved"] and not journal["database"]
    assert len(journal["passwords"]) == 3


def test_password_mismatch_stops_before_database_or_secret_changes(operator_flow):
    args, journal = operator_flow
    journal["passwords"][-1] = "TEST_ONLY_MISMATCH"
    with pytest.raises(setup.SetupError, match="confirmacao diferente"):
        setup.execute(args)
    assert not journal["database"] and not journal["saved"]
