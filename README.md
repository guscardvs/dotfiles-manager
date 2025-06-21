# Dotfile Manager

A flexible, Python-based tool for managing, synchronizing, and linking your dotfiles across systems using a manifest-driven approach.

---

## Features

- **Manifest-based configuration**: Supports TOML, YAML, and JSON formats.
- **Git integration**: Synchronize dotfiles with remote repositories.
- **Automatic linking**: Create symlinks for dotfiles as specified in the manifest.
- **System import**: Generate manifests from your current dotfiles.
- **Orphaned file detection**: Find and manage unmanaged files in your dotfiles directory.
- **Customizable**: Easily extendable and configurable.

---

## Goals

Check pending features at [goals.md](./goals.md)

---

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/yourusername/dotfile-manager.git
cd dotfile-manager
pip install -e .
```

---

## Usage

All commands are available via the CLI app:

```bash
dfman <command> [options]
```

### Commands Overview

Below are the main commands with usage and examples.

---

### `init`

Initialize the dotfile manager and create a manifest.

```bash
dfman init
```

- Prompts for manifest format, root directory, repository URL, and other settings.
- Creates a manifest file and initializes the dotfiles directory.

---

### `check`

Print the current manifest in a human-readable format.

```bash
dfman check
```

---

### `sync`

Synchronize dotfiles with the remote repository (pull and/or push changes).

```bash
dfman sync --pull --save --m "Sync message"
```

- `--pull`: Pull changes from remote (default: True)
- `--save`: Push local changes (default: True)
- `--m`: Commit message

---

### `review`

Show the current status of the dotfiles git repository.

```bash
dfman review
```

---

### `link`

Create symlinks for dotfiles as specified in the manifest.

```bash
dfman link
dfman link ~/.bashrc ~/.vimrc
```

- If no files are specified, links all dotfiles in the manifest.

---

### `from-system`

Import dotfiles from your system into the manifest and dotfiles directory.

```bash
dfman from-system
dfman from-system ~/.bashrc ~/.vimrc
```

- Moves/copies files from your home directory into the managed directory and updates the manifest.

---

### `download`

Clone a remote dotfiles repository and set up the manifest.

```bash
dfman download --repository-url <url> --branch main
```

- Downloads the repository and links the manifest file.

---

### `edit-file`

Edit a file using your preferred editor and add it to the manifest.

```bash
dfman edit-file ~/.bashrc --editor nvim
```

- Opens the file in the specified editor, creates a symlink, and updates the manifest.

---

### `edit-manifest`

Edit the manifest file directly in your editor.

```bash
dfman edit-manifest --editor nvim
```

---

### `unlink`

Remove symlinks for specified dotfiles (or all if none specified).

```bash
dfman unlink
dfman unlink ~/.bashrc
```

---

### `remove`

Remove dotfiles from the manifest and unlink them.

```bash
dfman remove ~/.bashrc ~/.vimrc
```

---

### `list-dotfiles`

List all dotfiles in the manifest.

```bash
dfman list-dotfiles
```

---

### `map-orphaned-files`

Find and map orphaned files in the dotfiles directory (files not tracked in the manifest).

```bash
dfman map-orphaned-files
```

---

### `log`

Show the git log of the dotfiles repository.

```bash
dfman log --limit 20
```

---

### `exec`

Execute a command on a dotfile (e.g., open with an editor or print contents).

```bash
dfman exec ~/.bashrc --with-command nvim
dfman exec ~/.bashrc
```

---

### `save-changes`

Save changes to the manifest and optionally push them to the remote repository.

```bash
dfman save-changes --m "Commit message" --save
```

- `--m`: Commit message for the changes.
- `--save`: Push changes to the remote (default: True). If not set, only commits locally.

---

## Manifest Example

```toml
[dotfile_manager]
root = "~/dotfiles"
repository_url = "git@github.com:yourusername/dotfiles.git"
repository_branch = "main"
dotfiles = [
    { name = ".bashrc", location = ".bashrc" },
    { name = ".vimrc", location = ".vimrc" }
]
```

---

## Project Structure

```
dotfile_manager/
    app.py          # CLI entrypoint
    utils.py        # Utilities and helpers
    linker/         # Symlink logic
    manifest/       # Manifest schema, loader, and format logic
    syncer/         # Git integration
```

---

## Requirements

- Python 3.13+
- [escudeiro](https://guscardvs.github.io/escudeiro)
- [gitpython](https://gitpython.readthedocs.io/)
- [termcolor](https://pypi.org/project/termcolor/)
- [ruamel.yaml](https://pypi.org/project/ruamel.yaml/)
- [tomlkit](https://pypi.org/project/tomlkit/)
- [orjson](https://pypi.org/project/orjson/)
- [cyclopts](https://pypi.org/project/cyclopts/)
- [questionary](https://pypi.org/project/questionary/)

---

## License

Apache License

---

*Contributions welcome! Send your pull requests.*
