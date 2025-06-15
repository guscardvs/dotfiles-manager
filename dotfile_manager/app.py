import shutil
from collections.abc import Sequence
from pathlib import Path

from cyclopts import App
from termcolor import colored

from dotfile_manager.linker.pure import USUAL_DOTFILES, PureLinker
from dotfile_manager.manifest.concepts import ManifestFormat
from dotfile_manager.manifest.loader import (
    loaders,
    print_manifest,
    validate_manifest_path,
)
from dotfile_manager.syncer.git import GitSyncer
from dotfile_manager.utils import ValidationError, configdir, handle_error, load_path

app = App(
    name="Dofile Manager",
)


@app.command
@handle_error
def check_settings(
    manifest_path: Path = configdir() / "dfman.toml",
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
):
    """
    Test the manifest file by loading it and printing it as JSON.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    Returns:
        str: The manifest file content as JSON.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    print_manifest(manifest)


@app.command
@handle_error
def sync(
    manifest_path: Path = configdir() / "dfman.toml",
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    pull: bool = True,
    save: bool = True,
):
    """
    Synchronize the dotfiles with the remote repository.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)

    syncer = GitSyncer.from_manifest(manifest)
    if pull:
        syncer.pull()
    if save:
        syncer.save()
    if not pull and not save:
        print(
            colored(
                "No action specified. Use --pull to pull changes or --save to save changes.",
                "yellow",
            )
        )

@app.command
@handle_error
def review(
    manifest_path: Path = configdir() / "dfman.toml",
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
):
    """
    Review the changes in the dotfiles repository.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)

    syncer = GitSyncer.from_manifest(manifest)
    syncer.review()

@app.command
@handle_error
def link(
    manifest_path: Path = configdir() / "dfman.toml",
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
):
    """
    Create symbolic links for the dotfiles specified in the manifest.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    linker = PureLinker(manifest=manifest)
    linker.link_all()

@app.command
@handle_error
def from_system(
    manifest_path: Path = configdir() / "dfman.toml",
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    dotfiles: Sequence[str | Path] = USUAL_DOTFILES,
    sync: bool = True,
):
    """
    Synchronize the manifest with the current system's dotfiles.
    This command will update a manifest file based on the current system's dotfiles.

    Args:
        manifest_path (Path): The path to save the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    dotfiles = [load_path(df, Path.home()) for df in dotfiles]
    linker = PureLinker(manifest=manifest)
    linker.save_from_system(dotfiles)
    if sync:
        syncer = GitSyncer.from_manifest(manifest)
        syncer.save()


@app.command
@handle_error
def download(
    repository_url: str,
    branch: str = "main",
    manifest_path: Path = configdir() / "dfman",
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    repository_path: Path = Path.home() / ".dotfiles",
    pinned_hash: str | None = None,
):
    """
    Download the dotfiles specified in the manifest.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    """
    
    syncer, manifest_file = GitSyncer.download(
        repository_url=repository_url,
        repository_branch=branch,
        manifest_format=manifest_format,
        repository_path=repository_path,
        pinned_hash=pinned_hash,
    )
    manifest = syncer.manifest
    if not manifest_path.exists():
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
    elif not manifest_path.is_dir():
        shutil.rmtree(manifest_path)
        raise ValidationError(f"{manifest_path} is not a directory.")
    manifest_path = manifest_path.with_suffix(f".{manifest.original_format.value}")
    manifest_path.symlink_to(manifest_file, target_is_directory=False)
    
    print_manifest(manifest)