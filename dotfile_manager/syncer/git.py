import shutil
from pathlib import Path
from typing import Self

from escudeiro.data import data
from escudeiro.lazyfields import lazyfield
from escudeiro.misc import timezone
from git import Repo
from termcolor import colored

from dotfile_manager.manifest.concepts import ManifestFormat
from dotfile_manager.manifest.loader import dumpers, loaders, validate_manifest_path
from dotfile_manager.manifest.schema import Manifest
from dotfile_manager.utils import ValidationError


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
    push_after_commit: bool = True
    pinned_hash: str | None = None

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
            push_after_commit=manifest.push_after_commit,
            pinned_hash=manifest.pinned_hash,
            manifest=manifest,
        )

    def _verify_manifest_file(self) -> None:
        """
        Verifies that the manifest file exists in the repository path.
        Raises an error if the manifest file is not found.
        """
        manifest_file = self.repository_path / f"dfman.{self.manifest.original_format}"
        if not manifest_file.exists():
            manifest_file.touch()
            manifest_file.write_text(
                dumpers[self.manifest.original_format](self.manifest)
            )
            print(colored(f"Manifest file {manifest_file} created.", "yellow"))

        print(colored(f"Manifest file {manifest_file} verified.", "green"))

    def save(self) -> None:
        """
        Synchronizes the local repository with the remote repository.
        Commits changes and pushes them if push_after_commit is True.
        """
        self._verify_manifest_file()
        repo = self.instance
        repo.git.add(A=True)
        commit_message = self.commit_message.format(
            timestamp=timezone.now().isoformat(timespec="seconds")
        )
        repo.index.commit(commit_message)

        if self.push_after_commit:
            origin = repo.remote(name="origin")
            origin.push(refspec=f"{self.repository_branch}:{self.repository_branch}")
        if self.pinned_hash:
            raise ValueError("Cannot sync changes with a pinned hash.")
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
        origin.pull(refspec=f"{self.repository_branch}")
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
    def download(
        cls,
        repository_url: str,
        repository_branch: str,
        repository_path: Path,
        manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
        pinned_hash: str | None = None,
    ) -> tuple[Self, Path]:
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
                    repository_path, manifest.root,
                )
            return cls(
                repository_url=repository_url,
                repository_path=repository_path,
                manifest=manifest,
                repository_branch=repository_branch,
                pinned_hash=pinned_hash,
            ), manifest_path
        except Exception as e:
            if repository_path.exists():
                shutil.rmtree(repository_path, ignore_errors=True)
            raise e
