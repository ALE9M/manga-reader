$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Stop-WithMessage([string]$Message) {
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    Write-Host ""
    Read-Host "Premi Invio per chiudere"
    exit 1
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Installazione Manga Reader" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Questa procedura installa automaticamente le dipendenze e scarica i modelli."
Write-Host "E' necessaria una connessione internet; il download complessivo puo' essere grande."
Write-Host ""

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PyLauncher) {
    Stop-WithMessage "Non trovo il launcher Python (py). Installa Python 3.11 da https://www.python.org/downloads/windows/ e seleziona 'Install launcher' durante l'installazione. Poi esegui di nuovo setup_windows.bat."
}
& py -3.11 --version
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Python 3.11 non risulta installato. Installa Python 3.11 da https://www.python.org/downloads/windows/ e poi esegui di nuovo setup_windows.bat."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/5] Creo l'ambiente Python locale..."
    & py -3.11 -m venv (Join-Path $ProjectRoot ".venv")
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Non riesco a creare l'ambiente virtuale." }
} else {
    Write-Host "[1/5] Ambiente Python gia' presente."
}

Write-Host "[2/5] Aggiorno pip..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Aggiornamento pip non riuscito. Controlla la connessione internet." }

Write-Host "[3/5] Installo PyTorch CPU e le dipendenze dell'applicazione..."
& $VenvPython -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Installazione di PyTorch non riuscita." }
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Installazione delle dipendenze base non riuscita." }
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements-detector.txt")
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Installazione delle dipendenze del detector non riuscita." }

Write-Host "[4/5] Scarico il detector manga..."
$VendorRoot = Join-Path $ProjectRoot "vendor"
$DetectorRoot = Join-Path $VendorRoot "comic-text-detector"
$Extracted = Join-Path $VendorRoot "comic-text-detector-master"
$DetectorZip = Join-Path $env:TEMP "manga-reader-comic-text-detector.zip"
New-Item -ItemType Directory -Force -Path $VendorRoot | Out-Null
if (-not (Test-Path (Join-Path $DetectorRoot "inference.py"))) {
    if (Test-Path $DetectorRoot) { Remove-Item -Recurse -Force $DetectorRoot }
    if (Test-Path $Extracted) { Remove-Item -Recurse -Force $Extracted }
    Invoke-WebRequest -Uri "https://github.com/dmMaze/comic-text-detector/archive/refs/heads/master.zip" -OutFile $DetectorZip
    # Use .NET directly instead of Expand-Archive, which can fail if the
    # Microsoft.PowerShell.Archive module cannot be loaded on some Windows installs.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($DetectorZip, $VendorRoot)
    if (-not (Test-Path (Join-Path $Extracted "inference.py"))) {
        Stop-WithMessage "Il download del repository detector non ha prodotto la struttura attesa. Controlla la connessione e riprova."
    }
    if (Test-Path $DetectorRoot) { Remove-Item -Recurse -Force $DetectorRoot }
    Move-Item -LiteralPath $Extracted -Destination $DetectorRoot
    Remove-Item -Force -ErrorAction SilentlyContinue $DetectorZip
} else {
    Write-Host "  Detector gia' presente; salto il download."
}

Write-Host "[5/5] Scarico il modello pretrained ONNX..."
$ModelsRoot = Join-Path $ProjectRoot "models"
$ModelPath = Join-Path $ModelsRoot "comictextdetector.pt.onnx"
New-Item -ItemType Directory -Force -Path $ModelsRoot | Out-Null
if (-not (Test-Path $ModelPath) -or (Get-Item $ModelPath).Length -lt 10000000) {
    Remove-Item -Force -ErrorAction SilentlyContinue $ModelPath
    Invoke-WebRequest -Uri "https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.2.1/comictextdetector.pt.onnx" -OutFile $ModelPath
    if (-not (Test-Path $ModelPath) -or (Get-Item $ModelPath).Length -lt 10000000) {
        Stop-WithMessage "Il modello non e' stato scaricato correttamente. Riprova con una connessione internet stabile."
    }
} else {
    Write-Host "  Modello gia' presente; salto il download."
}

Write-Host ""
Write-Host "Installazione completata!" -ForegroundColor Green
Write-Host "Adesso puoi avviare il programma con Avvia_Manga_Reader.bat."
Write-Host "Al primo avvio manga-ocr potrebbe scaricare il proprio modello."
Write-Host ""
Read-Host "Premi Invio per chiudere"
