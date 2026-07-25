$ErrorActionPreference = "Stop"

if (Get-Command python -ErrorAction SilentlyContinue) {
  python app.py
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  py -3 app.py
} else {
  Write-Error "No Python runtime found. Please install Python 3 and try again."
}
