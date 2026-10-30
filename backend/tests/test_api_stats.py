from __future__ import annotations

from fastapi.testclient import TestClient
from ouija import clones
from ouija.api import create_app
from ouija.config import Settings
from ouija.evaluation.stats import paired_bootstrap, summarise

# ---- stats ---------------------------------------------------------------------------------------


def test_paired_bootstrap_centres_on_the_difference():
    a = [1, 1, 1, 0, 1, 1, 0, 1]
    b = [0, 1, 0, 0, 1, 0, 0, 1]
    mean, lo, hi = paired_bootstrap(a, b, n=2000)
    assert mean == 3 / 8
    assert lo <= mean <= hi and lo >= -0.01


def test_summarise_counts_grades_by_method_blind():
    runs = {
        "b1": [
            {"case": "c1", "words": 5, "commits": ["x"]},
            {"case": "c2", "words": 4, "commits": ["o2"]},
        ],
        "b2": [
            {"case": "c1", "words": 50, "commits": ["x"]},
            {"case": "c2", "words": 40, "commits": ["o2"]},
        ],
        "b3": [
            {"case": "c1", "words": 9, "commits": ["o1"]},
            {"case": "c2", "words": 9, "commits": []},
        ],
        "seance": [
            {"case": "c1", "words": 20, "silent": False, "origin": "o1", "walk": ["x", "o1"]},
            {"case": "c2", "words": 5, "silent": True, "origin": "o2", "walk": ["o2"]},
        ],
    }
    blind = [{"gid": f"g{i}", "case": c} for i, c in enumerate(["c1"] * 4 + ["c2"] * 4)]
    methods = ["b1", "b2", "b3", "seance"] * 2
    key = {f"g{i}": m for i, m in enumerate(methods)}
    grades = dict(zip(key, ["N", "E", "N", "R", "N", "N", "N", "N"], strict=True))
    s = summarise(runs, blind, key, grades)
    assert s["methods"]["seance"]["reason_match"] == 1
    assert s["methods"]["b2"]["explains"] == 1
    assert s["blame_is_origin"] == 1 and s["log_s_has_origin"] == 1
    assert s["answerable"] == 1 and s["silent_when_unanswerable"] == 1


# ---- API -----------------------------------------------------------------------------------------


def test_health_and_empty_gallery(tmp_path, fake_llm):
    app = create_app(
        Settings(static_dir=str(tmp_path / "none"), gallery_dir=str(tmp_path)), llm=fake_llm({})
    )
    c = TestClient(app)
    assert c.get("/api/health").json()["ok"] is True
    assert c.get("/api/gallery").json() == []


def test_walk_plan_seance_end_to_end_without_network(haunted_repo, tmp_path, fake_llm, monkeypatch):
    repo, shas = haunted_repo
    monkeypatch.setattr(clones, "ensure", lambda *a, **k: repo)
    llm = fake_llm({"found": True, "passages": ["P3"], "medium": "A proxy, says the spirit."})
    app = create_app(Settings(static_dir=str(tmp_path / "none"), rate_per_minute=100), llm=llm)
    c = TestClient(app)
    w = c.post(
        "/api/walk",
        json={
            "owner": "o",
            "repo": "r",
            "ref": f"{shas['deletion']}^",
            "path": "app.py",
            "line": 2,
            "size_kb": 10,
        },
    )
    assert w.status_code == 200, w.text
    body = w.json()
    assert [x["author"] for x in body["commits"]] == ["Bob", "Ada"]
    assert {"repos/o/r/pulls/12", "repos/o/r/pulls/40"} <= set(body["need"])
    github = {p: None for p in body["need"]}
    assert (
        c.post("/api/plan", json={"walk_id": body["walk_id"], "github": github}).json()["need"]
        == []
    )
    s = c.post("/api/seance", json={"walk_id": body["walk_id"], "github": github}).json()
    assert s["ghost"]["name"] == "Ada" and s["silent"] is False
    assert "proxy drops the first packet" in s["quotes"][0]["text"]


def test_walk_refuses_big_repos_and_bad_names(tmp_path, fake_llm):
    app = create_app(
        Settings(static_dir=str(tmp_path / "none"), clone_dir=str(tmp_path)), llm=fake_llm({})
    )
    c = TestClient(app)
    big = {
        "owner": "kubernetes",
        "repo": "kubernetes",
        "ref": "main",
        "path": "x.go",
        "line": 1,
        "size_kb": 1_500_000,
    }
    r = c.post("/api/walk", json=big)
    assert r.status_code == 413 and "gallery" in r.json()["detail"]
    r = c.post("/api/walk", json={**big, "owner": "../etc", "size_kb": 10})
    assert r.status_code == 413


def test_unknown_walk_fades(tmp_path, fake_llm):
    c = TestClient(create_app(Settings(static_dir=str(tmp_path / "none")), llm=fake_llm({})))
    assert c.post("/api/seance", json={"walk_id": "nope", "github": {}}).status_code == 404
