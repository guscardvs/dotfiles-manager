from collections.abc import Collection
from pathlib import Path

from escudeiro.data import data
from termcolor import colored

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
        print(f"Linked {dotfile.name} to {out_location}")

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
                "Please ensure the dotfile is present in the manifest root."
            )
        out_location = home / dotfile.location
        if out_location.exists():
            raise ValidationError(
                f"Output location {out_location} already exists. "
                "Please remove it before linking."
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
        home = Path.home()
        floc = self.manifest.root / dotfile.dflocation
        out_location = home / dotfile.location
        if out_location.exists():
            raise ValidationError(
                f"Output location {out_location} already exists. "
                "Please remove it before linking."
            )
        out_location.parent.mkdir(parents=True, exist_ok=True)
        out_location.symlink_to(floc, target_is_directory=floc.is_dir())
        return out_location.as_posix()

    def link_all(self) -> None:
        """
        Create symlinks for all dotfiles in the manifest.
        """
        for dotfile in self.manifest.dotfiles:
            self.link(dotfile)
        print("All dotfiles linked successfully.")

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
            dfloc = (
                    self.manifest.root / file.relative_to(Path.home())
                )
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
                        "Please remove it before adding.",
                        "red",
                    )
                )
                continue
            if not dfloc.exists():
                dfloc.parent.mkdir(parents=True, exist_ok=True)
            
            with open(dfloc, "w") as f:
                f.write(file.read_text())
            self.manifest.dotfiles.append(dotfile)

        print(colored("Manifest updated with current system's dotfiles.", "green"))
