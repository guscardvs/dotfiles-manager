import shutil
import subprocess
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import questionary
from cyclopts import App, Parameter
from escudeiro.misc import next_or
from termcolor import colored

from dotfile_manager.linker.pure import USUAL_DOTFILES, PureLinker
from dotfile_manager.manifest.concepts import ManifestFormat
from dotfile_manager.manifest.diffs import persist_changes
from dotfile_manager.manifest.loader import (
    dumpers,
    loaders,
    print_dotfiles,
    print_manifest,
    resolve_dfman_path,
    validate_manifest_path,
)
from dotfile_manager.manifest.schema import Dotfile, Manifest
from dotfile_manager.syncer.git import GitSyncer
from dotfile_manager.utils import (
    PartialEntry,
    ValidationError,
    configdir,
    get_timezone,
    handle_error,
    load_path,
)

app = App(
    name="Dotfile Manager",
)

CONFIG_DIR = configdir() / "dfman"


@app.command
@handle_error
def check(
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
):
    """
    Check the settings of the dotfile manager.
    This command will load the manifest file and print its contents.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    print_manifest(manifest)


@app.command
@handle_error
def sync(
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    message: Annotated[str | None, Parameter(alias="m")] = None,
    pull: bool = True,
    save: bool = True,
):
    """
    Synchronize the dotfiles with the remote repository.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        message (str | None): The commit message to use when saving changes.
        pull (bool): Whether to pull changes from the remote repository.
        save (bool): Whether to save changes to the remote repository.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)

    syncer = GitSyncer.from_manifest(manifest)
    if pull:
        syncer.pull()
    if save:
        syncer.apply(message)
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
    manifest_path: Path = CONFIG_DIR,
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
    dotfiles: Sequence[str | Path] = (),
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
):
    """
    Create symbolic links for the dotfiles specified in the manifest.

    Args:
        dotfiles (Sequence[str | Path]): A sequence of dotfiles to link. If empty, all dotfiles in the manifest will be linked.
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    linker = PureLinker(manifest=manifest)
    if not dotfiles:
        print(
            colored(
                "No dotfiles specified. Linking all dotfiles in the manifest.", "yellow"
            )
        )
        linker.link_all()
        print(colored("All dotfiles linked successfully.", "green"))
        return
    dfs: list[Dotfile] = []
    for df in dotfiles:
        if isinstance(df, str):
            df = Path(df)
        if df.is_absolute():
            rel_df = df.relative_to(Path.home())
        else:
            rel_df = df
        instance = next_or(
            selected
            for selected in manifest.dotfiles
            if selected.name == df
            or selected.location in map(Path.as_posix, [rel_df, df])
        )
        if instance is None:
            print(
                colored(
                    f"Dotfile {df} not found in the manifest. Skipping.",
                    "yellow",
                )
            )
        else:
            dfs.append(instance)
    if not dfs:
        print(colored("No dotfiles to link.", "yellow"))
        return
    for dotfile in dfs:
        try:
            linker.link(dotfile)
        except ValidationError as e:
            print(colored(f"Error linking {dotfile.name}: {e.message}", "red"))
        else:
            print(colored(f"Linked dotfile: {dotfile.name}", "green"))

    print(colored("All dotfiles linked successfully.", "green"))


@app.command
@handle_error
def from_system(
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    dotfiles: Sequence[str | Path] = USUAL_DOTFILES,
    sync: bool = True,
    message: Annotated[str | None, Parameter(alias="m")] = None,
):
    """
    Create managed dotfiles from the system's dotfiles.
    This command will create symbolic links for the specified dotfiles in the manifest.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        dotfiles (Sequence[str | Path]): A sequence of dotfiles to create.
        sync (bool): Whether to sync the manifest after creating dotfiles.
        message (str | None): The commit message to use when saving changes.
    """
    if dotfiles is USUAL_DOTFILES:
        print(
            colored(
                "No dotfiles specified. Using default dotfiles: "
                + ", ".join(map(str, USUAL_DOTFILES)),
                "yellow",
            )
        )
        if not questionary.confirm(
            "Do you want to use the default dotfiles? (y/n)",
            default=True,
        ).ask():
            return
        dotfiles = questionary.checkbox(
            "Select dotfiles to include in the manifest:",
            choices=[questionary.Choice(df, checked=True) for df in USUAL_DOTFILES],
        ).ask()
        if not dotfiles:
            print(colored("No dotfiles selected. Exiting.", "yellow"))
            return

    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    dotfiles = [load_path(df, Path.home()) for df in dotfiles]
    linker = PureLinker(manifest=manifest)
    backups: list[tuple[Path, Path]] = linker.make_backups(dotfiles)
    try:
        linker.save_from_system(dotfiles)
        linker.persist_links()
        persist_changes(manifest, manifest_path)
        if sync:
            syncer = GitSyncer.from_manifest(manifest)
            syncer.apply(message)
            syncer.save()
    except Exception as e:
        if not isinstance(e, ValidationError):
            print(colored(f"Unexpected error: {e}", "red"))
            traceback.print_exc()
        print(colored(f"Error while updating manifest: {e}", "red"))
        if backups:
            print(colored("Restoring backups...", "yellow"))
            linker.restore_backups(backups)
        return
    else:
        if backups:
            print(
                colored(
                    "Backups created for existing dotfiles: "
                    + ", ".join(f"{src} -> {dst}" for src, dst in backups),
                    "yellow",
                )
            )
            if questionary.confirm(
                "Do you want to delete the backups? (y/n)",
                default=True,
            ).ask():
                linker.delete_backups(backups)
    print(colored("Manifest updated with system dotfiles.", "green"))


@app.command
@handle_error
def download(
    repository_url: str,
    branch: str = "main",
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    repository_path: Path = Path.home() / ".dotfiles",
    pinned_hash: str | None = None,
    force: bool = False,
):
    """
    Download the managed dotfiles from a remote repository and create a symlink to the manifest file.

    Args:
        repository_url (str): The URL of the remote repository.
        branch (str): The branch to clone from.
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        repository_path (Path): The local path to clone the repository.
        pinned_hash (str | None): Optional pinned hash for the repository.
        force (bool): Whether to overwrite the existing manifest symlink if it exists.
    """

    with GitSyncer.download(
        repository_url=repository_url,
        repository_branch=branch,
        manifest_format=manifest_format,
        repository_path=repository_path,
        pinned_hash=pinned_hash,
    ) as (syncer, manifest_file):
        manifest = syncer.manifest
        if not manifest_path.exists():
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
        elif not manifest_path.is_dir():
            shutil.rmtree(manifest_path)
            raise ValidationError(f"{manifest_path} is not a directory.")
        manifest_path = manifest_path.with_suffix(f".{manifest.original_format.value}")
        if manifest_path.exists() and force:
            manifest_path.unlink()
        elif manifest_path.exists():
            raise ValidationError(
                f"{manifest_path} already exists. Use --force to overwrite it."
            )

        manifest_path.symlink_to(manifest_file, target_is_directory=False)


@app.command
@handle_error
def edit_file(
    file_path: str | Path,
    target_path: str | Path | None = None,
    editor: str | None = None,
    description: str | None = None,
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    sync: bool = True,
    message: Annotated[str | None, Parameter(alias="m")] = None,
):
    """
    Edit a file using the specified editor and create a symlink to it.

    Args:
        file_path (str | Path): The path to the file to edit.
        target_path (str | Path | None): The path where the symlink should be created.
        editor (str | None): The editor to use for editing the file.
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        sync (bool): Whether to sync the manifest after editing the file.
        message (str | None): The commit message to use when saving changes.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    if not any((editor, manifest.default_editor)):
        raise ValidationError(
            "No default editor specified. Please provide a default editor."
        )
    elif not editor:
        editor = manifest.default_editor

    if isinstance(file_path, str):
        file_path = Path(file_path)
    if isinstance(target_path, str):
        target_path = Path(target_path)
        if not target_path.is_absolute():
            target_path = Path.home() / target_path

    if file_path.is_absolute():
        if file_path.is_relative_to(Path.home()):
            target_path = target_path or file_path
            file_path = manifest.root / file_path.relative_to(Path.home())
        elif file_path.is_relative_to(manifest.root):
            target_path = target_path or Path.home() / file_path.relative_to(
                manifest.root
            )
            file_path = manifest.root / file_path.relative_to(manifest.root)
        else:
            raise ValidationError(
                "Dotfile manager only supports files inside the home or manifest root directories."
            )
    else:
        target_path = target_path or Path.home() / file_path
        file_path = manifest.root / file_path

    if file_path.exists():
        if not file_path.is_file():
            raise ValidationError(f"{file_path} is not a file.")
        if not target_path.is_symlink() or target_path.resolve() != file_path.resolve():
            raise ValidationError(
                f"Another file or symlink already exists at {target_path}. "
            )
    else:
        if target_path.exists():
            raise ValidationError(
                f"Target path {target_path} already exists. Please choose a different file name."
            )
        file_path.parent.mkdir(parents=True, exist_ok=True)

    # spawn the editor
    if shutil.which(editor) is None:
        raise ValidationError(f"Editor {editor} not found in PATH.")

    editor_cmd = [editor, str(file_path)]
    print(colored(f"Opening {file_path} in {editor}...", "green"))
    try:
        _ = subprocess.run(editor_cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise ValidationError(f"Failed to open editor: {e}")
    except FileNotFoundError:
        raise ValidationError(
            f"Editor {editor} not found. Please install it or specify a different editor."
        )
    except Exception as e:
        raise ValidationError(f"An unexpected error occurred: {e}")
    print(colored(f"File {file_path} edited successfully.", "green"))

    if not file_path.exists():
        print(
            colored(
                f"File {file_path} does not exist after editing, ending...", "yellow"
            )
        )
        return

    if target_path.exists():
        return
    target_path.symlink_to(file_path, target_is_directory=False)
    print(
        colored(f"Created symlink at {target_path} pointing to {file_path}.", "green")
    )
    created_at = get_timezone().today().isoformat()
    dotfile = Dotfile(
        name=file_path.name,
        location=Path.as_posix(
            target_path.relative_to(Path.home())
            if target_path.is_absolute()
            else target_path
        ),
        dflocation=Path.as_posix(
            file_path.relative_to(manifest.root)
            if file_path.is_absolute()
            else file_path
        ),
        description=description
        if description is not None
        else f"Edited file {file_path.name} with {editor} at {created_at}.",
    )
    manifest.dotfiles.append(dotfile)
    if sync:
        syncer = GitSyncer.from_manifest(manifest)
        message = (
            message
            or questionary.text(
                "Enter a commit message for the changes made to the manifest:",
                default=f"Added dotfile {dotfile.name} at {created_at}",
            ).ask()
        )
        syncer.apply(message)
        syncer.save()


@app.command
@handle_error
def edit_manifest(
    editor: str | None = None,
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    sync: bool = True,
    message: Annotated[str | None, Parameter(alias="m")] = None,
):
    """
    Edit the manifest file using the specified editor.

    Args:
        editor (str | None): The editor to use for editing the manifest file.
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        sync (bool): Whether to sync the manifest after editing.
        message (str | None): The commit message to use when saving changes.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)

    if sync:
        syncer = GitSyncer.from_manifest(manifest)
        syncer.pull()

    if not any((editor, manifest.default_editor)):
        raise ValidationError(
            "No default editor specified. Please provide a default editor."
        )
    elif not editor:
        editor = manifest.default_editor
    if shutil.which(editor) is None:
        raise ValidationError(f"Editor {editor} not found in PATH.")
    editor_cmd = [editor, str(manifest_path)]
    print(colored(f"Opening {manifest_path} in {editor}...", "green"))
    try:
        _ = subprocess.run(editor_cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise ValidationError(f"Failed to open editor: {e}")
    except FileNotFoundError:
        raise ValidationError(
            f"Editor {editor} not found. Please install it or specify a different editor."
        )
    except Exception as e:
        raise ValidationError(f"An unexpected error occurred: {e}")
    print(colored(f"Manifest {manifest_path} edited successfully.", "green"))
    new_manifest = loaders[manifest_format](manifest_path)
    if sync:
        syncer = GitSyncer.from_manifest(new_manifest)
        message = (
            message
            or questionary.text(
                "Enter a commit message for the changes made to the manifest:",
                default="Edited manifest file.",
            ).ask()
        )
        syncer.apply(message)
        syncer.save()


@app.command
@handle_error
def unlink(
    dotfiles: Sequence[str | Path] = (),
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
):
    """
    Remove symbolic links for the specified dotfiles in the manifest.

    Args:
        dotfiles (Sequence[str | Path]): A sequence of dotfiles to unlink. If empty, all dotfiles in the manifest will be unlinked.
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    linker = PureLinker(manifest=manifest)
    if not dotfiles:
        linker.unlink_all()
    else:
        dfs: list[Dotfile] = []
        for df in dotfiles:
            if isinstance(df, str):
                df = Path(df)
            if df.is_absolute():
                rel_df = df.relative_to(Path.home())
            else:
                rel_df = df
            df = next_or(
                selected
                for selected in manifest.dotfiles
                if selected.name == df
                or selected.location in map(Path.as_posix, [rel_df, df])
            )
            if df is None:
                print(
                    colored(
                        f"Dotfile {df} not found in the manifest. Skipping.",
                        "yellow",
                    )
                )
            else:
                dfs.append(df)
        if not dfs:
            print(colored("No dotfiles to unlink.", "yellow"))
            return
        for dotfile in dfs:
            try:
                linker.unlink(dotfile)
            except ValidationError as e:
                print(colored(f"Error unlinking {dotfile.name}: {e.message}", "red"))
            else:
                print(colored(f"Unlinked dotfile: {dotfile.name}", "green"))
    print(colored("All dotfiles unlinked successfully.", "green"))


@app.command
@handle_error
def remove(
    dotfiles: Sequence[str | Path],
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    sync: bool = True,
    message: Annotated[str | None, Parameter(alias="m")] = None,
):
    """
    Remove dotfiles from the manifest and unlink them.
    Does NOT support removing dotfiles that are not in the manifest.

    Args:
        dotfiles (Sequence[str | Path]): A sequence of dotfiles to remove. If empty, no dotfiles will be removed.
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        sync (bool): Whether to sync the manifest after removing dotfiles.
        message (str | None): The commit message to use when saving changes.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    linker = PureLinker(manifest=manifest)

    dfs: list[Dotfile] = []
    for df in dotfiles:
        if isinstance(df, str):
            df = Path(df)
        if df.is_absolute():
            rel_df = df.relative_to(Path.home())
        else:
            rel_df = df
        instance = next_or(
            selected
            for selected in manifest.dotfiles
            if selected.name == df
            or selected.location in map(Path.as_posix, [rel_df, df])
        )
        if instance is None:
            print(
                colored(
                    f"Dotfile {df} not found in the manifest. Skipping.",
                    "yellow",
                )
            )
        else:
            dfs.append(instance)

    if not dfs:
        print(colored("No dotfiles to remove.", "yellow"))
        return

    for dotfile in dfs:
        try:
            linker.unlink(dotfile)
            manifest.dotfiles.remove(dotfile)
            if dotfile.dflocation:
                dflocation = manifest.root / dotfile.dflocation
                if dflocation.exists():
                    dflocation.unlink()
                    print(colored(f"Removed dotfile location: {dflocation}", "green"))
            else:
                print(
                    colored(
                        f"Dotfile {dotfile.name} has no dflocation. Skipping unlink.",
                        "yellow",
                    )
                )
            print(colored(f"Removed dotfile: {dotfile.name}", "green"))
        except ValidationError as e:
            print(colored(f"Error removing {dotfile.name}: {e.message}", "red"))

    # Save the updated manifest
    with open(manifest_path, "w") as f:
        _ = f.write(dumpers[manifest_format](manifest))

    print(colored("Dotfiles removed and manifest updated successfully.", "green"))
    persist_changes(manifest, manifest_path)
    if sync:
        syncer = GitSyncer.from_manifest(manifest)
        message = (
            message
            or questionary.text(
                "Enter a commit message for the changes made to the manifest:",
                default=f"Removed dotfiles: {', '.join(df.name for df in dfs)}",
            ).ask()
        )
        syncer.apply(message)
        syncer.save()


@app.command
@handle_error
def list_dotfiles(
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
):
    """
    List all dotfiles in the manifest.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    print_dotfiles(manifest)


@app.command
@handle_error
def map_orphaned_files(
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    sync: bool = True,
    message: Annotated[str | None, Parameter(alias="m")] = None,
):
    """
    Find and map orphaned files in the manifest root.
    This command will search for files in the manifest root that are not managed by the dotfile manager
    and will print them out. It will also update the manifest file to include these orphaned files.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        sync (bool): Whether to sync the manifest after mapping orphaned files.
        message (str | None): The commit message to use when saving changes.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    linker = PureLinker(manifest=manifest)
    orphaned_files = linker.find_orphaned()
    if not orphaned_files:
        return
    linker.sync_orphaned(orphaned_files)
    linker.remove_ghost_refs()
    persist_changes(manifest, manifest_path)
    if sync:
        syncer = GitSyncer.from_manifest(manifest)
        message = (
            message
            or questionary.text(
                "Enter a commit message for the changes made to the manifest:",
                default="Mapped orphaned files.",
            ).ask()
        )
        syncer.apply(message)
        syncer.save()


@app.command
@handle_error
def revert(
    refspec: str,
    backup_branch: str | None = None,
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    sync: bool = True,
):
    """
    Revert the manifest to a previous state using the specified refspec.
    # THIS FUNCTION IS NOT IMPLEMENTED YET

    Args:
        refspec (str): The refspec to revert to.
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        sync (bool): Whether to sync the manifest after reverting.
    """
    print(
        colored(
            "Reverting the manifest is experimental and may have bugs.",
            "yellow",
        )
    )
    if not questionary.confirm(
        "Are you sure you want to revert the manifest? (y/n)",
        default=True,
    ).ask():
        print(colored("Revert cancelled.", "red"))
        return
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    syncer = GitSyncer.from_manifest(manifest)
    syncer.revert(refspec, backup_branch)
    if sync:
        syncer.save()
    print_manifest(syncer.manifest)


@app.command
@handle_error
def log(
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    limit: int = 10,
    pretty: bool = True
):
    """
    Show the git log of the manifest repository.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        limit (int): The number of log entries to show.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    syncer = GitSyncer.from_manifest(loaders[manifest_format](manifest_path))
    syncer.log(limit, pretty)


@app.command
@handle_error
def exec_(
    dotfile: str | Path,
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    with_command: str | None = None,
):
    """
    Execute a command on a dotfile from the manifest.
    This command will find the dotfile in the manifest and execute the specified command on it.
    If no command is specified, it will print the contents of the dotfile.

    Args:
        dotfile (str | Path): The name or path of the dotfile to execute.
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        with_command (str | None): The command to execute on the dotfile. If None, it will print the contents of the dotfile.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    if isinstance(dotfile, str):
        dotfile = Path(dotfile)
    if dotfile.is_absolute():
        relative_dotfile_loc = dotfile.relative_to(Path.home())
    else:
        relative_dotfile_loc = dotfile
    absolue_dotfile_loc = manifest.root / relative_dotfile_loc
    dfloc = next_or(
        selected
        for selected in manifest.dotfiles
        if selected.name == dotfile.name
        or selected.location
        in map(Path.as_posix, [relative_dotfile_loc, dotfile, absolue_dotfile_loc])
    )
    if dfloc is None:
        raise ValidationError(f"Dotfile {dotfile} not found in the manifest.")
    dfloc_path = resolve_dfman_path(dfloc, manifest)
    if not dfloc_path.exists():
        raise ValidationError(
            f"Brolen dotfile {dfloc.name} does not exist in the manifest root: {dfloc_path}"
        )
    if with_command:
        if not shutil.which(with_command):
            raise ValidationError(f"Command {with_command} not found in PATH.")
        print(colored(f"Running command: {with_command} {dfloc_path}", "yellow"))
        _ = subprocess.run([with_command, str(dfloc_path)], check=True)
    else:
        with open(dfloc_path) as f:
            print(colored(f.read(), "green"))


@app.command
@handle_error
def init(ask: bool = True):
    """
    Initialize the dotfile manager.
    This command will create the default manifest file and set up the dotfile manager.

    Args:
        ask (bool): Whether to ask for confirmation before initializing.
    """
    if not ask:
        print(
            colored(
                "Skipping questionaire. Initializing dotfile manager...",
                "yellow",
            )
        )
        manifest_format = ManifestFormat.TOML
        manifest_path = CONFIG_DIR
        if manifest_path.exists():
            print(
                colored(
                    f"Manifest file {manifest_path} already exists. Please remove it or use a different path.",
                    "yellow",
                )
            )
            return
        manifest_path = manifest_path.with_suffix(f".{manifest_format.value}")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = Manifest(
            root=Path.home() / ".dotfiles",
            repository_url="",
            original_format=manifest_format,
            extra_paths=[],
            default_terminal="",
            default_editor="",
            default_shell=PartialEntry(
                "bash",
                map(Path, ("/usr/bin", "/bin", "/usr/local/bin", "~/.local/bin")),
            ),
            repository_branch="main",
            dotfiles=[],
            pinned_hash="",
        )
    else:
        manifest_config_path = CONFIG_DIR
        manifest_format = questionary.select(
            "Select the manifest format:",
            choices=[
                questionary.Choice(ManifestFormat.TOML, checked=True),
                questionary.Choice(ManifestFormat.YAML),
                questionary.Choice(ManifestFormat.JSON),
            ],
        ).ask()
        manifest_path = manifest_config_path.with_suffix(f".{manifest_format}")
        if manifest_path.exists():
            print(
                colored(
                    f"Manifest file {manifest_path} already exists. Please remove it or use a different path.",
                    "yellow",
                )
            )
            return

        def _validate_path(path: str | Path) -> Path:
            """
            Validate the provided path for the manifest root.
            Ensures that the path is a directory and is writable.
            """
            path = Path(path).expanduser().resolve()
            if not path.is_relative_to(Path.home()):
                raise ValidationError(
                    "The manifest root must be a subdirectory of your home directory."
                )
            return path

        manifest = Manifest(
            root=questionary.path(
                "Enter the root directory for your dotfiles:",
                default=(Path.home() / ".dotfiles").as_posix(),
                validate=_validate_path,
                only_directories=True,
            ).ask(),
            repository_url=questionary.text(
                "Enter the URL of your dotfiles repository",
            ).ask(),
            original_format=manifest_format,
            extra_paths=(),
            default_terminal=questionary.text(
                "Enter your default terminal (leave empty for none):",
                default="",
            ).ask(),
            default_editor=questionary.text(
                "Enter your default editor (leave empty for none):",
                default="",
            ).ask(),
            default_shell=PartialEntry(
                "bash",
                map(Path, ("/usr/bin", "/bin", "/usr/local/bin", "~/.local/bin")),
            ),
            repository_branch=questionary.text(
                "Enter the branch of your repository to use (default: main):",
                default="main",
            ).ask(),
            dotfiles=[],
            pinned_hash=questionary.text(
                "Enter the pinned hash for your repository (leave empty for none):",
                default="",
            ).ask(),
        )

    source_path = manifest.root / manifest_path.name
    if source_path.exists():
        raise ValidationError(
            f"Manifest file {source_path} already exists. Please remove it or use a different path."
        )
    persist_changes(manifest, source_path)
    manifest_path.symlink_to(source_path)
    print(
        colored(
            f"Dotfile manager initialized with manifest at {manifest_path}.",
            "green",
        )
    )
    _ = GitSyncer.init_git(manifest.root)

@app.command
@handle_error
def save_changes(
    manifest_path: Path = CONFIG_DIR,
    manifest_format: ManifestFormat = ManifestFormat.PRESUMED,
    message: Annotated[str | None, Parameter(alias="m")] = None,
    save: bool = True,
):
    """
    Save changes to the manifest and optionally pull changes from the remote repository.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.
        message (str | None): The commit message to use when saving changes.
        save (bool): Whether to save changes to the remote.
    """
    manifest_path, manifest_format = validate_manifest_path(
        manifest_path, manifest_format
    )
    manifest = loaders[manifest_format](manifest_path)
    syncer = GitSyncer.from_manifest(manifest)
    if not syncer.is_dirty():
        print(colored("No changes to save.", "yellow"))
        return
    syncer.apply(message)
    if save:
        syncer.save()
        print(colored("Changes saved successfully.", "green"))
    else:
        print(colored("Changes saved, run `dfman sync` to sync with remote.", "yellow"))
