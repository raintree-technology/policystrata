from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_keeps_the_public_project_contract() -> None:
    text = README.read_text(encoding="utf-8")
    for required in (
        "<!-- project-record: policystrata -->",
        "**Active open-source project",
        "## See a failure",
        "## Evidence and limits",
        "## Raintree open-source system",
        "## Project policies",
    ):
        assert required in text
    assert sum(line.startswith("# ") for line in text.splitlines()) == 1
    assert text.index("uvx policystrata demo") < text.index("## Scan an application")


def test_published_package_readmes_keep_the_package_contract() -> None:
    root = README.parent
    for relative in ("packages/node/README.md", "packages/gateway/README.md"):
        text = (root / relative).read_text(encoding="utf-8")
        for required in ("**Active", "npm install", "Expected result", "support boundary"):
            assert required.lower() in text.lower(), f"{relative} is missing {required}"
        assert sum(line.startswith("# ") for line in text.splitlines()) == 1
