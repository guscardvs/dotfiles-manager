import shutil
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Self

from escudeiro.data import data
from escudeiro.lazyfields import lazyfield
from escudeiro.misc import to_snake
from git import Repo
from termcolor import colored

from dotfile_manager.manifest.concepts import ManifestFormat
from dotfile_manager.manifest.loader import loaders, validate_manifest_path
from dotfile_manager.manifest.schema import Manifest
from dotfile_manager.utils import ValidationError, get_timezone


@data
class GitSyncer:
    """
    A class to handle git synchronization for dotfiles.
    """

    repository_url: str
    repository_path: Path
    manifest: Manifest
    repository_branch: str = "main"
    commit_message: str = "Sync dotfiles {timestamp}"
    pinned_hash: str | None = None

    @staticmethod
    def init_git(path: Path) -> Repo:
        """
        Initializes a git repository at the specified path.
        If the repository already exists, it returns the existing Repo instance.
        """
        if not (path / ".git").exists():
            path.mkdir(parents=True, exist_ok=True)
            return Repo.init(path)
        return Repo(path)

    def __post_init__(self) -> None:
        if not self.repository_url:
            raise ValidationError(
                "Repository URL cannot be empty, fix your configuration."
            )

    @lazyfield
    def instance(self) -> Repo:
        """
        Returns a git Repo instance for the specified repository path.
        If the repository does not exist, it initializes a new one.
        """
        if not (self.repository_path / ".git").exists():
            self.repository_path.mkdir(parents=True, exist_ok=True)
            repo = Repo.init(self.repository_path)
        else:
            repo = Repo(self.repository_path)
            if repo.bare:
                repo = Repo.init(self.repository_path)
        if not repo.remotes:
            repo.create_remote("origin", self.repository_url)
        return repo

    @classmethod
    def from_manifest(cls, manifest: Manifest) -> Self:
        """
        Creates a GitSyncer instance from a Manifest object.
        """
        return cls(
            repository_url=manifest.repository_url,
            repository_path=manifest.root,
            repository_branch=manifest.repository_branch,
            pinned_hash=manifest.pinned_hash,
            manifest=manifest,
        )

    def apply(self, message: str | None) -> None:
        repo = self.instance
        repo.git.add(A=True)
        commit_message = message or self.commit_message.format(
            timestamp=get_timezone().now().isoformat(timespec="seconds")
        )
        repo.index.commit(commit_message)

    def save(self) -> None:
        """
        Synchronizes the local repository with the remote repository.
        Commits changes and pushes them if push_after_commit is True.
        """
        repo = self.instance
        origin = repo.remote(name="origin")
        origin.push(refspec=f"{self.repository_branch}:{self.repository_branch}")
        if self.pinned_hash:
            raise ValidationError("Cannot sync changes with a pinned hash.")
        print(
            colored(
                f"Repository {self.repository_path} synchronized successfully.", "green"
            )
        )

    def pull(self) -> None:
        """
        Pulls the latest changes from the remote repository.
        """
        repo = self.instance
        origin = repo.remote(name="origin")
        origin.pull(refspec=f"{self.repository_branch}", rebase=True)
        print(
            colored(f"Repository {self.repository_path} pulled successfully.", "green")
        )

    def sync(self) -> None:
        """
        Synchronizes the local repository with the remote repository.
        This method combines pull and save operations.
        """
        self.pull()
        self.save()

    def review(self) -> None:
        """
        Reviews the changes in the local repository.
        Prints the status of the repository.
        """
        repo = self.instance
        status = repo.git.status()
        print(colored(f"Repository {self.repository_path} status:\n{status}", "blue"))

        if not repo.is_dirty(untracked_files=True):
            print(colored("No changes to commit.", "green"))
        else:
            print(colored("There are changes to commit.", "yellow"))

    @classmethod
    @contextmanager
    def download(
        cls,
        repository_url: str,
        repository_branch: str,
        repository_path: Path,
        manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
        pinned_hash: str | None = None,
    ) -> Generator[tuple[Self, Path]]:
        """
        Downloads the repository from the specified URL and branch.
        Initializes a GitSyncer instance with the downloaded repository.

        Args:
            repository_url (str): The URL of the remote repository.
            repository_branch (str): The branch to clone.
            manifest_path (Path): The path to the manifest file.
            repository_path (Path): The local path to clone the repository.
            manifest_format (ManifestFormat): The format of the manifest file.
            pinned_hash (str | None): Optional pinned hash for the repository.
        Returns:
            tuple[Self, Path]: A tuple containing the GitSyncer instance and the path to the manifest file.
        """

        repo = Repo.clone_from(
            repository_url,
            repository_path,
            branch=repository_branch,
            depth=1,
        )
        try:
            if pinned_hash:
                repo.git.checkout(pinned_hash)
            if not (repository_path / ".git").exists():
                raise ValidationError(f"Failed to clone repository: {repository_url}")
            manifest_file = None
            for file in repository_path.iterdir():
                if file.is_file() and file.name.split(".")[0] == "dfman":
                    manifest_file = file
                    break
            if manifest_file is None:
                raise ValidationError(
                    f"No manifest file found in the specified repository: {repository_url}"
                    + f" with branch {repository_branch}"
                    + (f" and pinned hash {pinned_hash}" if pinned_hash else "")
                )
            manifest_path, file_format = validate_manifest_path(
                manifest_file, manifest_format
            )
            if file_format != manifest_format:
                if manifest_format is ManifestFormat.PRESUMED:
                    manifest_format = file_format
                else:
                    raise ValidationError(
                        f"Manifest format mismatch: expected {manifest_format}, "
                        f"but found {file_format} in {manifest_path}"
                    )
            manifest = loaders[manifest_format](manifest_path)
            if manifest.root != repository_path:
                shutil.move(
                    repository_path,
                    manifest.root,
                )
            yield (
                cls(
                    repository_url=repository_url,
                    repository_path=repository_path,
                    manifest=manifest,
                    repository_branch=repository_branch,
                    pinned_hash=pinned_hash,
                ),
                manifest_path,
            )
        except Exception as e:
            if repository_path.exists():
                shutil.rmtree(repository_path, ignore_errors=True)
            raise e

    def revert(
        self,
        refspec: str,
        backup_branch: str | None,
    ) -> None:
        """Reverts the repository to a specific commit or branch.
        Args:
            refspec (str): The commit hash or branch name to revert to.
            backup_branch (str | None): Optional name for the backup branch.
                If not provided, a default backup branch name will be used.

        """

        if self.pinned_hash:
            raise ValidationError("Cannot revert changes with a pinned hash.")

        backup_branch = (
            backup_branch
            or f"backup_{to_snake(datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))}"
        )
        repo = self.instance
        if backup_branch not in repo.branches:
            repo.git.checkout("-b", backup_branch)
        else:
            repo.git.checkout(backup_branch)
        origin = repo.remote(name="origin")
        origin.push(
            refspec=f"{backup_branch}:{backup_branch}",
            force=True,
        )
        repo.git.checkout(self.repository_branch)
        commits_to_revert = list(repo.iter_commits(f"{refspec}..HEAD"))
        if not commits_to_revert:
            print(colored("No commits to revert.", "yellow"))
            return
        repo.git.revert(
            *[commit.hexsha for commit in commits_to_revert],
            no_edit=True,
        )

        # save and push changes
        origin = repo.remote(name="origin")
        origin.push(refspec=f"{self.repository_branch}:{self.repository_branch}")
        print(
            colored(
                f"Repository {self.repository_path} reverted to {refspec} (via revert commits) and changes pushed successfully.",
                "green",
            )
        )
        if backup_branch != self.repository_branch:
            print(
                colored(
                    f"Backup branch {backup_branch} created with the state before the revert.",
                    "yellow",
                )
            )

    def log(self, limit: int = 10) -> None:
        """
        Prints the commit log of the repository.

        Args:
            limit (int): The number of commits to show in the log. Defaults to 10.
        """
        repo = self.instance
        log_entries = repo.git.log(
            "--pretty=format:%h - %an, %ar : %s", n=limit
        ).splitlines()
        if not log_entries:
            print(colored("No commits found in the repository.", "yellow"))
            return
        print(colored("Commit Log:", "blue"))
        for entry in log_entries:
            print(colored(entry, "green"))
