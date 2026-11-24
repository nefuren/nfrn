"""LICENSE と README のライセンス記載が揃っていることを確認する（Issue #16）。"""

from app.config import REPO_DIR


def test_license_file_is_mit():
    text = (REPO_DIR / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License")
    assert "Permission is hereby granted, free of charge" in text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in text


def test_readme_has_license_section():
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    assert "## ライセンス" in readme
    section = readme.split("## ライセンス", 1)[1]
    assert "MIT" in section
    assert "(LICENSE)" in section
