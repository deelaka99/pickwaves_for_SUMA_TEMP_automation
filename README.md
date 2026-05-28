# pickwaves_for_SUMA_TEMP_automation (Python + Playwright)

Automates the Helm SUMA TEMP workflow with Python and Playwright.

The SUMA TEMP script currently handles the shared Helm login flow. The remaining SUMA TEMP steps will be added to `suma_temp.py` as each instruction screenshot and `outerHTML` is provided.

## Setup

1) Create a virtual environment and install dependencies:

```
python -m venv .venv
```

Windows PowerShell:

```
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install
```

macOS/Linux:

```
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
```

2) Set environment variables, or add them to a `.env` file in this folder:

```
$env:HELM_URL="https://mybeautyandcareltd.myhelm.app/"
$env:HELM_EMAIL="your-email@example.com"
$env:HELM_PASSWORD="your-password"
```

macOS/Linux:

```
export HELM_URL="https://mybeautyandcareltd.myhelm.app/"
export HELM_EMAIL="your-email@example.com"
export HELM_PASSWORD="your-password"
```

## Run

```
.\.venv\Scripts\Activate.ps1
python suma_temp.py
```

macOS/Linux:

```
source .venv/bin/activate
python suma_temp.py
```

## Notes

- `suma_temp.py` loads credentials from `.env` using `python-dotenv`.
- Set `DEBUG=true` to print extra login diagnostics.
- `clf_temp.py` is the reference automation pattern for the broader Helm workflow.
