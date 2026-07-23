from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from policystrata import __version__


def test_current_package_version_has_release_tag() -> None:
    if os.environ.get("POLICYSTRATA_SKIP_RELEASE_TAG_TEST") == "1":
        pytest.skip("release tag check skipped for non-PyPI publish workflow")
    if not (Path(".") / ".git").exists():
        pytest.skip("release tag check requires a git checkout")

    result = subprocess.run(
        ["git", "tag", "--list", f"v{__version__}"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == f"v{__version__}"
