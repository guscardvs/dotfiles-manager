from pathlib import Path
from unittest.mock import MagicMock, patch

from pytest import CaptureFixture

from dotfile_manager.app import app
from dotfile_manager.linker.default import DefaultLinker
from dotfile_manager.manifest.schema import Manifest, path_as_posix
from dotfile_manager.utils import ValidationError


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

    @patch("questionary.confirm")
    def test_from_system_restores_backups_if_any_error_happens(
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
        original_restore = DefaultLinker.restore_backups
        call_count = 0

        def _restore_backups(
            self: DefaultLinker, backups: list[tuple[Path, Path]]
        ):
            nonlocal call_count
            call_count += 1
            return original_restore(self, backups)

        with (
            patch("dotfile_manager.app.persist_changes") as mock_persist,
            patch(
                "dotfile_manager.app.PureLinker.restore_backups",
                new=_restore_backups,
            ),
        ):
            mock_persist.side_effect = Exception("Simulated error")
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
        assert call_count == 1
        assert redirected_file.exists()
        assert redirected_file.read_text() == "Sample content"
        assert not bak_file.exists()
        assert sample_file.exists()
        assert sample_file.read_text() == "Sample content"
        assert not (redirected_file.is_symlink() or sample_file.is_symlink())
        assert capsys.readouterr().out.strip().split("\n") == [
            f"Backed up {sample_file} to {bak_file}",
            "Updating manifest with current system's dotfiles...",
            f"Checking dotfile: {sample_file}",
            f"Adding dotfile: {sample_file.name} found in {path_as_posix(sample_file)}",
            "Manifest updated with current system's dotfiles.",
            "Persisting links to the manifest...",
            f"Linked {sample_file.name} to {sample_file} -> {redirected_file}",
            "Links persisted to the manifest.",
            f"Unexpected error: {mock_persist.side_effect}",
            f"Error while updating manifest: {mock_persist.side_effect}",
            "Restoring backups...",
            f"Original file {sample_file} exists. Overwriting it.",
            f"Restored {sample_file} from {bak_file}",
        ]

    @patch("questionary.confirm")
    def test_from_system_restores_correctly_from_validation(
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
        original_restore = DefaultLinker.restore_backups
        call_count = 0

        def _restore_backups(
            self: DefaultLinker, backups: list[tuple[Path, Path]]
        ):
            nonlocal call_count
            call_count += 1
            return original_restore(self, backups)

        with (
            patch("dotfile_manager.app.persist_changes") as mock_persist,
            patch(
                "dotfile_manager.app.PureLinker.restore_backups",
                new=_restore_backups,
            ),
        ):
            mock_persist.side_effect = ValidationError("Simulated error")
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
        assert call_count == 1
        assert redirected_file.exists()
        assert redirected_file.read_text() == "Sample content"
        assert not bak_file.exists()
        assert sample_file.exists()
        assert sample_file.read_text() == "Sample content"
        assert not (redirected_file.is_symlink() or sample_file.is_symlink())
        assert capsys.readouterr().out.strip().split("\n") == [
            f"Backed up {sample_file} to {bak_file}",
            "Updating manifest with current system's dotfiles...",
            f"Checking dotfile: {sample_file}",
            f"Adding dotfile: {sample_file.name} found in {path_as_posix(sample_file)}",
            "Manifest updated with current system's dotfiles.",
            "Persisting links to the manifest...",
            f"Linked {sample_file.name} to {sample_file} -> {redirected_file}",
            "Links persisted to the manifest.",
            f"Error while updating manifest: {mock_persist.side_effect}",
            "Restoring backups...",
            f"Original file {sample_file} exists. Overwriting it.",
            f"Restored {sample_file} from {bak_file}",
        ]
