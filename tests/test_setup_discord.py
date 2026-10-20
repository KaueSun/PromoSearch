"""Synthetic setup contracts; no real webhook or external request is used."""

import json
from types import SimpleNamespace

import pytest

from radar_gamer.http import ApiError
from tools import configure_discord as setup

URL = "https://discord.com/api/webhooks/123/TEST_ONLY_PRIVATE_TOKEN"
METADATA = {"id": "123", "type": 1, "channel_id": "456", "guild_id": "789"}


class Client:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.replies.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def test_cloud_confirms_delivery_without_printing_private_url(monkeypatch, capsys):
    client = Client([METADATA, {"id": "999"}])
    monkeypatch.setattr(setup, "Client", lambda: client)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", URL)
    assert setup.verify_cloud() == 0
    assert [kwargs.get("method", "GET") for _, kwargs in client.calls] == ["GET", "POST"]
    assert client.calls[1][0] == URL + "?wait=true"
    payload = json.loads(client.calls[1][1]["body"])
    assert payload["allowed_mentions"] == {"parse": []}
    assert "ainda esta em configuracao" in payload["embeds"][0]["description"]
    assert "price" not in str(payload)
    output = capsys.readouterr()
    assert URL not in output.out + output.err


@pytest.mark.parametrize("metadata", [
    {}, {**METADATA, "id": "999"}, {**METADATA, "type": 2},
    {**METADATA, "channel_id": None}, {**METADATA, "guild_id": None}, [],
])
def test_destination_must_match_actual_server_webhook(metadata):
    with pytest.raises(setup.SetupError):
        setup.validate_destination(Client([metadata]), URL)


@pytest.mark.parametrize("url", [
    "https://discord.com.evil.test/api/webhooks/123/TOKEN",
    URL + "?wait=true", URL + "\n", "http://discord.com/api/webhooks/123/TOKEN",
])
def test_invalid_link_is_blocked_before_any_request(url):
    client = Client([])
    with pytest.raises(ValueError):
        setup.validate_destination(client, url)
    assert client.calls == []


@pytest.fixture
def flow(monkeypatch):
    journal = {"names": [], "commands": [], "saved": [], "prompts": 0}

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
        return [{"name": name} for name in journal["names"]]

    def prompt():
        journal["prompts"] += 1
        return URL

    monkeypatch.setattr(setup, "run", command)
    monkeypatch.setattr(setup, "gh_json", api)
    monkeypatch.setattr(setup, "configure_environment", lambda _: None)
    monkeypatch.setattr(setup, "read_webhook", prompt)
    monkeypatch.setattr(setup, "Client", lambda: Client([METADATA]))
    monkeypatch.setattr(setup, "set_secret", lambda *args: journal["saved"].append(args))
    return journal


def test_setup_saves_only_webhook_and_dispatches_once(flow, capsys):
    assert setup.configure("owner/repo") == 0
    assert flow["saved"] == [("owner/repo", "DISCORD_WEBHOOK_URL", URL)]
    assert flow["commands"][-1] == [
        "gh", "workflow", "run", "discord.yml", "--repo", "owner/repo", "--ref", "main"
    ]
    output = capsys.readouterr()
    assert URL not in output.out + output.err + str(flow["commands"])


def test_existing_webhook_is_preserved_without_duplicate_test_message(flow):
    flow["names"] = ["DATABASE_URL", "TOKEN_ENCRYPTION_KEY", "DISCORD_WEBHOOK_URL"]
    assert setup.configure("owner/repo") == 0
    assert flow["saved"] == [] and flow["prompts"] == 0
    assert not any(argv[:3] == ["gh", "workflow", "run"] for argv in flow["commands"])


def test_wrong_account_cannot_receive_webhook(flow, monkeypatch):
    monkeypatch.setattr(setup, "gh_json", lambda *args: {"login": "another-owner"})
    with pytest.raises(setup.SetupError, match="proprietario"):
        setup.configure("owner/repo")
    assert flow["saved"] == [] and flow["prompts"] == 0


def test_failed_destination_never_saves_webhook(flow, monkeypatch):
    monkeypatch.setattr(setup, "Client", lambda: Client([ApiError("404")]))
    with pytest.raises(ApiError):
        setup.configure("owner/repo")
    assert flow["saved"] == []


def test_uncertain_dispatch_is_not_automatically_repeated(flow, monkeypatch):
    calls = []
    previous = setup.run

    def command(argv, **kwargs):
        if argv[:3] == ["gh", "workflow", "run"]:
            calls.append(argv)
            raise setup.SetupError("TEST_ONLY_COMMAND_ERROR")
        return previous(argv, **kwargs)

    monkeypatch.setattr(setup, "run", command)
    with pytest.raises(setup.SetupError, match="anterior pode ter sido aceita"):
        setup.configure("owner/repo")
    assert len(calls) == 1 and len(flow["saved"]) == 1


@pytest.mark.parametrize("error", [
    RuntimeError("TEST_ONLY_PRIVATE"), ApiError("404"), ApiError("network", ambiguous=True),
])
def test_library_errors_do_not_expose_credentials(error, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["setup", "--verify-only"])

    def fail():
        raise error

    monkeypatch.setattr(setup, "verify_cloud", fail)
    assert setup.main() == 1
    output = capsys.readouterr()
    assert "TEST_ONLY_PRIVATE" not in output.out + output.err


def test_private_dialog_masks_webhook_and_is_destroyed(monkeypatch):
    import sys

    calls = []
    root = SimpleNamespace(withdraw=lambda: None, destroy=lambda: calls.append("destroy"))

    def prompt(*args, **kwargs):
        assert kwargs["show"] == "*" and kwargs["parent"] is root
        return URL

    tk = SimpleNamespace(Tk=lambda: root, TclError=RuntimeError, simpledialog=SimpleNamespace(askstring=prompt))
    monkeypatch.setitem(sys.modules, "tkinter", tk)
    assert setup.read_webhook() == URL
    assert calls == ["destroy"]
