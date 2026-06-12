# pickwaves_for_SUMA_TEMP_automation (Python + Playwright)

Automates the Helm SUMA TEMP workflow with Python and Playwright.

`suma_temp.py` follows the SUMA TEMP pick creation workflow through Step 36:

- Logs in to Helm.
- Loads the saved Orders filter `Despatch Ready - Pregen Success - To Allocate`.
- Allocates stock, filters fully allocated SUMATEMP orders, and creates picks.
- Captures the created pick references from the pick creation result modal.
- Opens Despatch > Picking and adds the `SUMATEMP` tag to the created pick rows.

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

Streamlit app:

```
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Direct script run:

```
.\.venv\Scripts\Activate.ps1
python suma_temp.py
```

macOS/Linux:

```
source .venv/bin/activate
streamlit run app.py
```

Direct script run:

```
source .venv/bin/activate
python suma_temp.py
```

## Notes

- `suma_temp.py` loads credentials from `.env` using `python-dotenv`.
- `app.py` provides Start and Stop buttons and a fixed-height log panel for the automation output.
- Set `DEBUG=true` to print extra login diagnostics.
- The script prefers the `MULTI` pick reference from the creation result modal for the first tag pass, then tags the `SINGLE` pick reference when it is present.
- `clf_temp.py` and the CLF `prime_picks.py` flow were used as reference patterns for selectors and pick-tagging behavior.
