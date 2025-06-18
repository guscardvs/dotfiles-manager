from collections.abc import Collection
from functools import partial
from pathlib import Path

from escudeiro.config import utils
from escudeiro.data import data, field

from dotfile_manager.manifest.concepts import ManifestFormat
from dotfile_manager.utils import PartialEntry


@data(frozen=False)
class Dotfile:
    name: str
    location: str
    dflocation: str = ""
    description: str = ""

as_tuple_field = partial(field, fromdict=list)
_as_path = utils.instance_is_casted(Path, Path)


def find_or_create_path(pathstr: str | Path) -> Path:
    """
    Converts a string path to a Path object, expanding user directories.
    """
    path = _as_path(pathstr).expanduser().resolve()
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return path

def path_as_posix(path: Path) -> str:
    """
    Converts a Path object to a POSIX string representation.
    """
    home = Path.home()
    if path.is_absolute() and path.is_relative_to(home):
        path = path.relative_to(home)
        return f"~/{path.as_posix()}"
    else:
        return path.as_posix()


@data
class Manifest:
    root: Path = field(asdict=path_as_posix, fromdict=find_or_create_path)
    repository_url: str
    original_format: ManifestFormat
    extra_paths: Collection[str] = as_tuple_field()
    default_terminal: str = ""
    default_editor: str = ""
    default_shell: PartialEntry = PartialEntry(
        "bash", map(Path, ("/usr/bin", "/bin", "/usr/local/bin", "~/.local/bin"))
    )
    repository_branch: str = "main"
    dotfiles: list[Dotfile] =field(default_factory=list)
    pinned_hash: str = ""