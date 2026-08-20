"""``api.main`` builds its FastAPI app at import time (``app = create_app()``),
so every test in the suite shares that one singleton via the ``client``
fixture — there's no safe way to re-import it in-process with different env
vars without risking cross-test pollution. Each case here spawns an isolated
subprocess instead.
"""

import subprocess
import sys

_IMPORT_SNIPPET = "from api.main import create_app; create_app(); print('STARTED')"


def _run(env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    import os

    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, "-c", _IMPORT_SNIPPET],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_refuses_to_start_with_default_secrets_outside_local() -> None:
    result = _run({"ENVIRONMENT": "staging"})
    assert result.returncode != 0
    assert "Refusing to start with insecure default secret" in result.stderr
    assert "jwt_secret" in result.stderr
    assert "session_secret" in result.stderr


def test_starts_outside_local_with_real_secrets_configured() -> None:
    result = _run(
        {
            "ENVIRONMENT": "staging",
            "JWT_SECRET": "a-real-unique-production-secret-value",
            "SESSION_SECRET": "another-real-unique-secret-value",
        }
    )
    assert result.returncode == 0, result.stderr
    assert "STARTED" in result.stdout


def test_local_environment_is_exempt_even_with_default_secrets() -> None:
    result = _run({"ENVIRONMENT": "local"})
    assert result.returncode == 0, result.stderr
    assert "STARTED" in result.stdout
