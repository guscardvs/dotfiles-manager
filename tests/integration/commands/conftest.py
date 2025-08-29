import random
import shutil
import string
from collections.abc import Generator
from pathlib import Path

import pytest

from dotfile_manager.app import app
from dotfile_manager.manifest.concepts import ManifestFormat
from dotfile_manager.manifest.loader import loaders
from dotfile_manager.manifest.schema import Manifest


@pytest.fixture
def dfpath(tmp_path: Path) -> Path:
    return tmp_path / ".dotfiles"


@pytest.fixture
def dfmanpath(tmp_path: Path) -> Path:
    return tmp_path / ".dfman"


@pytest.fixture
def randpath() -> Generator[Path]:
    home = Path.home()
    folder = home / "".join(
        random.choice(string.ascii_letters) for _ in range(10)
    )
    folder.mkdir(parents=True, exist_ok=True)
    yield folder
    shutil.rmtree(folder)


@pytest.fixture
def loaded_manifest(dfpath: Path, dfmanpath: Path) -> Manifest:
    manifest_format = ManifestFormat.TOML
    dfman_real_path = dfmanpath.with_suffix(f".{manifest_format}")
    _ = app(
        [
            "init",
            "--manifest-path",
            str(dfmanpath),
            "--repository-path",
            str(dfpath),
            "--manifest-format",
            str(manifest_format),
            "--repository-branch",
            "develop",
            "--default-terminal",
            "zsh",
            "--default-editor",
            "nano",
            "--repository-url",
            "https://example.com/repo.git",
        ]
    )
    return loaders[manifest_format](dfman_real_path)
