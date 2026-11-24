# DeskCatSetup.ps1 - One-click DeskCat setup for Windows.
# Finds Python (or installs it), installs PyQt6 if needed, then starts the cat.
# You don't run this directly - double-click run_windows.bat instead.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Step($msg) {
    Write-Host ""
    Write-Host "== $msg" -ForegroundColor Cyan
}

# Run a program hidden and silent; returns its exit code and what it printed.
# This deliberately does not use PowerShell's own "2>" redirection: Windows
# PowerShell turns anything a program prints on its error stream into a
# PowerShell error when redirected, and with "Stop" above that aborts the
# whole setup (which is exactly what a failed "import PyQt6" used to do).
function Invoke-Quiet($exe, $arguments) {
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $exe
        $psi.Arguments = $arguments
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $proc = [System.Diagnostics.Process]::Start($psi)
        $errTask = $proc.StandardError.ReadToEndAsync()
        $out = $proc.StandardOutput.ReadToEnd()
        $proc.WaitForExit()
        $null = $errTask.Result
        return New-Object PSObject -Property @{ Code = $proc.ExitCode; Out = "$out".Trim() }
    } catch {
        return New-Object PSObject -Property @{ Code = 1; Out = "" }
    }
}

# True if this python.exe really runs and is new enough for PyQt6 (3.9+).
function Test-Python($exe) {
    if (-not $exe -or -not (Test-Path $exe)) { return $false }
    $r = Invoke-Quiet $exe '-c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"'
    return ($r.Code -eq 0)
}

# True if PyQt6 can actually be loaded by this Python.
function Test-PyQt($exe) {
    $r = Invoke-Quiet $exe '-c "import PyQt6.QtWidgets"'
    return ($r.Code -eq 0)
}

function Get-PythonExe {
    # 1. python on PATH - but ignore the Microsoft Store stub, which just
    #    opens the Store instead of running Python.
    $cmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*" -and (Test-Python $cmd.Source)) {
        return $cmd.Source
    }
    # 2. The py launcher.
    $py = Get-Command py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($py) {
        $r = Invoke-Quiet $py.Source '-3 -c "import sys; print(sys.executable)"'
        if ($r.Code -eq 0 -and (Test-Python $r.Out)) { return $r.Out }
    }
    # 3. Usual per-user install folders.
    $found = Get-ChildItem "$env:LocalAppData\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    foreach ($f in $found) {
        if (Test-Python $f.FullName) { return $f.FullName }
    }
    return $null
}

try {
    Write-Host "DeskCat setup - first run installs what is missing, then starts the cat."

    # ---- Python ----
    $PyExe = Get-PythonExe
    if (-not $PyExe) {
        Write-Step "Python is not installed yet - installing it now (one-time, a few minutes)..."
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            $ErrorActionPreference = "Continue"
            winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements --silent
            $ErrorActionPreference = "Stop"
            if ($LASTEXITCODE -ne 0 -and -not (Get-PythonExe)) { throw "winget could not install Python. Check your internet connection and try again." }
        } else {
            Write-Host "Downloading the official Python installer..."
            $url = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
            $installer = Join-Path $env:TEMP "python-3.12.7-amd64.exe"
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
            Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
            Remove-Item $installer -ErrorAction SilentlyContinue
        }
        # Pick up the newly installed Python in this session.
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path", "User")
        $PyExe = Get-PythonExe
        if (-not $PyExe) { throw "Python was installed but I still cannot find it. Please restart your PC and double-click run_windows.bat again." }
        Write-Host "Python installed."
    }

    # ---- PyQt6 ----
    Write-Step "Checking DeskCat's graphics library..."
    if (-not (Test-PyQt $PyExe)) {
        Write-Host "Installing PyQt6 (one-time download, about 100 MB)..."
        # pip prints warnings on its error stream; they must not stop the setup.
        $ErrorActionPreference = "Continue"
        if ((Invoke-Quiet $PyExe '-c "import pip"').Code -ne 0) {
            & $PyExe -m ensurepip --upgrade
        }
        & $PyExe -m pip install --disable-pip-version-check -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            # No permission to write into Python's own folder: install for this user only.
            & $PyExe -m pip install --disable-pip-version-check --user -r requirements.txt
        }
        $ErrorActionPreference = "Stop"
        if (-not (Test-PyQt $PyExe)) {
            throw "Could not install PyQt6 for $PyExe. Check your internet connection and double-click run_windows.bat again. To install it by hand, run:  `"$PyExe`" -m pip install PyQt6"
        }
        Write-Host "PyQt6 installed."
    }

    # ---- Launch the cat ----
    Write-Step "Starting the cat..."
    $pyw = Join-Path (Split-Path $PyExe -Parent) "pythonw.exe"
    if (-not (Test-Path $pyw)) { $pyw = $PyExe }
    Start-Process -FilePath $pyw -ArgumentList '"deskcat.py"' -WorkingDirectory $ScriptDir
    Write-Host ""
    Write-Host "DeskCat is running! Look for the little white cat wandering your screen." -ForegroundColor Green
    Write-Host "Right-click the cat to quit. This window closes in a few seconds..."
    Start-Sleep -Seconds 5
    exit 0
} catch {
    Write-Host ""
    Write-Host "Something went wrong: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "If it keeps happening, deskcat.log in this folder may have more detail."
    exit 1
}
