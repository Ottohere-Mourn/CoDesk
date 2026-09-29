from pathlib import Path

from swcub.provenance import source_path_label


def test_source_path_label_distinguishes_repo_and_pinned_external_files(tmp_path):
    repo = tmp_path / "repo"
    osworld = tmp_path / "deps" / "osworld"
    other = tmp_path / "other"
    repo.mkdir()
    osworld.mkdir(parents=True)
    other.mkdir()

    assert source_path_label(repo / "runner.py", repo) == "runner.py"
    assert source_path_label(osworld / "agent.py", repo,
                             (("osworld-v2.1", osworld),)) == "osworld-v2.1/agent.py"
    assert source_path_label(other / "module.py", repo).startswith("external:")
