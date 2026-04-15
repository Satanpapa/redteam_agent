from pathlib import Path


def test_required_files_exist():
    required = [
        "README.md",
        "PROJECT_SUMMARY.md",
        "config.yaml",
        "code/models.py",
        "code/docker_sandbox.py",
        "code/llm_client.py",
        "containers/Dockerfile",
    ]
    for rel in required:
        assert Path(rel).exists(), rel


def test_config_mentions_feedback_loop():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "Planner → Decision Engine → Executor → Analyzer → Learner → Planner" in text
