from pathlib import Path

from escudeiro.misc import autopath

from dotfile_manager.utils import configdir

CONFIG_DIR = configdir() / "dfman"


def get_default_repository_path(repository: str | Path | None) -> Path:
    if repository is None:
        return Path.home() / ".dotfiles"
    return autopath(repository)
