from __future__ import annotations

from datetime import UTC, datetime

from ouija import gitwalk, links, seance
from ouija.evaluation.mine import is_candidate_line, is_candidate_path, mine_repo, parse_diff
from ouija.ollama import LLMError
from ouija.rank import rank, tokens
from ouija.sources import Source, github_sources, passages
from ouija.verify import is_verbatim

# ---- git walk ----------------------------------------------------------------------------------


def test_walk_goes_past_the_reformat_to_the_origin(haunted_repo):
    repo, shas = haunted_repo
    commits = gitwalk.walk(repo, f"{shas['deletion']}^", "app.py", 2)
    assert [c.sha for c in commits] == [shas["format"], shas["origin"]]
    assert commits[-1].author == "Ada"
    assert "proxy drops the first packet" in commits[-1].body


def test_blame_stops_at_the_reformat(haunted_repo):
    repo, shas = haunted_repo
    assert gitwalk.blame(repo, f"{shas['deletion']}^", "app.py", 2) == shas["format"]


def test_line_at_and_missing_line(haunted_repo):
    repo, shas = haunted_repo
    assert gitwalk.line_at(repo, shas["origin"], "app.py", 2).strip() == "s.retry(1)"
    try:
        gitwalk.line_at(repo, shas["origin"], "app.py", 99)
    except gitwalk.GitError as e:
        assert "does not exist" in str(e)
    else:
        raise AssertionError("expected GitError")


def test_log_s_finds_oldest_first(haunted_repo):
    repo, shas = haunted_repo
    found = gitwalk.log_s(repo, shas["revert"], "app.py", "retry")
    assert found[0].sha == shas["origin"]


def test_main_identifier_skips_keywords():
    assert gitwalk.main_identifier("if config.yjit && defined?(RubyVM::YJIT.enable)") == "config"
    assert gitwalk.main_identifier("return nil") is None


# ---- links ---------------------------------------------------------------------------------------


def test_pr_numbers_from_messages():
    assert links.prs_in_message("Merge pull request #58332 from rails/fxn/revert") == [58332]
    assert links.prs_in_message("Fix the thing (#1234)\n\nbody") == [1234]
    assert links.prs_in_message("Refs #12 in passing") == []


def test_linked_issues():
    body = "Fixes #10. Also closes: #11 and https://github.com/o/r/issues/12 but not #13"
    assert links.linked_issues(body, "o", "r") == [10, 11, 12]


def test_parse_line_url():
    d = links.parse_line_url("https://github.com/rails/rails/blob/main/railties/lib/x.rb#L232")
    assert d == {
        "owner": "rails",
        "repo": "rails",
        "ref": "main",
        "path": "railties/lib/x.rb",
        "line": 232,
    }
    assert links.parse_line_url("https://example.com") is None


# ---- sources, passages, the quote checker --------------------------------------------------------


def _src(raw: str, kind: str = "pr") -> Source:
    return Source(
        id="pr:1", kind=kind, url="u", author="ada", created="2020-01-01T00:00:00Z", raw=raw
    )


def test_passages_are_verbatim_and_skip_templates_and_commands():
    raw = (
        "<!-- Thanks for your PR! Please fill in the template. -->\r\n"
        "#### What this PR does\r\n\r\n"
        "We retry once because the proxy drops the first packet after an idle period.\r\n\r\n"
        "/lgtm\r\n/kind bug\r\n\r\n"
        "Short."
    )
    ps = passages(_src(raw))
    texts = [p.text for p in ps]
    assert texts == ["We retry once because the proxy drops the first packet after an idle period."]
    assert all(is_verbatim(t, raw) for t in texts)


def test_long_paragraphs_are_cut_at_sentences():
    raw = " ".join(f"Sentence number {i} explains a small part of the reason." for i in range(40))
    ps = passages(_src(raw))
    assert len(ps) > 1 and all(len(p.text) <= 700 for p in ps)
    assert all(is_verbatim(p.text, raw) for p in ps)


def test_commit_subjects_survive_even_when_short():
    assert [p.text for p in passages(_src("Fix typo", kind="commit"))] == ["Fix typo"]


def test_signed_off_trailers_are_not_passages():
    raw = "Add retry\n\nSigned-off-by: Ada <a@x>"
    assert [p.text for p in passages(_src(raw, kind="commit"))] == ["Add retry"]


def test_is_verbatim_tolerates_rewrapping_only():
    src = "We retry once because\nthe proxy drops packets."
    assert is_verbatim("We retry once because the proxy drops packets.", src)
    assert not is_verbatim("We retry twice because the proxy drops packets.", src)
    assert not is_verbatim("   ", src)


def test_github_sources_drop_bots_and_anything_after_the_cutoff():
    gh = {
        "repos/o/r/pulls/5": {
            "number": 5, "title": "Retry", "body": "Fixes #9", "user": {"login": "ada"},
            "created_at": "2019-01-01T00:00:00Z", "html_url": "pr5",
        },
        "repos/o/r/issues/5/comments": [
            {"id": 1, "body": "/lgtm", "user": {"login": "k8s-ci-robot", "type": "Bot"}, "created_at": "2019-01-02T00:00:00Z", "html_url": "c1"},
            {"id": 2, "body": "Needed for the proxy.", "user": {"login": "bob"}, "created_at": "2019-01-02T00:00:00Z", "html_url": "c2"},
            {"id": 3, "body": "This broke after the removal!", "user": {"login": "cy"}, "created_at": "2024-06-01T00:00:00Z", "html_url": "c3"},
        ],
        "repos/o/r/pulls/5/comments": [],
        "repos/o/r/pulls/5/reviews": [],
        "repos/o/r/issues/9": {"number": 9, "title": "Packets lost", "body": "First packet after idle is lost.", "user": {"login": "dee"}, "created_at": "2018-12-01T00:00:00Z", "html_url": "i9"},
        "repos/o/r/issues/9/comments": [],
    }  # fmt: skip
    cutoff = datetime(2024, 1, 1, tzinfo=UTC)
    got = github_sources([5], gh, "o", "r", cutoff)
    assert [s.id for s in got] == ["pr:5", "pr_comment:2", "issue:9"]


# ---- ranking -------------------------------------------------------------------------------------


def test_tokens_split_camel_and_snake():
    assert tokens("RubyVM::YJIT.enable retry_once") == [
        "ruby",
        "vm",
        "yjit",
        "enable",
        "retry",
        "once",
    ]


def test_rank_keeps_commits_first_then_best_match(haunted_repo):
    from ouija.sources import Passage

    ps = [
        Passage("c#0", "commit:a", "Reformat with black"),
        Passage("p#0", "pr:1", "Unrelated chatter about CI"),
        Passage("p#1", "pr:1", "We retry the socket because the proxy drops packets"),
    ]
    kinds = {"commit:a": "commit", "pr:1": "pr"}
    got = rank(ps, "s.retry(1) socket", kinds, limit=2)
    assert [p.id for p in got] == ["c#0", "p#1"]


# ---- the séance ----------------------------------------------------------------------------------


def _run(haunted_repo, llm, github=None):
    repo, shas = haunted_repo
    ref = f"{shas['deletion']}^"
    commits = gitwalk.walk(repo, ref, "app.py", 2)
    return seance.run(
        owner="o",
        repo="r",
        path="app.py",
        line=2,
        line_text=gitwalk.line_at(repo, ref, "app.py", 2),
        commits=commits,
        github=github or {},
        llm=llm,
    )


def test_seance_quotes_the_origin_verbatim_and_names_the_ghost(haunted_repo, fake_llm):
    # P1 is the reformat's subject, P2 Ada's subject, P3 Ada's reason (walk order, commits first).
    llm = fake_llm({"found": True, "passages": ["P3"], "medium": "The spirit speaks of a proxy."})
    out = _run(haunted_repo, llm)
    assert out["silent"] is False
    assert out["ghost"]["name"] == "Ada" and out["ghost"]["login"] == "ada"
    assert out["blame"]["author"] == "Bob"
    [q] = out["quotes"]
    assert q["text"] == "The proxy drops the first packet after idle, so we retry once."
    assert q["is_ghost"] is True and q["kind"] == "commit"
    assert out["medium"] == "The spirit speaks of a proxy."
    # The model saw ids only in an enum: it cannot write the quote.
    schema = llm.calls[0]["schema"]
    assert schema["properties"]["passages"]["items"]["enum"][:3] == ["P1", "P2", "P3"]


def test_seance_falls_silent_when_nothing_is_a_reason(haunted_repo, fake_llm):
    out = _run(
        haunted_repo, fake_llm({"found": False, "passages": [], "medium": "I sense a reason!"})
    )
    assert out["silent"] is True
    assert out["silence"] == seance.SILENCE
    assert out["quotes"] == [] and out["medium"] == ""


def test_seance_ignores_ids_outside_the_enum_and_found_without_passages(haunted_repo, fake_llm):
    out = _run(haunted_repo, fake_llm({"found": True, "passages": ["P99", 3], "medium": "x"}))
    assert out["silent"] is True


def test_seance_survives_a_dead_model(haunted_repo, fake_llm):
    out = _run(haunted_repo, fake_llm(LLMError("timeout")))
    assert out["silent"] is True and out["stats"]["model_error"] == "timeout"


def test_plan_asks_for_prs_then_linked_issues():
    from ouija.gitwalk import Commit

    c = Commit(
        "a" * 40, "Ada", "a@x", "2019-01-01T00:00:00Z", "2019-01-01T00:00:00Z", "Retry (#5)", ""
    )
    first = seance.plan([c], {}, "o", "r")
    assert first[0] == "repos/o/r/pulls/5"
    gh = {p: [] for p in first}
    gh["repos/o/r/pulls/5"] = {"body": "Fixes #9", "number": 5}
    assert seance.plan([c], gh, "o", "r") == ["repos/o/r/issues/9", "repos/o/r/issues/9/comments"]


# ---- the miner -----------------------------------------------------------------------------------


def test_parse_diff_line_numbers():
    diff = (
        "diff --git a/x.rb b/x.rb\n--- a/x.rb\n+++ b/x.rb\n"
        "@@ -232 +232 @@ module Rails\n-        if config.yjit && defined?(X)\n+        if config.yjit\n"
    )
    d = parse_diff(diff)
    assert d["x.rb"]["removed"] == [(232, "        if config.yjit && defined?(X)")]
    assert d["x.rb"]["added"] == [(232, "        if config.yjit")]


def test_candidate_filters():
    assert is_candidate_path("lib/active_record/base.rb")
    assert not is_candidate_path("test/base_test.rb") and not is_candidate_path("pkg/x_test.go")
    assert not is_candidate_path("CHANGELOG.md")
    assert is_candidate_line("    s.retry( 1 )  # once")
    assert not is_candidate_line("    end") and not is_candidate_line("  # a comment line here")


def test_mine_finds_the_restored_line(haunted_repo):
    repo, shas = haunted_repo
    cases, stats = mine_repo(repo, "o/r")
    assert stats["kept"] == 1
    [c] = cases
    assert c.deletion == shas["deletion"] and c.parent == shas["format"]
    assert c.line == 2 and c.line_text.strip() == "s.retry( 1 )"
    assert c.cutoff.startswith("2024-01-01")


# ---- Entire agent-session checkpoints ------------------------------------------------------------


def test_entire_prompts_become_sources(tmp_path):
    import subprocess

    from ouija import entire

    repo = tmp_path / "r"
    repo.mkdir()

    def g(*a):
        out = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        return out.stdout.strip()

    g("init", "-q", "-b", "main")
    g("config", "user.name", "Ada")
    g("config", "user.email", "ada@example.com")
    (repo / "theme.css").write_text("iframe { background: white; }\n", encoding="utf-8")
    g("add", ".")
    g("commit", "-q", "-m", "Keep the preview light\n\nEntire-Checkpoint: 01ABCDEFGHJK")
    g("checkout", "-q", "--orphan", "cp")
    g("rm", "-rq", "--cached", ".")
    (repo / "theme.css").unlink()
    (repo / "0").mkdir()
    (repo / "0" / "prompt.txt").write_text(
        "The preview should stay in light mode, because authors test content as readers see it.",
        encoding="utf-8",
    )
    (repo / "0" / "metadata.json").write_text(
        '{"agent": "Claude Code", "created_at": "2026-10-01T00:00:00Z"}'
    )
    g("add", "0")
    g("commit", "-q", "-m", "Checkpoint")
    g("update-ref", "refs/entire/checkpoints/JK/01ABCDEFGHJK", "HEAD")
    g("checkout", "-q", "-f", "main")

    commits = gitwalk.walk(str(repo), "main", "theme.css", 1)
    assert entire.checkpoint_ids(commits[0].message) == ["01ABCDEFGHJK"]
    [src] = entire.sources(str(repo), commits, "o", "r", fetched=True)
    assert src.kind == "checkpoint" and src.author == "Ada"
    assert "because authors test content" in src.raw
    assert "Claude Code" in src.title
