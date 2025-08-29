from pathlib import Path

from escudeiro.misc import autopath
from git import Commit
from pytest import CaptureFixture

from dotfile_manager.app import app
from dotfile_manager.manifest.concepts import ManifestFormat
from dotfile_manager.manifest.schema import Manifest
from dotfile_manager.syncer.git import GitSyncer
import pytest


class TestLog:
    @pytest.fixture
    def commit_instance(self, loaded_manifest: Manifest, dfmanpath: Path):
        syncer = GitSyncer.from_manifest(loaded_manifest)
        root = autopath(loaded_manifest.root)
        _ = (root / "test1.txt").write_text("Test 1")
        commit_message = "Add test1.txt"
        repo = syncer.instance
        repo.git.add(A=True)
        commit = repo.index.commit(commit_message)
        return commit

    def test_log_success(
        self,
        loaded_manifest: Manifest,
        dfmanpath: Path,
        commit_instance: Commit,
        capsys: CaptureFixture,
    ):
        syncer = GitSyncer.from_manifest(loaded_manifest)
        repo = syncer.instance

        _ = app(
            [
                "log",
                "--manifest-path",
                str(
                    dfmanpath.with_suffix(
                        f".{loaded_manifest.original_format}"
                    )
                ),
            ]
        )

        stdout = capsys.readouterr().out
        assert "Commit Log:" in stdout
        assert commit_instance.message in stdout
        assert repo.git.rev_parse(commit_instance.hexsha, short=7) in stdout

    def test_log_success_nopretty(
        self,
        loaded_manifest: Manifest,
        dfmanpath: Path,
        commit_instance: Commit,
        capsys: CaptureFixture,
    ):
        syncer = GitSyncer.from_manifest(loaded_manifest)
        repo = syncer.instance

        _ = app(
            [
                "log",
                "--manifest-path",
                str(
                    dfmanpath.with_suffix(
                        f".{loaded_manifest.original_format}"
                    )
                ),
                "--no-pretty",
            ]
        )

        stdout = capsys.readouterr().out
        assert "Commit Log:" in stdout
        assert commit_instance.message in stdout
        assert repo.git.rev_parse(commit_instance.hexsha) in stdout
        assert commit_instance.author.name in stdout
        assert commit_instance.author.email in stdout

    def test_log_fails_correctly_for_empty_repo(
        self,
        loaded_manifest: Manifest,
        dfmanpath: Path,
        capsys: CaptureFixture,
    ):
        _ = app(
            [
                "log",
                "--manifest-path",
                str(
                    dfmanpath.with_suffix(
                        f".{loaded_manifest.original_format}"
                    )
                ),
            ]
        )

        stdout = capsys.readouterr().out
        assert "Commit Log:" in stdout
        assert "No commits found." in stdout

    def test_log_fails_for_uninitialized_manifest_path(
        self, dfmanpath: Path, capsys: CaptureFixture
    ):
        with pytest.raises(SystemExit) as excinfo:
            _ = app(
                [
                    "log",
                    "--manifest-path",
                    str(dfmanpath.with_suffix(f".{ManifestFormat.TOML}")),
                ]
            )
        assert excinfo.value.code == 1

        stdout = capsys.readouterr().out
        assert (
            stdout
            == f"Manifest file does not exist: '{dfmanpath.with_suffix(f'.{ManifestFormat.TOML}')}'\n"
        )
