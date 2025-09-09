from pathlib import Path
from unittest.mock import patch

import pytest

from dotfile_manager.app import app
from dotfile_manager.linker.default import DefaultLinker
from dotfile_manager.manifest.loader import dumpers, loaders
from dotfile_manager.manifest.schema import Dotfile, Manifest


class TestMapOrphanedFiles:
    def test_map_orphaned_files(
        self,
        loaded_manifest: Manifest,
        dfpath: Path,
        dfmanpath: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        orphaned_file = dfpath / "orphaned_file.txt"
        _ = orphaned_file.write_text("orphaned")
        orphaned_dir = dfpath / "orphaned_dir"
        _ = orphaned_dir.mkdir()
        linked_file = dfpath / "linked_file.txt"
        _ = linked_file.write_text("linked")
        home = Path.home()
        linked_file_target = home / linked_file.name
        linker = DefaultLinker(
            loaded_manifest,
            dfmanpath.with_suffix(f".{loaded_manifest.original_format}"),
        )
        with patch("dotfile_manager.linker.default.print_colored"):
            _ = linker._link_direct( # pyright: ignore[reportPrivateUsage]
                Dotfile(
                    name=linked_file.name,
                    location=linked_file_target.as_posix(),
                    dflocation=linked_file.relative_to(
                        loaded_manifest.root
                    ).as_posix(),
                    description="",
                ),
            )

        _ = app(
            [
                "map-orphaned-files",
                "--manifest-path",
                str(dfmanpath),
                "--manifest-format",
                loaded_manifest.original_format,
                "--no-sync",
            ]
        )

        captured = capsys.readouterr().out.strip().split("\n")
        assert captured == [
            "Found unmanaged files and directories in the manifest root:",
            f"- {orphaned_file}",
            f"- {orphaned_dir}",
            f"- {linked_file}",
            "Syncing unmanaged files and directories...",
            f"Creating symlink for {orphaned_file.name} at {home / orphaned_file.name} pointing to {orphaned_file}",
            f"Linked {orphaned_file.name} to {home / orphaned_file.name}",
            f"Creating symlink for {orphaned_dir.name} at {home / orphaned_dir.name} pointing to {orphaned_dir}",
            f"Linked {orphaned_dir.name} to {home / orphaned_dir.name}",
            f"Dotfile {linked_file.name} already linked.",
            "Unmanaged files and directories synced.",
            "Removing ghost references from the manifest...",
            "No ghost references found in the manifest.",
            f"Manifest file {dfmanpath.with_suffix(f'.{loaded_manifest.original_format}')} updated.",
        ]

        reloaded_manifest = loaders[loaded_manifest.original_format](
            dfmanpath.with_suffix(f".{loaded_manifest.original_format}")
        )

        assert (
            len(reloaded_manifest.dotfiles)
            == len(loaded_manifest.dotfiles) + 3
        )
        paths = [df.dflocation for df in reloaded_manifest.dotfiles]
        assert (
            orphaned_file.relative_to(loaded_manifest.root).as_posix() in paths
        )
        assert (
            orphaned_dir.relative_to(loaded_manifest.root).as_posix() in paths
        )
        assert (
            linked_file.relative_to(loaded_manifest.root).as_posix() in paths
        )

    def test_map_orphaned_files_no_orphans(
        self,
        loaded_manifest: Manifest,
        dfmanpath: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        _ = app(
            [
                "map-orphaned-files",
                "--manifest-path",
                str(dfmanpath),
                "--manifest-format",
                loaded_manifest.original_format,
                "--no-sync",
            ]
        )

        captured = capsys.readouterr().out.strip().split("\n")
        assert captured == [
            "No unmanaged files or directories found in the manifest root.",
            "Removing ghost references from the manifest...",
            "No ghost references found in the manifest.",
            "No changes to be made. Exiting...",
        ]

        reloaded_manifest = loaders[loaded_manifest.original_format](
            dfmanpath.with_suffix(f".{loaded_manifest.original_format}")
        )

        assert len(reloaded_manifest.dotfiles) == len(loaded_manifest.dotfiles)

    def test_map_orphaned_files_ghost_refs(
        self,
        loaded_manifest: Manifest,
        dfmanpath: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        dotfile = Dotfile(
            "ghost_file.txt",
            "ghost_file.txt",
            "ghost_file.txt",
            "Auto-generated dotfile for config",
        )
        loaded_manifest.dotfiles.append(dotfile)

        dumped_manifest = dumpers[loaded_manifest.original_format](
            loaded_manifest
        )
        _ = dfmanpath.with_suffix(
            f".{loaded_manifest.original_format}"
        ).write_text(dumped_manifest)

        _ = app(
            [
                "map-orphaned-files",
                "--manifest-path",
                str(dfmanpath),
                "--manifest-format",
                loaded_manifest.original_format,
                "--no-sync",
            ]
        )

        captured = capsys.readouterr().out.strip().split("\n")
        assert captured == [
            "No unmanaged files or directories found in the manifest root.",
            "Removing ghost references from the manifest...",
            "Removed 1 ghost references from the manifest.",
            "The following dotfiles were removed from the manifest:",
            f"- {dotfile.name} ({dotfile.dflocation})",
            f"Manifest file {dfmanpath.with_suffix(f'.{loaded_manifest.original_format}')} updated.",
        ]


# TODO: Create framework to test git sync
