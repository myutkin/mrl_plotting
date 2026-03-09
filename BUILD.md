# Build

Install dependencies locally:

```bash
python -m pip install -r requirements.txt
```

Run the app:

```bash
python main.py
```

Build a local executable:

```bash
pyinstaller main.spec --clean
```

GitHub Actions builds Windows and Linux artifacts automatically from
[`.github/workflows/build.yml`](/data/Work/apps/plot_app/.github/workflows/build.yml).

To publish downloadable release files on GitHub:

```bash
git tag v0.1.0
git push origin main --tags
```

Pushing a tag like `v0.1.0` triggers the workflow to upload Windows and Linux
bundles to the GitHub release for that tag.
