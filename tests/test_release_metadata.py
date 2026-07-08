from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from policystrata import __version__


def test_current_package_version_has_release_tag() -> None:
    if not (Path(".") / ".git").exists():
        pytest.skip("release tag check requires a git checkout")

    result = subprocess.run(
        ["git", "tag", "--list", f"v{__version__}"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == f"v{__version__}"
