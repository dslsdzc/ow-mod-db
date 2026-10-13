import json
import sys

import httpx

import licenses


class FakeResp:
    def __init__(self, status: int, payload: dict | None = None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeClient:
    """按 slug 返回预置响应; 记录 (url, headers) 供断言; 值为 Exception 时抛出。"""

    def __init__(self, mapping: dict):
        self.mapping = mapping
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, headers=None):
        self.calls.append((url, dict(headers or {})))
        slug = url.split("/repos/", 1)[1]
        v = self.mapping[slug]
        if isinstance(v, Exception):
            raise v
        return v


def _payload(spdx):
    return FakeResp(200, {"license": {"spdx_id": spdx}})


# ---- repo_slug ----

def test_repo_slug_parses_common_forms():
    assert licenses.repo_slug("https://github.com/o/n") == "o/n"
    assert licenses.repo_slug("https://github.com/o/n/") == "o/n"
    assert licenses.repo_slug("https://github.com/o/n.git") == "o/n"
    assert licenses.repo_slug("") == ""
    assert licenses.repo_slug("https://gitlab.com/o/n") == ""
    assert licenses.repo_slug("https://github.com/o") == ""


# ---- fetch_license_spdx ----

def test_fetch_maps_status_and_license_variants():
    client = FakeClient({
        "o/mit": _payload("MIT"),
        "o/none": FakeResp(200, {"license": None}),
        "o/empty": FakeResp(200, {}),
        "o/noassert": _payload("NOASSERTION"),
        "o/gone": FakeResp(404),
        "o/err": httpx.ConnectError("boom"),
        "o/other": FakeResp(500),
    })
    assert licenses.fetch_license_spdx("o/mit", client) == "MIT"
    assert licenses.fetch_license_spdx("o/none", client) == "none"
    assert licenses.fetch_license_spdx("o/empty", client) == "none"
    assert licenses.fetch_license_spdx("o/noassert", client) == "NOASSERTION"
    assert licenses.fetch_license_spdx("o/gone", client) == "none"
    assert licenses.fetch_license_spdx("o/err", client) is None
    assert licenses.fetch_license_spdx("o/other", client) is None


def test_fetch_normalizes_noassertion_case():
    client = FakeClient({
        "o/upper": _payload("NOASSERTION"),
        "o/mixed": _payload("NoAssertion"),
        "o/lower": _payload("noassertion"),
    })
    assert licenses.fetch_license_spdx("o/upper", client) == "NOASSERTION"
    assert licenses.fetch_license_spdx("o/mixed", client) == "NOASSERTION"
    assert licenses.fetch_license_spdx("o/lower", client) == "NOASSERTION"


def test_fetch_sends_expected_url_and_headers():
    client = FakeClient({"o/mit": _payload("MIT")})
    licenses.fetch_license_spdx("o/mit", client)
    url, headers = client.calls[-1]
    assert url == "https://api.github.com/repos/o/mit"
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["User-Agent"] == "ow-mod-db-licenses/1.0"
    assert "Authorization" not in headers          # 无 token 不发授权头

    licenses.fetch_license_spdx("o/mit", client, token="tok123")
    _, headers = client.calls[-1]
    assert headers["Authorization"] == "Bearer tok123"


def test_fetch_rate_limited_on_403_and_429_with_slug():
    client = FakeClient({"o/a": FakeResp(403), "o/b": FakeResp(429)})
    for slug in ("o/a", "o/b"):
        try:
            licenses.fetch_license_spdx(slug, client)
            assert False, "应当抛 RateLimited"
        except licenses.RateLimited as e:
            assert e.args[0] == slug


# ---- scan ----

def _mod(uid, repo=""):
    return {"uniqueName": uid, "repo": repo}


def test_scan_incremental_only_missing(monkeypatch):
    official = {"releases": [_mod("A.B", "https://github.com/o/a"), _mod("C.D", "https://github.com/o/c")]}
    calls = []

    def fake_fetch(slug, client, token=""):
        calls.append(slug)
        return None

    monkeypatch.setattr(licenses, "fetch_license_spdx", fake_fetch)
    cache, notes = licenses.scan(official, {"A.B": "MIT"}, {})
    assert calls == ["o/c"]
    assert cache["A.B"] == "MIT"
    assert "C.D" not in cache
    assert notes == ["C.D: 查询失败, 保留旧值(未收录)"]


def test_scan_empty_official():
    cache, notes = licenses.scan({}, {}, {})
    assert cache == {} and notes == []


def test_scan_skips_empty_uid_and_marks_none_repo():
    official = {"releases": [_mod("", "https://github.com/o/x"), _mod("X.Y", "")]}
    cache, notes = licenses.scan(official, {}, {})
    assert cache == {"X.Y": "none"}
    assert notes == ["X.Y: (新收录) -> none"]


def test_scan_limit_caps_targets(monkeypatch):
    official = {"releases": [_mod(f"M{i}", f"https://github.com/o/r{i}") for i in range(4)]}
    seen = []

    def fake_fetch(slug, client, token=""):
        seen.append(slug)
        return "MIT"

    monkeypatch.setattr(licenses, "fetch_license_spdx", fake_fetch)
    licenses.scan(official, {}, {}, limit=2)
    assert len(seen) == 2                       # limit 生效(默认 0 = 全量)
    seen.clear()
    licenses.scan(official, {}, {})
    assert len(seen) == 4


def test_scan_passes_token_and_client_to_fetch(monkeypatch):
    official = {"releases": [_mod("A.B", "https://github.com/o/a")]}
    captured = {}

    def fake_fetch(slug, client, token=""):
        captured["slug"], captured["client"], captured["token"] = slug, client, token
        return "MIT"

    monkeypatch.setattr(licenses, "fetch_license_spdx", fake_fetch)
    licenses.scan(official, {}, {}, token="tok9")
    assert captured["slug"] == "o/a"
    assert isinstance(captured["client"], httpx.Client)   # 传入真实 client 而非其它值
    assert captured["token"] == "tok9"
    licenses.scan(official, {}, {})
    assert captured["token"] == ""                   # 默认 token 为空串


def test_scan_client_options(monkeypatch):
    official = {"releases": [_mod("A.B", "https://github.com/o/a")]}
    captured = {}

    class FakeHttpxClient:
        def __init__(self, **kw):
            captured.update(kw)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, headers=None):
            raise AssertionError("fetch 已被替换, 不应发请求")

    monkeypatch.setattr(licenses, "fetch_license_spdx", lambda slug, client, token="": "MIT")
    monkeypatch.setattr(licenses.httpx, "Client", FakeHttpxClient)
    licenses.scan(official, {}, {})
    assert captured == {"timeout": 20.0, "follow_redirects": True}


def test_scan_continues_on_failure_and_stops_on_rate_limit(monkeypatch):
    official = {"releases": [
        _mod("A.B", "https://github.com/o/a"),
        _mod("C.D", "https://github.com/o/c"),
        _mod("E.F", "https://github.com/o/e"),
    ]}
    calls = []

    def fake_fetch(slug, client, token=""):
        calls.append(slug)
        if slug == "o/a":
            return None                 # 失败: continue 到下一个目标
        raise licenses.RateLimited(slug)

    monkeypatch.setattr(licenses, "fetch_license_spdx", fake_fetch)
    notes = licenses.scan(official, {}, {})[1]
    assert calls == ["o/a", "o/c"]      # 失败后继续; 遇限速立即停止(不再查 o/e)
    assert notes[0] == "A.B: 查询失败, 保留旧值(未收录)"
    assert notes[1] == "GitHub API 限速(扫描到 o/c), 本次提前结束; 其余条目留待下次"


def test_scan_notes_are_precise(monkeypatch):
    official = {"releases": [_mod("A.B", "https://github.com/o/a"), _mod("C.D", "https://github.com/o/c")]}

    def fake_fetch(slug, client, token=""):
        return "Apache-2.0"

    monkeypatch.setattr(licenses, "fetch_license_spdx", fake_fetch)
    cache, notes = licenses.scan(official, {"A.B": "MIT"},
                                 {"A.B": "MIT", "C.D": "GPL-3.0"}, full=True)
    assert notes == [
        "A.B: MIT -> Apache-2.0",
        "C.D: (新收录) -> Apache-2.0",
        "A.B: 人工覆盖 Apache-2.0 -> MIT",
        "C.D: 人工覆盖 Apache-2.0 -> GPL-3.0",
    ]
    assert cache == {"A.B": "MIT", "C.D": "GPL-3.0"}


def test_scan_override_without_change_has_no_note():
    cache, notes = licenses.scan({}, {"A.B": "MIT"}, {"A.B": "MIT"})
    assert notes == []
    assert cache == {"A.B": "MIT"}


def test_scan_override_adds_note_without_previous_value():
    cache, notes = licenses.scan({}, {}, {"N.E": "MIT"})
    assert notes == ["N.E: 人工覆盖 (无) -> MIT"]
    assert cache == {"N.E": "MIT"}


def test_scan_failure_keeps_cached_value_in_note(monkeypatch):
    official = {"releases": [_mod("A.B", "https://github.com/o/a")]}
    monkeypatch.setattr(licenses, "fetch_license_spdx", lambda slug, client, token="": None)
    cache, notes = licenses.scan(official, {"A.B": "MIT"}, {}, full=True)
    assert notes == ["A.B: 查询失败, 保留旧值(MIT)"]   # 显示的是缓存中的旧值
    assert cache == {"A.B": "MIT"}


# ---- main / CLI ----

def test_cli_parser_defaults_and_help():
    parser = licenses.build_parser()
    assert parser.description == "Scan mod repo licenses into license_cache.json"
    args = parser.parse_args([])
    assert args.official == "source/official.json"
    assert args.cache == "source/license_cache.json"
    assert args.overrides == "source/license_overrides.json"
    assert args.full is False
    assert args.limit == 0
    helps = {a.option_strings[0]: a.help for a in parser._actions if a.option_strings}
    assert helps["--full"] == "全量重扫(默认只补缺失)"
    assert helps["--limit"] == "最多扫描 N 个(调试用)"


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_main_wires_args_token_and_saves(tmp_path, monkeypatch, capsys):
    official = _write(tmp_path, "official.json", {"releases": [{"uniqueName": "A.B"}]})
    cachep = _write(tmp_path, "cache.json", {})
    captured = {}

    def fake_scan(official_, cache_, overrides_, *, full, limit, token):
        captured.update(full=full, limit=limit, token=token, overrides=overrides_, official=official_)
        cache_["A.B"] = "MIT"
        return cache_, ["A.B: (新收录) -> MIT"]

    monkeypatch.setattr(licenses, "scan", fake_scan)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(sys, "argv", [
        "licenses.py", "--official", str(official), "--cache", str(cachep),
        "--full", "--limit", "3",
    ])
    licenses.main()
    out = capsys.readouterr().out
    assert captured["official"] == {"releases": [{"uniqueName": "A.B"}]}
    assert captured["full"] is True
    assert captured["limit"] == 3
    assert captured["token"] == "tok"
    assert captured["overrides"] == {}            # overrides 文件不存在时为空表
    assert "A.B: (新收录) -> MIT" in out
    assert "许可缓存: 1 项, 本次变更 1 条" in out
    assert json.loads(cachep.read_text(encoding="utf-8")) == {"A.B": "MIT"}


def test_main_reads_overrides_and_falls_back_to_gh_token(tmp_path, monkeypatch, capsys):
    official = _write(tmp_path, "official.json", {"releases": []})
    cachep = _write(tmp_path, "cache.json", {})
    overrides = _write(tmp_path, "overrides.json", {"X.Y": "MIT"})
    captured = {}

    def fake_scan(official_, cache_, overrides_, *, full, limit, token):
        captured.update(full=full, limit=limit, token=token, overrides=overrides_)
        return cache_, []

    monkeypatch.setattr(licenses, "scan", fake_scan)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "gh-tok")
    monkeypatch.setattr(sys, "argv", [
        "licenses.py", "--official", str(official), "--cache", str(cachep),
        "--overrides", str(overrides),
    ])
    licenses.main()
    out = capsys.readouterr().out
    assert captured["overrides"] == {"X.Y": "MIT"}
    assert captured["token"] == "gh-tok"
    assert captured["full"] is False and captured["limit"] == 0
    assert "警告" not in out
    assert "许可缓存: 0 项, 本次变更 0 条" in out


def test_main_warns_without_token(tmp_path, monkeypatch, capsys):
    official = _write(tmp_path, "official.json", {"releases": []})
    cachep = _write(tmp_path, "cache.json", {})

    monkeypatch.setattr(licenses, "scan", lambda *a, **kw: ({}, []))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", [
        "licenses.py", "--official", str(official), "--cache", str(cachep),
    ])
    licenses.main()
    lines = capsys.readouterr().out.splitlines()
    assert "  警告: 未设置 GITHUB_TOKEN, GitHub API 限制 60 次/小时(大库可能被限速)" in lines
