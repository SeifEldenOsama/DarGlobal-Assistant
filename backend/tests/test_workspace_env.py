from app.core.config import _WORKSPACE_ENV_FILE


def test_workspace_env_file_targets_repository_root() -> None:
    assert _WORKSPACE_ENV_FILE.name == ".env"
    assert _WORKSPACE_ENV_FILE.parent.name == "Tech Assigment"
