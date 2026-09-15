# ECADEC-PW (PowerShell-only)

Minimal PowerShell commands to set up, check PowerFactory, create a matching virtualenv, install, run, and test.

Start by cloning the repository and entering its folder:

```powershell
git clone <your-repo-url>
Set-Location ECADEC-PW
```

1) Check PowerFactory Python and interpreter (first)

```powershell
# Does the PowerFactory Python folder exist?
Test-Path 'C:\Program Files\DIgSILENT\PowerFactory 2026 SP3\Python\3.14\python.exe'

# If present, print its Python version and check the powerfactory import
& 'C:\Program Files\DIgSILENT\PowerFactory 2026 SP3\Python\3.14\python.exe' -c "import sys, importlib.util; print(sys.version); print(importlib.util.find_spec('powerfactory'))"

# Also show the interpreter you will use for normal 'python'
python -V
python -c "import sys; print(sys.executable)"
```

2) Create a virtualenv using the PowerFactory Python (recommended if PowerFactory folder exists)

```powershell
# create venv with PowerFactory's interpreter
& 'C:\Program Files\DIgSILENT\PowerFactory 2026 SP3\Python\3.14\python.exe' -m venv .venv-3.14

# activate it
.\.venv-3.14\Scripts\Activate.ps1

# ensure pip is up-to-date and install deps into this venv
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

3) (Alternative) Create and activate a regular project venv using the system/default `python`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

4) Run the package

```powershell
python -m ecadec_pw.simulate
# or, after editable install:
simulate-new
```

5) Run tests

```powershell
python -m pip install pytest
pytest -q
```

6) If `import powerfactory` fails, example fixes

```powershell
# Option A: run with PowerFactory's python directly
& 'C:\Program Files\DIgSILENT\PowerFactory 2026 SP3\Python\3.14\python.exe' -m ecadec_pw.simulate

# Option B: add PowerFactory python folder to PATH for the current session then run
$env:PATH = 'C:\Program Files\DIgSILENT\PowerFactory 2026 SP3\Python\3.14;' + $env:PATH
python -m ecadec_pw.simulate
```

7) Windows execution policy (if activation blocked):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Installing Git

If you don't have Git installed on your computer, follow the steps below for your operating system.

Windows
- Download and run the official installer: https://git-scm.com/download/win
- Run the installer (default options are fine for most users).
- Open PowerShell and verify the install:
```powershell
git --version
```

macOS
- Using Homebrew:
```bash
brew install git
```
- Or install the Xcode Command Line Tools:
```bash
xcode-select --install
```

Linux (Debian/Ubuntu)
```bash
sudo apt update
sudo apt install git
```

Linux (Fedora/CentOS/RHEL)
```bash
sudo dnf install git
```

Verify installation on any OS:
```bash
git --version
```

See the official Git downloads page for more options: https://git-scm.com/downloads
