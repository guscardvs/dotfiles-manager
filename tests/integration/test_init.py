from pathlib import Path

import pytest
from git import Repo

from dotfile_manager.app import app
from dotfile_manager.manifest.concepts import ManifestFormat
from dotfile_manager.manifest.loader import loaders
from dotfile_manager.manifest.schema import Manifest
from dotfile_manager.utils import PartialEntry


class TestInit:
    @pytest.fixture
    def dfpath(self, tmp_path: Path) -> Path:
        return tmp_path / ".dotfiles"

    @pytest.fixture
    def dfmanpath(self, tmp_path: Path) -> Path:
        return tmp_path / ".dfman"

    @pytest.mark.parametrize("manifest_format", ManifestFormat.valid())
    def test_init_success(
        self, manifest_format: ManifestFormat, dfpath: Path, dfmanpath: Path
    ):
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

        dfman_real_path = dfmanpath.with_suffix(f".{manifest_format}")

        assert not Repo(dfpath).bare
        assert dfman_real_path.exists()
        assert loaders[manifest_format](dfman_real_path) == Manifest(
            root=dfpath,
            repository_url="https://example.com/repo.git",
            original_format=manifest_format,
            extra_paths=[],
            default_terminal="zsh",
            default_editor="nano",
            default_shell=PartialEntry(
                "bash",
                map(
                    Path,
                    ("/usr/bin", "/bin", "/usr/local/bin", "~/.local/bin"),
                ),
            ),
            repository_branch="develop",
            dotfiles=[],
            pinned_hash="",
        )

    def test_init_already_initialized(self, dfpath: Path, dfmanpath: Path):
        _ = app(
            [
                "init",
                "--manifest-path",
                str(dfmanpath),
                "--repository-path",
                str(dfpath),
                "--repository-url",
                "https://example.com/repo.git",
            ]
        )

        with pytest.raises(SystemExit) as excinfo:
            _ = app(
                [
                    "init",
                    "--manifest-path",
                    str(dfmanpath),
                    "--repository-path",
                    str(dfpath),
                ]
            )
        assert excinfo.value.code == 1

    def test_init_works_for_already_existent_directory_with_no_children(
        self, dfpath: Path, dfmanpath: Path
    ):
        dfpath.mkdir(parents=True, exist_ok=True)

        _ = app(
            [
                "init",
                "--manifest-path",
                str(dfmanpath),
                "--repository-path",
                str(dfpath),
                "--repository-url",
                "https://example.com/repo.git",
            ]
        )

        gitdir = dfpath / ".git"
        dfman_real_path = dfmanpath.with_suffix(f".{ManifestFormat.TOML}")

        assert not Repo(gitdir).bare
        assert dfman_real_path.exists()

    def test_init_only_fails_if_source_file_already_exists(
        self, dfpath: Path, dfmanpath: Path
    ):
        dfpath.mkdir(parents=True, exist_ok=True)
        dfman_real_path = dfmanpath.with_suffix(f".{ManifestFormat.TOML}")
        (dfpath / dfman_real_path.name).touch()

        with pytest.raises(SystemExit) as excinfo:
            _ = app(
                [
                    "init",
                    "--manifest-path",
                    str(dfmanpath),
                    "--repository-path",
                    str(dfpath),
                    "--repository-url",
                    "https://example.com/repo.git",
                ]
            )
        assert excinfo.value.code == 1

    def test_init_fails_for_already_existent_manifest(
        self, dfpath: Path, dfmanpath: Path
    ):
        dfmanpath.with_suffix(f".{ManifestFormat.TOML}").parent.mkdir(
            parents=True, exist_ok=True
        )
        dfmanpath.with_suffix(f".{ManifestFormat.TOML}").touch()

        with pytest.raises(SystemExit) as excinfo:
            _ = app(
                [
                    "init",
                    "--manifest-path",
                    str(dfmanpath),
                    "--repository-path",
                    str(dfpath),
                    "--manifest-format",
                    ManifestFormat.TOML,
                    "--repository-url",
                    "https://example.com/repo.git",
                ]
            )
        assert excinfo.value.code == 1

    def test_manifest_path_and_source_path_are_identical(
        self, dfpath: Path, dfmanpath: Path
    ):
        manpath = dfmanpath.with_suffix(f".{ManifestFormat.TOML}")
        sourcepath = dfpath / manpath.name

        _ = app(
            [
                "init",
                "--manifest-path",
                str(manpath),
                "--repository-path",
                str(dfpath),
                "--repository-url",
                "https://example.com/repo.git",
            ]
        )

        assert manpath.exists() and sourcepath.exists()
        assert (
            manpath.is_symlink() and manpath.resolve() == sourcepath.resolve()
        )

    def test_git_is_initialized_properly(self, dfpath: Path, dfmanpath: Path):
        _ = app(
            [
                "init",
                "--manifest-path",
                str(dfmanpath),
                "--repository-path",
                str(dfpath),
                "--repository-branch",
                "develop",
                "--repository-url",
                "https://example.com/repo.git",
            ]
        )
        repo = Repo(dfpath)
        assert not repo.bare
        assert repo.active_branch.name == "develop"
        assert repo.remotes.origin.url == "https://example.com/repo.git"

    def test_pinned_hash_works_for_existent_hash(
        self, dfpath: Path, dfmanpath: Path
    ):
        repo = Repo.init(dfpath, initial_branch="develop")
        hashes = []
        for idx in range(3):
            _ = (dfpath / f"test{idx}.txt").write_text(f"Test {idx}")
            repo.git.add(A=True)
            commit = repo.index.commit(f"Saving file test{idx}.txt")
            hashes.append(commit.hexsha)

        _ = app(
            [
                "init",
                "--manifest-path",
                str(dfmanpath),
                "--repository-path",
                str(dfpath),
                "--repository-url",
                "https://example.com/repo.git",
                "--pinned-hash",
                hashes[0],
            ]
        )

        assert repo.head.commit.hexsha == hashes[0]
        assert not (dfpath / "test2.txt").exists()
        assert not (dfpath / "test3.txt").exists()

    def test_pinned_hash_does_not_checkout_if_hash_already_correct(
        self, dfpath: Path, dfmanpath: Path
    ):
        repo = Repo.init(dfpath, initial_branch="develop")
        hashes = []
        for idx in range(3):
            _ = (dfpath / f"test{idx}.txt").write_text(f"Test {idx}")
            repo.git.add(A=True)
            commit = repo.index.commit(f"Saving file test{idx}.txt")
            hashes.append(commit.hexsha)

        _ = app(
            [
                "init",
                "--manifest-path",
                str(dfmanpath),
                "--repository-path",
                str(dfpath),
                "--repository-url",
                "https://example.com/repo.git",
                "--pinned-hash",
                hashes[-1],
            ]
        )

        assert repo.head.commit.hexsha == hashes[-1]
        assert not repo.head.is_detached

    def test_pinned_hash_fails_if_hash_does_not_exist(
        self, dfpath: Path, dfmanpath: Path
    ):
        with pytest.raises(SystemExit) as excinfo:
            _ = app(
                [
                    "init",
                    "--manifest-path",
                    str(dfmanpath),
                    "--repository-path",
                    str(dfpath),
                    "--repository-url",
                    "https://example.com/repo.git",
                    "--pinned-hash",
                    "wrong-hash",
                ]
            )

        assert excinfo.value.code == 1
