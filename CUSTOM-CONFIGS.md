Run this from the repository after updating your installed End4 configs:

```bash
git fetch origin
./reapply-custom-configs --dry-run
./reapply-custom-configs
```

Reload Quickshell afterward. This utility uses Python 3, Git, and GNU patch, and does not
switch branches, change your checkout, or run the updater itself.

It reads the terminal escaping fix, Wi-Fi rescan button, and optimized SVG
assets from `origin/custom-changes` and patches your installed files. It uses
the common ancestor of `main` and that branch as the original version, so
unrelated changes made by updates or local edits can survive. Whitespace-only
branch changes are ignored, and patch context must match without fuzz. Repeating the
command skips changes that are already present. Keep this repository around
so you can run the command after later updates.

Changed files under `dots/.config/` and `dots/.local/share/` are discovered
automatically and mapped to `${XDG_CONFIG_HOME:-~/.config}/` and
`${XDG_DATA_HOME:-~/.local/share}/`. Repository-only assets such as `.github/`
are ignored. To save more customizations to existing files, commit them to
your custom branch and push. Use
`--ref custom-changes` if you want to read a local branch instead. `--base`
defaults to `main`; it should name the branch tracking the original configs.

All files are checked before anything is written. A conflict or missing file
stops the command without changing installed configs. Resolve conflicting
customizations against the updated configs before retrying. Added, deleted,
renamed, or binary files need manual attention; this utility patches existing
text files (including SVGs). It never fetches branches automatically, so run
`git fetch origin` to include newly pushed changes.

Replaced files are backed up under
`${XDG_STATE_HOME:-~/.local/state}/reapply-custom-configs/<timestamp>/`, with
separate `.config/` and `.local/share/` subdirectories. The command prints the
exact backup directory. To undo a run, copy the contents of those subdirectories
back into your config and data directories respectively. Symlinked configs remain symlinked; their
targets receive the patched contents. No backups are created for a dry run.

Run the isolated checks with:

```bash
python3 sdata/test-reapply-custom-configs.py
```
