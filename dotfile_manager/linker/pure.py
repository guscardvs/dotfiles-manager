import shutil
from collections.abc import Collection
from pathlib import Path

from escudeiro.data import data
from termcolor import colored

from dotfile_manager.manifest.loader import resolve_dfman_path, resolve_location
from dotfile_manager.manifest.schema import Dotfile, Manifest, path_as_posix
from dotfile_manager.utils import ValidationError

USUAL_DOTFILES = (
    ".bashrc",
    ".zshrc",
    ".vimrc",
    ".tmux.conf",
    ".profile",
    ".config/nvim/init.vim",
    ".config/alacritty/alacritty.yml",
    ".config/kitty/kitty.conf",
    ".config/starship.toml",
    ".config/ghostty/config",
    ".config/hypr/hyprland.conf",
    ".config/waybar/config",
    ".antigenrc",
)


@data
class PureLinker:
    manifest: Manifest

    def link(self, dotfile: Dotfile) -> None:
        """
        Create a symlink for the dotfile in the specified location.

        Args:
            dotfile (Dotfile): The dotfile to link.
        """
        if not dotfile.dflocation:
            out_location = self._link_by_structure(dotfile)
        else:
            out_location = self._link_direct(dotfile)
        print(colored(f"Linked {dotfile.name} to {out_location}", "green"))

    def _link_by_structure(self, dotfile: Dotfile) -> str:
        """
        Create a symlink for the dotfile based on dotfiles
        folder structure where root == $HOME.

        Args:
            dotfile (Dotfile): The dotfile to link.

        Returns:
            str: The location of the created symlink.
        """
        home = Path.home()
        loc = Path(dotfile.location).expanduser().resolve()
        if not loc.is_absolute():
            loc = home / loc
        elif not loc.is_relative_to(home):
            raise ValidationError(
                "Cannot link by structure for absolute paths that"
                + " are not relative to $HOME. "
            )
        floc = self.manifest.root / loc.relative_to(home)
        if not floc.exists():
            raise ValidationError(
                f"Dotfile location {floc} does not exist. "
                + "Please ensure the dotfile is present in the manifest root."
            )
        out_location = home / dotfile.location
        if out_location.exists():
            raise ValidationError(
                f"Output location {out_location} already exists. "
                + "Please remove it before linking."
            )
        out_location.parent.mkdir(parents=True, exist_ok=True)
        out_location.symlink_to(floc, target_is_directory=floc.is_dir())
        return out_location.as_posix()

    def _link_direct(self, dotfile: Dotfile) -> str:
        """
        Create a symlink for the dotfile directly to its specified location.

        Args:
            dotfile (Dotfile): The dotfile to link.

        Returns:
            str: The location of the created symlink.
        """
        floc = resolve_dfman_path(dotfile, self.manifest)
        out_location = resolve_location(dotfile, self.manifest)
        if out_location.exists():
            if out_location.is_symlink() and out_location.resolve() == floc.resolve():
                print(
                    colored(
                        f"Output location {out_location} already exists and "
                        + "is a symlink to the correct location. Skipping.",
                        "yellow",
                    )
                )
                return out_location.as_posix()
            raise ValidationError(
                f"Output location {out_location} already exists. "
                + "Please remove it before linking."
            )
        elif out_location.is_symlink():
            print(
                colored(
                    f"Output location {out_location} is a ghost symlink. "
                    + "Removing it before creating a new link.",
                    "yellow",
                )
            )
            out_location.unlink()
        out_location.parent.mkdir(parents=True, exist_ok=True)
        print(
            colored(
                f"Creating symlink for {dotfile.name} at {out_location} pointing to {floc}",
                "cyan",
            )
        )
        if not floc.exists():
            raise ValidationError(
                f"Dotfile location {floc} does not exist. "
                + "Please ensure the dotfile is present in the manifest root."
            )
        out_location.symlink_to(floc, target_is_directory=floc.is_dir())
        return out_location.as_posix()

    def link_all(self) -> None:
        """
        Create symlinks for all dotfiles in the manifest.
        """
        for dotfile in self.manifest.dotfiles:
            self.link(dotfile)

    def save_from_system(self, dotfiles: Collection[Path]):
        """
        Update the manifest with the current system's dotfiles.

        Args:
            dotfiles (Collection[str]): A collection of dotfile names to update.
        """
        print(colored("Updating manifest with current system's dotfiles...", "yellow"))
        for file in dotfiles:
            print(colored(f"Checking dotfile: {file}", "cyan"))
            if not (file.exists() or file.is_file()):
                print(
                    colored(
                        f"Dotfile {file} does not exist or is not a file. Skipping.",
                        "red",
                    )
                )
                continue
            dfloc = self.manifest.root / file.relative_to(Path.home())
            if (
                dfloc.exists()
                and file.is_symlink()
                and dfloc.resolve() == file.resolve()
            ):
                print(
                    colored(
                        f"Dotfile {file} is already a symlink. Skipping.",
                        "yellow",
                    )
                )
                continue
            elif file.is_symlink() and dfloc.resolve() != file.resolve():
                print(
                    colored(
                        f"Dotfile {file} is a broken symlink. Skipping.",
                        "red",
                    )
                )
                continue
            dotfile = Dotfile(
                name=file.name,
                location=path_as_posix(file),
                dflocation=dfloc.relative_to(self.manifest.root).as_posix(),
                description=f"Auto-generated dotfile for {file.name}",
            )
            print(
                colored(
                    f"Adding dotfile: {dotfile.name} found in {dotfile.location}",
                    "blue",
                )
            )
            if dfloc.exists() and dfloc.is_symlink():
                print(
                    colored(
                        f"Dotfile {dotfile.name} already exists at {dfloc}. Skipping.",
                        "yellow",
                    )
                )
                continue
            elif dfloc.exists() and not dfloc.is_file():
                print(
                    colored(
                        f"Dotfile {dotfile.name} exists at {dfloc} but is not a file. "
                        + "Please remove it before adding.",
                        "red",
                    )
                )
                continue
            if not dfloc.exists():
                dfloc.parent.mkdir(parents=True, exist_ok=True)
            if file.is_file():
                _ = shutil.move(file, dfloc)
            else:
                # If it's a directory, copy it instead of moving
                _ = shutil.copytree(file, dfloc, dirs_exist_ok=True)
                shutil.rmtree(file, ignore_errors=True)
            self.manifest.dotfiles.append(dotfile)

        print(colored("Manifest updated with current system's dotfiles.", "green"))

    def unlink(self, dotfile: Dotfile) -> None:
        """
        Remove the symlink for the dotfile.

        Args:
            dotfile (Dotfile): The dotfile to unlink.
        """
        home = Path.home()
        out_location = home / dotfile.location
        if not out_location.exists():
            raise ValidationError(
                f"Output location {out_location} does not exist. "
                + "Please ensure the dotfile is linked before unlinking."
            )
        if not out_location.is_symlink():
            raise ValidationError(
                f"Output location {out_location} is not a symlink. "
                + "Please ensure the dotfile is linked before unlinking."
            )
        print(colored(f"Unlinking {dotfile.name} from {out_location}", "yellow"))
        if out_location.is_dir():
            print(
                colored(f"Removing directory {out_location} before unlinking.", "red")
            )
            shutil.rmtree(out_location, ignore_errors=True)
        else:
            # TODO: this might leave ghost parent dirs, should we handle that?
            out_location.unlink()
        print(colored(f"Unlinked {dotfile.name} from {out_location}", "green"))

    def unlink_all(self) -> None:
        """
        Remove symlinks for all dotfiles in the manifest.
        """
        for dotfile in self.manifest.dotfiles:
            try:
                self.unlink(dotfile)
            except ValidationError as e:
                print(colored(str(e), "red"))

    def find_orphaned(self) -> list[Path]:
        """
        Find unmanaged files and directories inside manifest.root.

        Returns:
            list[Path]: A list of unmanaged files and directories in the manifest root.
        """
        orphaned_files: list[Path] = []
        for item in self.manifest.root.iterdir():
            if item.is_dir() and item.name == ".git":
                # Skip the .git directory
                continue
            if (
                item.is_file()
                and item
                == self.manifest.root / f"dfman.{self.manifest.original_format}"
            ):
                # Skip the manifest file itself
                continue
            if self._is_orphaned(item):
                orphaned_files.append(item)
        if orphaned_files:
            print(
                colored(
                    "Found unmanaged files and directories in the manifest root:",
                    "yellow",
                )
            )
            for file in orphaned_files:
                print(colored(f"- {file}", "cyan"))
        else:
            print(
                colored(
                    "No unmanaged files or directories found in the manifest root.",
                    "green",
                )
            )
        return orphaned_files

    def _is_orphaned(self, path: Path) -> bool:
        """
        Check if a file is orphaned (not managed by the manifest).

        Args:
            file (Path): The file to check.

        Returns:
            bool: True if the file is orphaned, False otherwise.
        """
        if not path.is_file() and not path.is_dir():
            return False
        relative_path = path.relative_to(self.manifest.root)
        for dotfile in self.manifest.dotfiles:
            # Check if the dotfile's location matches the path's relative path
            if dotfile.location == relative_path.as_posix():
                return False
            # Check if the managed part is a subdirectory of the path
            elif Path(dotfile.dflocation).is_relative_to(relative_path):
                return False
        return True

    def sync_orphaned(self, orphaned_files: list[Path]) -> None:
        """
        Sync orphaned files and directories by removing them.

        Args:
            orphaned_files (list[Path]): A list of unmanaged files and directories to remove.
        """
        if not orphaned_files:
            print(colored("No unmanaged files to sync.", "green"))
            return
        print(colored("Syncing unmanaged files and directories...", "yellow"))
        for file in orphaned_files:
            likely_location = Path.home() / file.relative_to(self.manifest.root)
            dotfile = Dotfile(
                name=file.name,
                location=likely_location.relative_to(Path.home()).as_posix(),
                dflocation=file.relative_to(self.manifest.root).as_posix(),
                description=f"Unmanaged dotfile for {file.name}",
            )
            if (
                not likely_location.is_symlink() and likely_location.exists()
            ) or likely_location.resolve() != file.resolve():
                print(
                    colored(
                        f"Dotfile is broken: {dotfile.dflocation} -> ({likely_location.as_posix()}), not fixing it.",
                        "red",
                    )
                )
                continue
            elif likely_location.exists():
                print(colored(f"Dotfile {dotfile.name} already linked.", "green"))
            else:
                self.link(dotfile)
            self.manifest.dotfiles.append(dotfile)

        print(colored("Unmanaged files and directories synced.", "green"))

    def remove_ghost_refs(self) -> None:
        """
        Remove entries in the manifest that are not present in the manifest root.
        """
        print(colored("Removing ghost references from the manifest...", "yellow"))
        original_count = len(self.manifest.dotfiles)
        existing = [
            dotfile
            for dotfile in self.manifest.dotfiles
            if (self.manifest.root / dotfile.dflocation).exists()
        ]
        missing = [
            dotfile
            for dotfile in self.manifest.dotfiles
            if not (self.manifest.root / dotfile.dflocation).exists()
        ]
        self.manifest.dotfiles.clear()
        self.manifest.dotfiles.extend(existing)
        removed_count = original_count - len(existing)
        if removed_count > 0:
            print(
                colored(
                    f"Removed {removed_count} ghost references from the manifest.",
                    "green",
                )
            )
            print(
                colored(
                    "The following dotfiles were removed from the manifest:",
                    "yellow",
                )
            )
            for dotfile in missing:
                print(colored(f"- {dotfile.name} ({dotfile.dflocation})", "red"))
        else:
            print(colored("No ghost references found in the manifest.", "green"))

    def make_backups(self, files: list[Path]) -> list[tuple[Path, Path]]:
        """
        Create backups of the specified files.

        Args:
            files (list[Path]): A list of files to back up.

        Returns:
            list[tuple[Path, Path]]: A list of tuples containing the original file and its backup.
        """
        backups: list[tuple[Path, Path]] = []
        for file in files:
            if not file.exists():
                print(colored(f"File {file} does not exist. Skipping backup.", "red"))
                continue
            backup_file = file.with_suffix(file.suffix + ".bak")
            if file.is_file():
                _ = shutil.copy(file, backup_file)
            else:
                _ = shutil.copytree(file, backup_file, dirs_exist_ok=True)
            backups.append((file, backup_file))
            print(colored(f"Backed up {file} to {backup_file}", "green"))
        return backups

    def restore_backups(self, backups: list[tuple[Path, Path]]) -> None:
        """
        Restore files from their backups.

        Args:
            backups (list[tuple[Path, Path]]): A list of tuples containing the original file and its backup.
        """
        for original, backup in backups:
            if not backup.exists():
                print(
                    colored(f"Backup {backup} does not exist. Skipping restore.", "red")
                )
                continue
            if original.exists():
                print(
                    colored(
                        f"Original file {original} exists. Overwriting it.", "yellow"
                    )
                )
            if backup.is_file():
                _ = shutil.move(backup, original)
            else:
                if original.exists() and original.is_dir():
                    print(
                        colored(
                            f"Original {original} is a directory. Removing it before restoring.",
                            "yellow",
                        )
                    )
                    shutil.rmtree(original, ignore_errors=True)
                _ = shutil.copytree(backup, original, dirs_exist_ok=True)
                shutil.rmtree(backup, ignore_errors=True)
            print(colored(f"Restored {original} from {backup}", "green"))

    def delete_backups(self, backups: list[tuple[Path, Path]]) -> None:
        """
        Delete the specified backup files.

        Args:
            backups (list[tuple[Path, Path]]): A list of tuples containing the original file and its backup.
        """
        for original, backup in backups:
            if not backup.exists():
                print(
                    colored(
                        f"Backup {backup} does not exist. Skipping deletion.", "red"
                    )
                )
                continue
            if backup.is_file():
                backup.unlink()
            else:
                shutil.rmtree(backup, ignore_errors=True)
            print(colored(f"Deleted backup {backup} for {original}", "green"))

    def persist_links(self) -> None:
        """
        Persist the current links to the manifest file.
        This updates the manifest with the current state of the dotfiles.
        """
        print(colored("Persisting links to the manifest...", "yellow"))
        # remove original files and make symlinks from the manifest root
        for dotfile in self.manifest.dotfiles:
            dfman_location = resolve_dfman_path(dotfile, self.manifest)
            out_location = resolve_location(dotfile, self.manifest)
            if not dfman_location.exists():
                print(
                    colored(
                        f"Dotfile {dotfile.name} does not exist in the manifest root. "
                        + "Skipping link persistence.",
                        "red",
                    )
                )
                continue
            if out_location.exists() and not out_location.is_symlink():
                print(
                    colored(
                        f"Output location {out_location} exists and is not a symlink. "
                        + "Removing it before linking.",
                        "yellow",
                    )
                )
                if out_location.is_dir():
                    shutil.rmtree(out_location, ignore_errors=True)
                else:
                    out_location.unlink()
            elif (
                out_location.is_symlink()
                and out_location.resolve() != dfman_location.resolve()
            ):
                print(
                    colored(
                        f"Output location {out_location} is a ghost symlink. "
                        + "Removing it before linking.",
                        "yellow",
                    )
                )
                shutil.rmtree(out_location, ignore_errors=True)
            elif not out_location.exists():
                out_location.parent.mkdir(parents=True, exist_ok=True)
                out_location.symlink_to(
                    dfman_location, target_is_directory=dfman_location.is_dir()
                )

                print(
                    colored(
                        f"Linked {dotfile.name} to {out_location} -> {dfman_location}",
                        "green",
                    )
                )
            else:
                print(
                    colored(
                        f"Output location {out_location} already exists and is a symlink to the correct location. Skipping.",
                        "yellow",
                    )
                )
        print(colored("Links persisted to the manifest.", "green"))
