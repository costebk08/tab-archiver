# Packaging and Releases

## End-user downloads

Published builds are attached to GitHub Releases:

- `Tab-Archiver-Windows.zip` — contains `Tab Archiver.exe`
- `Tab-Archiver-macOS.dmg` — macOS app bundle
- `Tab-Archiver-Linux.tar.gz` — Linux executable

Landing page: enable GitHub Pages from the `docs/` folder, or use the Pages job in the release workflow.

Download page links:

- Latest release: `https://github.com/<owner>/<repo>/releases/latest`
- Windows asset: `.../releases/latest/download/Tab-Archiver-Windows.zip`

Update `app/config.py` if the GitHub repo slug differs from `costebk08/tab-archiver`.

## Build locally

```bash
pip install -r requirements.txt -r requirements-build.txt
pyinstaller packaging/tab_archiver.spec --noconfirm
```

macOS app bundle:

```bash
pyinstaller packaging/tab_archiver_mac.spec --noconfirm
```

## Create a release

1. Commit and push the repository to GitHub.
2. Enable GitHub Pages (Settings → Pages → Build and deployment → GitHub Actions).
3. Create and push a version tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The `Release` workflow builds all three platforms and publishes assets automatically.

## Optional code signing

The workflow includes placeholder steps for signing. To enable production signing, add repository secrets and replace the placeholder commands:

| Platform | Secrets |
|----------|---------|
| Windows | `WINDOWS_CERTIFICATE`, `WINDOWS_CERTIFICATE_PASSWORD` |
| macOS | `APPLE_CERTIFICATE_BASE64`, `APPLE_CERTIFICATE_PASSWORD` |

Unsigned builds still work, but operating systems may show extra security prompts on first launch.
