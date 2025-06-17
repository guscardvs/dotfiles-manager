import sys
from collections.abc import Callable, Mapping
from io import StringIO
from pathlib import Path
from typing import cast

import orjson
import tomlkit
from escudeiro.data import asdict, fromdict
from escudeiro.ds import CallableRegistry
from escudeiro.misc import jsonx
from orjson import JSONDecodeError
from ruamel.yaml import YAML, YAMLError
from termcolor import colored
from tomlkit.exceptions import TOMLKitError

from dotfile_manager.utils import ValidationError

from .concepts import ManifestFormat
from .schema import Dotfile, Manifest

yaml_loader = YAML()

loaders = CallableRegistry[ManifestFormat, Callable[[Path], Manifest]](
    ManifestFormat, prefix="_loader_"
)
dumpers = CallableRegistry[ManifestFormat, Callable[[Manifest], str]](
    ManifestFormat, prefix="_dump_"
)


@loaders
def _loader_yaml(manifest_path: Path) -> Manifest:
    try:
        with open(manifest_path) as stream:
            output_map = yaml_loader.load(stream)
        output_map.setdefault("original_format", ManifestFormat.YAML)
        return fromdict(Manifest, output_map)
    except YAMLError as e:
        raise ValidationError(f"Error parsing YAML manifest: {e}")
    except (KeyError, TypeError, ValueError) as e:
        raise ValidationError(f"Error converting YAML manifest data: {e}") from e


@loaders
def _loader_json(manifest_path: Path) -> Manifest:
    try:
        with open(manifest_path) as stream:
            output_map = jsonx.load(stream)
            output_map.setdefault("original_format", ManifestFormat.JSON)
            return fromdict(Manifest, output_map)
    except (JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise ValidationError(f"Error parsing JSON manifest: {e}")


@loaders
def _loader_toml(manifest_path: Path) -> Manifest:
    try:
        with open(manifest_path) as stream:
            output_map = cast(Mapping, tomlkit.load(stream))["dotfile_manager"]
        output_map.setdefault("original_format", ManifestFormat.TOML)
        return fromdict(Manifest, output_map)
    except (TOMLKitError, KeyError) as e:
        raise ValidationError(f"Error parsing TOML manifest: {e}")
    except (KeyError, TypeError, ValueError) as e:
        raise ValidationError(f"Error converting TOML manifest data: {e}") from e


@dumpers
def _dump_yaml(manifest: Manifest) -> str:
    """
    Dumps the manifest to a YAML string.

    Args:
        manifest (Manifest): The manifest to dump.

    Returns:
        str: The YAML representation of the manifest.
    """
    manifest_dict = dict(asdict(manifest))
    _ = manifest_dict.pop("original_format", None)  # Remove original_format if present
    stream = StringIO()
    yaml_loader.dump(manifest_dict, stream)
    return stream.getvalue()


@dumpers
def _dump_json(manifest: Manifest) -> str:
    """
    Dumps the manifest to a JSON string.

    Args:
        manifest (Manifest): The manifest to dump.

    Returns:
        str: The JSON representation of the manifest.
    """
    output = dict(asdict(manifest))
    _ = output.pop("original_format", None)  # Remove original_format if present
    return jsonx.dumps(output, option=orjson.OPT_INDENT_2)

@dumpers
def _dump_toml(manifest: Manifest) -> str:
    """
    Dumps the manifest to a TOML string.

    Args:
        manifest (Manifest): The manifest to dump.

    Returns:
        str: The TOML representation of the manifest.
    """
    output = dict(asdict(manifest))
    _ = output.pop("original_format", None)
    # Remove original_format if present
    return tomlkit.dumps({"dotfile_manager": output})

def validate_manifest_path(
    manifest_path: Path, manifest_format: ManifestFormat
) -> tuple[Path, ManifestFormat]:
    """
    Validates the manifest path and returns it.
    If the manifest format is PRESUMED, it attempts to determine the format
    based on the file extension.
    Raises:
        ValidationError: If the manifest file does not exist or is not a file.
    If the manifest format cannot be determined from the file extension.

    Args:
        manifest_path (Path): The path to the manifest file.
        manifest_format (ManifestFormat): The format of the manifest file.

    Returns:
        tuple[Path, ManifestFormat]: A tuple containing the validated manifest path and its format.
    """
    # validate if the manifest lacks a file extension
    if manifest_path.suffix == "":
        # default to TOML if no extension is provided
        if manifest_format is ManifestFormat.PRESUMED:
            manifest_format = ManifestFormat.TOML
        # rename the file to include the default extension
        manifest_path = manifest_path.with_suffix(
            f".{manifest_format}"
        )
    if not manifest_path.exists():
        raise ValidationError(f"Manifest file does not exist: '{manifest_path}'")
    if not manifest_path.is_file():
        raise ValidationError(f"Manifest path is not a file: '{manifest_path}'")
    if manifest_format is ManifestFormat.PRESUMED:
        extension = manifest_path.suffix.strip(".")
        manifest_format = ManifestFormat(extension)
        if manifest_format is ManifestFormat.PRESUMED:
            raise ValidationError(
                f"Could not determine manifest format from file extension: '{manifest_path.suffixes}'"
            )
    return manifest_path, manifest_format


def print_manifest(manifest: Manifest) -> None:
    """
    Prints the manifest in a human-readable format.

    Args:
        manifest (Manifest): The manifest to print
    """

    print(colored(tomlkit.dumps({"dotfile_manager": asdict(manifest)}), "green"))
    if sys.stdout.isatty():
        print(colored("\nManifest printed successfully.", "green"))
    else:
        print(
            colored(
                "Manifest printed successfully. Use a terminal that supports color for better readability.",
                "yellow",
            )
        )

def print_dotfiles(manifest: Manifest) -> None:
    """
    Prints the dotfiles in the manifest in a human-readable format.

    Args:
        manifest (Manifest): The manifest containing dotfiles to print.
    """
    dotfiles = manifest.dotfiles
    if not dotfiles:
        print(colored("No dotfiles found in the manifest.", "yellow"))
        return

    print(colored("Dotfiles in the manifest:", "blue"))
    for dotfile in dotfiles:
        location = resolve_location(dotfile, manifest)
        dflocation = resolve_dfman_path(dotfile, manifest)
        if not dflocation.exists():
            state = "broken, no matching file in dotfile manager folder"
        elif location.is_symlink():
            if  dflocation.resolve() != location.resolve():
                state = "broken, symlink points to a different file"
            else:
                state = "linked"
        elif not location.exists():
            state = f"unlinked, run `dfman link '{dflocation}'` to link it"
        else:
            state = "broken, location exists but is not a symlink"

        print(
            colored(
                f"{dotfile.name} -> {dotfile.location} (dflocation: {dotfile.dflocation}, state: {state})",
                "cyan",
            )
        )

def resolve_dfman_path(dotfile: Dotfile, manifest: Manifest) -> Path:
    """
    Resolves the path of a dotfile in the manifest.

    Args:
        dotfile (Dotfile): The dotfile to resolve.
        manifest (Manifest): The manifest containing the dotfile.

    Returns:
        (Path): The resolved path of the dotfile.
    """

    dflocation = Path(dotfile.dflocation or dotfile.location).expanduser()
    if not dflocation.is_absolute():
        dflocation = manifest.root / dflocation
    elif not dflocation.relative_to(manifest.root):
        dflocation = manifest.root / dflocation.relative_to(Path.home())
    
    return dflocation

def resolve_location(dotfile: Dotfile, manifest: Manifest) -> Path:
    """
    Resolves the location of a dotfile in the manifest.

    Args:
        dotfile (Dotfile): The dotfile to resolve.
        manifest (Manifest): The manifest containing the dotfile.

    Returns:
        (Path): The resolved location of the dotfile.
    """
    location = Path(dotfile.location).expanduser()
    if not location.is_absolute():
        location = Path.home() / location
    elif location.is_relative_to(manifest.root):
        location = Path.home() / location.relative_to(manifest.root)
    return location.expanduser()
