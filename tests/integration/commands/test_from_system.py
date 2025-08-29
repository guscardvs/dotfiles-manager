from pathlib import Path

from pytest import CaptureFixture
from dotfile_manager.manifest.schema import Manifest, path_as_posix
from dotfile_manager.app import app
from unittest.mock import MagicMock, Mock, patch


class TestFromSystem:
    @patch("questionary.confirm")
    def test_from_system_success(
        self,
        questionary_confirm_mock: MagicMock,
        loaded_manifest: Manifest,
        dfpath: Path,
        dfmanpath: Path,
        randpath: Path,
        capsys: CaptureFixture,
    ):
        questionary_confirm_mock.return_value.ask.return_value = True
        sample_file = randpath / "sample.txt"
        _ = sample_file.write_text("Sample content")

        _ = app(
            [
                "from-system",
                "--manifest-path",
                str(
                    dfmanpath.with_suffix(
                        f".{loaded_manifest.original_format}"
                    )
                ),
                "--dotfiles",
                str(sample_file),
                "--no-sync",
            ]
        )

        redirected_file = dfpath / sample_file.parent.name / sample_file.name
        bak_file = sample_file.with_suffix(".txt.bak")
        assert redirected_file.exists()
        assert redirected_file.read_text() == "Sample content"
        assert not bak_file.exists()
        assert capsys.readouterr().out.strip().split("\n") == [
            f"Backed up {sample_file} to {bak_file}",
            "Updating manifest with current system's dotfiles...",
            f"Checking dotfile: {sample_file}",
            f"Adding dotfile: {sample_file.name} found in {path_as_posix(sample_file)}",
            "Manifest updated with current system's dotfiles.",
            "Persisting links to the manifest...",
            f"Linked {sample_file.name} to {sample_file} -> {redirected_file}",
            "Links persisted to the manifest.",
            f"Manifest file {dfmanpath.with_suffix(f'.{loaded_manifest.original_format}')} updated.",
            f"Backups created for existing dotfiles: {sample_file} -> {bak_file}",
            f"Deleted backup {bak_file} for {sample_file}",
            "Manifest updated with system dotfiles.",
        ]

    @patch("questionary.confirm")
    def test_from_system_generates_backups(
        self,
        questionary_confirm_mock: MagicMock,
        loaded_manifest: Manifest,
        dfpath: Path,
        dfmanpath: Path,
        randpath: Path,
        capsys: CaptureFixture,
    ):
        questionary_confirm_mock.return_value.ask.return_value = False
        sample_file = randpath / "sample.txt"
        _ = sample_file.write_text("Sample content")

        _ = app(
            [
                "from-system",
                "--manifest-path",
                str(
                    dfmanpath.with_suffix(
                        f".{loaded_manifest.original_format}"
                    )
                ),
                "--dotfiles",
                str(sample_file),
                "--no-sync",
            ]
        )

        redirected_file = dfpath / sample_file.parent.name / sample_file.name
        bak_file = sample_file.with_suffix(".txt.bak")
        assert redirected_file.exists()
        assert redirected_file.read_text() == "Sample content"
        assert bak_file.exists()
        assert bak_file.read_text() == "Sample content"
        assert capsys.readouterr().out.strip().split("\n") == [
            f"Backed up {sample_file} to {bak_file}",
            "Updating manifest with current system's dotfiles...",
            f"Checking dotfile: {sample_file}",
            f"Adding dotfile: {sample_file.name} found in {path_as_posix(sample_file)}",
            "Manifest updated with current system's dotfiles.",
            "Persisting links to the manifest...",
            f"Linked {sample_file.name} to {sample_file} -> {redirected_file}",
            "Links persisted to the manifest.",
            f"Manifest file {dfmanpath.with_suffix(f'.{loaded_manifest.original_format}')} updated.",
            f"Backups created for existing dotfiles: {sample_file} -> {bak_file}",
            "Manifest updated with system dotfiles.",
        ]
