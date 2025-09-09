from collections.abc import MutableMapping
from typing import Any, cast
from escudeiro.data import fromdict
import pytest
from pathlib import Path

import tomlkit
from dotfile_manager.app import app
from dotfile_manager.manifest.loader import dumpers, loaders
from dotfile_manager.manifest.schema import Dotfile, Manifest


class TestCheck:
    def test_check(
        self,
        loaded_manifest: Manifest,
        dfmanpath: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        dfman = dfmanpath.with_suffix(f".{loaded_manifest.original_format}")
        dotfiles = [
            Dotfile("text.txt", "text.txt", "text.txt", "Example text file"),
            Dotfile(
                "script.sh", "script.sh", "script.sh", "Example script file"
            ),
            Dotfile(
                "missing.txt",
                "missing.txt",
                "missing.txt",
                "Missing file example",
            ),
        ]
        loaded_manifest.dotfiles.extend(dotfiles)
        _ = dfman.write_text(
            dumpers[loaded_manifest.original_format](loaded_manifest)
        )

        _ = app(["check", "--manifest-path", str(dfman)])
        captured = (
            capsys.readouterr()
            .out.replace(
                "Manifest printed successfully. Use a terminal that supports color for better readability.",
                "",
            )
            .strip()
        )
        result = cast(MutableMapping[str, Any], tomlkit.loads(captured))
        result.setdefault("original_format", loaded_manifest.original_format)

        # assuming the output is toml
        assert fromdict(Manifest, result["dotfile_manager"]) == loaded_manifest
