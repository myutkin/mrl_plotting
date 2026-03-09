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
