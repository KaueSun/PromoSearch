"""Synthetic OAuth responses only; never opens a live authorization or account."""

import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlencode

import pytest

from tools import prepare_meli_callback as setup

ROOT = Path(__file__).resolve().parents[1]
STATE = "A" * 43
NODE = shutil.which("node")


def page_response(query, *, expire=False, clipboard_error=False):
    if not NODE:
        pytest.skip("Node.js is required to execute the callback JavaScript")
    harness = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const nodes = {title: {}, status: {}, copy: {disabled: true}};
const handlers = {};
nodes.copy.addEventListener = (name, callback) => { handlers[name] = callback; };
const history = [], clipboard = [], timers = [];
const window = {
  location: {search: input.query, pathname: '/PromoSearch/oauth-callback.html'},
  history: {replaceState: (...args) => history.push(args)},
  setTimeout: (callback, milliseconds) => timers.push({callback, milliseconds})
};
const navigator = {clipboard: {writeText: async (value) => {
  if (input.clipboard_error) throw new Error('denied');
  clipboard.push(value);
}}};
vm.runInNewContext(fs.readFileSync('docs/oauth-callback.js', 'utf8'), {
  window, navigator, URLSearchParams,
  document: {getElementById: id => nodes[id]}
});
(async () => {
  if (input.expire) for (const timer of timers) timer.callback();
  if (handlers.click) await handlers.click();
  process.stdout.write(JSON.stringify({nodes, history, clipboard, timerDelays: timers.map(t => t.milliseconds)}));
})().catch(() => process.exit(1));
"""
    result = subprocess.run(
        [NODE, "-e", harness], cwd=ROOT,
        input=json.dumps(dict(query=query, expire=expire, clipboard_error=clipboard_error)),
        text=True, encoding="utf-8", capture_output=True, check=True, timeout=15,
    )
    return json.loads(result.stdout)


def test_callback_transfers_only_code_and_state_after_explicit_click():
    result = page_response("?" + urlencode({"code": "TEST_ONLY_CODE", "state": STATE, "user_id": "123"}))
    assert result["history"] == [[None, "", "/PromoSearch/oauth-callback.html"]]
    assert json.loads(result["clipboard"][0]) == {"code": "TEST_ONLY_CODE", "state": STATE}
    assert result["timerDelays"] == [300000]
    assert "TEST_ONLY_CODE" not in str(result["nodes"])


@pytest.mark.parametrize("query", [
    "", "?error=access_denied&error_description=TEST_ONLY_PRIVATE",
    "?code=TEST_ONLY_CODE", "?state=" + STATE,
    "?code=TEST_ONLY_CODE&state=bad", "?code=TEST_ONLY_CODE&state=" + STATE + "&state=" + STATE,
    "?code=TEST_ONLY_CODE&code=SECOND_CODE&state=" + STATE,
    "?code=TEST_ONLY%0ACODE&state=" + STATE,
])
def test_bad_denied_or_missing_response_never_enables_copy(query):
    result = page_response(query)
    assert result["nodes"]["copy"]["disabled"] is True
    assert result["clipboard"] == []
    assert "TEST_ONLY_PRIVATE" not in str(result["nodes"])
    assert result["history"] == [[None, "", "/PromoSearch/oauth-callback.html"]]


def test_page_discards_temporary_return_after_five_minutes():
    result = page_response("?" + urlencode({"code": "TEST_ONLY_CODE", "state": STATE}), expire=True)
    assert result["clipboard"] == [] and result["nodes"]["copy"]["disabled"] is True


def test_clipboard_denial_does_not_expose_return_in_ui():
    result = page_response("?" + urlencode({"code": "TEST_ONLY_CODE", "state": STATE}), clipboard_error=True)
    assert result["clipboard"] == []
    assert "não permitiu copiar" in result["nodes"]["status"]["textContent"]
    assert "TEST_ONLY_CODE" not in str(result["nodes"])


def test_page_has_no_external_resources_or_credential_forms():
    from html.parser import HTMLParser

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append((tag, dict(attrs)))

    parser = Parser()
    parser.feed((ROOT / "docs/oauth-callback.html").read_text(encoding="utf-8"))
    assert not any(tag in {"form", "input", "iframe"} for tag, _ in parser.tags)
    assert {attrs["src"] for _, attrs in parser.tags if "src" in attrs} == {"oauth-callback.js"}
    metas = {attrs.get("name", attrs.get("http-equiv")): attrs.get("content")
             for tag, attrs in parser.tags if tag == "meta"}
    assert metas["referrer"] == "no-referrer"
    assert "connect-src 'none'" in metas["Content-Security-Policy"]
    source = (ROOT / "docs/oauth-callback.js").read_text(encoding="utf-8")
    assert not any(word in source for word in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage", "console."))


@pytest.fixture
def publisher(monkeypatch):
    journal = {"existing": None, "api": [], "commands": []}

    def run(argv, **kwargs):
        journal["commands"].append(argv)
        if argv[:3] == ["git", "branch", "--show-current"]:
            return "main"
        if argv[:4] == ["git", "remote", "get-url", "origin"]:
            return "https://github.com/owner/repo.git"
        return ""

    def api(*argv, **kwargs):
        journal["api"].append((argv, kwargs))
        if argv == ("api", "user"):
            return {"login": "owner"}
        if argv == ("api", "repos/owner/repo"):
            return {"private": False, "default_branch": "main"}
        if argv == ("api", "repos/owner/repo/pages"):
            return journal["existing"]
        return {}

    monkeypatch.setattr(setup, "run", run)
    monkeypatch.setattr(setup, "gh_json", api)
    return journal


def test_publisher_uses_only_public_docs_and_never_changes_secrets(publisher):
    assert setup.prepare("owner/repo") == 0
    post = [(args, kw) for args, kw in publisher["api"] if "POST" in args]
    assert len(post) == 1
    assert json.loads(post[0][1]["payload"]) == {
        "build_type": "legacy", "source": {"branch": "main", "path": "/docs"}
    }
    assert publisher["commands"][-1] == ["git", "push", "origin", "main"]
    assert "secret" not in str(publisher["api"]) + str(publisher["commands"])


def test_different_existing_site_is_preserved(publisher):
    publisher["existing"] = {"build_type": "legacy", "source": {"branch": "main", "path": "/"}}
    with pytest.raises(setup.SetupError, match="preservado"):
        setup.prepare("owner/repo")
    assert not any("POST" in args for args, _ in publisher["api"])
    assert ["git", "push", "origin", "main"] not in publisher["commands"]


def test_unchanged_pages_configuration_is_reused(publisher):
    publisher["existing"] = {"build_type": "legacy", "source": {"branch": "main", "path": "/docs"}}
    assert setup.prepare("owner/repo") == 0
    assert not any("POST" in args for args, _ in publisher["api"])


def test_wrong_account_cannot_publish(publisher, monkeypatch):
    monkeypatch.setattr(setup, "gh_json", lambda *args: {"login": "another"})
    with pytest.raises(setup.SetupError, match="proprietario"):
        setup.prepare("owner/repo")
    assert not publisher["commands"]


def test_return_url_belongs_to_owner_and_repository():
    assert setup.callback_url("KaueSun/PromoSearch") == "https://kauesun.github.io/PromoSearch/oauth-callback.html"
    with pytest.raises(setup.SetupError):
        setup.callback_url("evil.test/path/extra")
