import contextlib
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


@contextlib.contextmanager
def with_randpath() -> Generator[Path]:
    home = Path.home()
    folder = home / "".join(
        random.choice(string.ascii_letters) for _ in range(10)
    )
    folder.mkdir(parents=True, exist_ok=True)
    try:
        yield folder
    finally:
        shutil.rmtree(folder)


@pytest.fixture
def randpath() -> Generator[Path]:
    with with_randpath() as folder:
        yield folder


@pytest.fixture(autouse=True)
def override_home(monkeypatch: pytest.MonkeyPatch) -> None:
    with with_randpath() as randpath:
        monkeypatch.setenv("HOME", str(randpath))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(randpath / ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(randpath / ".local" / "share"))
        monkeypatch.setenv("XDG_CACHE_HOME", str(randpath / ".cache"))


@pytest.fixture
def dfpath(randpath: Path) -> Path:
    return randpath / ".dotfiles"


@pytest.fixture
def dfmanpath(randpath: Path) -> Path:
    return randpath / ".dfman"


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
