# Tab Archiver

A local cross-platform app for logging open browser tabs and reopening them later after a shutdown or browser close.

## Download (recommended)

**No git clone. No Python install.**

Get the latest packaged build from the [download page](https://costebk08.github.io/tab-archiver/) or [GitHub Releases](https://github.com/costebk08/tab-archiver/releases/latest):

| Platform | File |
|----------|------|
| Windows | `Tab-Archiver-Windows.zip` → run `Tab Archiver.exe` |
| macOS | `Tab-Archiver-macOS.dmg` |
| Linux | `Tab-Archiver-Linux.tar.gz` |

**Windows SmartScreen:** the first launch of an unsigned app may show “Windows protected your PC.” Click **More info**, then **Run anyway**. See `INSTALL.txt` in the zip for details.

### How to use

1. **Download** the build for your operating system
2. **Open the app** and leave it running
3. Click **Render Open Websites**, choose a browser, select tabs, and **Archive**

## Features

- Scans running browsers (Chrome, Edge, Brave, Firefox)
- Works on **Windows, macOS, and Linux**
- Checkbox archive workflow with collapsible local history
- **Open All** restores archived websites in one click
- **Start at login** toggle in the app
- **Update available** notice when a newer GitHub release is published

## Developer setup

If you want to run from source instead of a packaged download:

```bash
python3 launch.py
```

Or use the platform launcher scripts in the project folder.

Archive history is stored at `~/.tab-archiver/history.json`.

## Publishing a release

See [PACKAGING.md](PACKAGING.md) for PyInstaller builds, GitHub Actions releases, GitHub Pages, and optional code signing.

Quick release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Notes

- Private/incognito browsing is not supported
- Browsers lock session files while running; the app copies them to a temp folder before parsing
- Packaged builds are unsigned by default unless you configure signing secrets in GitHub Actions
