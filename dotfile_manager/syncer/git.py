import shutil
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Self

from escudeiro.data import data
from escudeiro.lazyfields import lazyfield
from escudeiro.misc import next_or, to_snake
from git import GitCommandError, Repo
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
        _ = repo.index.commit(commit_message)

    def save(self) -> None:
        """
        Synchronizes the local repository with the remote repository.
        Commits changes and pushes them if push_after_commit is True.
        """
        repo = self.instance
        origin = repo.remote(name="origin")
        _ = origin.push(refspec=f"{self.repository_branch}:{self.repository_branch}")
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
        _ = origin.pull(refspec=f"{self.repository_branch}", rebase=True)
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
                        + f"but found {file_format} in {manifest_path}"
                    )
            manifest = loaders[manifest_format](manifest_path)
            if manifest.root != repository_path:
                _ = shutil.move(
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
        repo = self.instance
        if repo.is_dirty(untracked_files=True):
            raise ValidationError(
                "Cannot revert changes while the repository has uncommitted changes."
            )

        if repo.head.object.hexsha == refspec:
            print(colored("Already at the specified commit or branch.", "yellow"))
            return

        commit_info = next_or(
            (commit, distance)
            for distance, commit in enumerate(repo.iter_commits())
            if commit.hexsha == refspec
        )
        if not commit_info:
            raise ValidationError(
                f"Commit or branch '{refspec}' not found in the repository."
            )

        if not backup_branch:
            backup_branch = f"backup-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if backup_branch in repo.branches:
            raise ValidationError(
                f"Backup branch '{backup_branch}' already exists. Please choose a different name."
            )
        repo.git.checkout("-b", backup_branch)
        remote = repo.remote(name="origin")
        if remote.exists():
            _ = remote.push(refspec=f"{backup_branch}:{backup_branch}")
        repo.git.checkout(self.repository_branch)
        self._insist_revert(refspec)

        if repo.is_dirty(untracked_files=True):
            print(colored("Repository has uncommitted changes after revert.", "yellow"))
            repo.git.add(A=True)
            repo.git.commit(m=f"Reverted to {refspec}")
        _ = remote.push(refspec=f"{self.repository_branch}:{self.repository_branch}")
        print(
            colored(
                f"Repository reverted to {refspec} and backup created at {backup_branch}.",
                "green",
            )
        )

    def _insist_revert(self, refspec: str) -> None:
        """
        Insists on reverting to a specific commit or branch.
        This method checks if the repository is clean and then performs the revert.
        """
        repo = self.instance
        while True:
            try:
                repo.git.revert(
                    refspec, no_edit=True, no_commit=True, strategy="theirs"
                )
                break
            except GitCommandError as e:
                if "nothing to revert" in str(e):
                    print(colored("No changes to revert.", "yellow"))
                    return
                elif "conflict" in str(e):
                    print(colored("Merge conflict detected. Insisting.", "red"))
                    unmerged = [
                        item
                        for item in repo.index.diff("HEAD")
                        if item.change_type == "U"
                    ]
                    for item in unmerged:
                        print(colored(f"Unmerged file: {item.a_path}", "red"))
                        print(
                            colored(
                                "Attempting to resolve conflicts automatically.",
                                "yellow",
                            )
                        )
                        repo.git.checkout(item.b_path, theirs=True)
                        repo.git.add(A=True)
                    print(colored("Conflicts resolved. Committing changes.", "green"))
                    _ = repo.index.commit(f"Resolved conflicts for revert to {refspec}")
                    return
                else:
                    print(colored(f"Error during revert: {e}", "red"))
                    raise e

    def log(self, limit: int = 10, pretty: bool = True) -> None:
        """
        Prints the commit log of the repository.

        Args:
            limit (int): The number of commits to show in the log. Defaults to 10.
        """
        repo = self.instance
        if pretty:
            log_entries = repo.git.log(
                "--pretty=format:%h - %an, %ar : %s", n=limit
            ).splitlines()
        else:
            log_entries = repo.git.log(n=limit).splitlines()
        if not log_entries:
            print(colored("No commits found in the repository.", "yellow"))
            return
        print(colored("Commit Log:", "blue"))
        for entry in log_entries:
            print(colored(entry, "green"))

    def is_dirty(self) -> bool:
        """
        Checks if the repository has uncommitted changes.

        Returns:
            bool: True if the repository is dirty, False otherwise.
        """
        return self.instance.is_dirty(untracked_files=True)
