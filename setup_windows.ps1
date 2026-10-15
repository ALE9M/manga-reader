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

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Installazione Manga Reader" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Richiesto Python 3.11 a 64 bit."
Write-Host "Il rilevamento usa Manga-Bubble-YOLO ONNX; PyTorch resta necessario per manga-ocr."
Write-Host ""

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PyLauncher) {
    Stop-WithMessage "Non trovo il launcher Python (py). Installa Python 3.11 a 64 bit da https://www.python.org/downloads/windows/ e seleziona 'Install launcher'."
}
& py -3.11 --version
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Python 3.11 non risulta installato. Installa Python 3.11 a 64 bit e poi esegui di nuovo setup_windows.bat."
}
$PythonBits = (& py -3.11 -c "import struct; print(struct.calcsize('P') * 8)") -join ""
if ($PythonBits.Trim() -ne "64") {
    Stop-WithMessage "È installato Python 3.11 a 32 bit. Manga Reader richiede Python 3.11 a 64 bit."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/4] Creo l'ambiente virtuale Python..."
    & py -3.11 -m venv (Join-Path $ProjectRoot ".venv")
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Non riesco a creare l'ambiente virtuale." }
} else {
    Write-Host "[1/4] Ambiente virtuale gia' presente."
    & $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "L'ambiente .venv esistente non usa Python 3.11. Elimina la cartella .venv e riesegui setup_windows.bat."
    }
}

Write-Host ""
Write-Host "[2/4] Installo le dipendenze con versioni compatibili..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Aggiornamento di pip non riuscito." }

# Remove stale OpenCV versions previously pulled in by comic-text-detector.
# The new ONNX detector does not use OpenCV, and OpenCV 5 requires NumPy 2.x.
& $VenvPython -m pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python opencv-contrib-python-headless

Write-Host "  Installo PyTorch CPU per manga-ocr..."
& $VenvPython -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Installazione di PyTorch CPU non riuscita." }

& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Installazione delle dipendenze di Manga Reader non riuscita." }
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements-detector.txt")
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Installazione delle dipendenze ONNX non riuscita." }

Write-Host "  Controllo la coerenza delle dipendenze..."
& $VenvPython -m pip check
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Sono presenti conflitti tra pacchetti. Copia il messaggio pip check per poterli correggere." }

& $VenvPython -c "import numpy, onnxruntime, torch, PySide6; from manga_ocr import MangaOcr; print('NumPy', numpy.__version__, '| ONNX Runtime', onnxruntime.__version__, '| PyTorch', torch.__version__)"
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Una o piu' librerie non si importano correttamente. Copia il messaggio di errore per la diagnosi." }

Write-Host ""
Write-Host "[3/4] Scarico il modello Manga-Bubble-YOLO (ONNX)..."
$ModelsRoot = Join-Path $ProjectRoot "models"
$ModelPath = Join-Path $ModelsRoot "yolo26n.onnx"
$ModelUrl = "https://huggingface.co/Kiuyha/Manga-Bubble-YOLO/resolve/fb646500455e8a8a3a807fd27b855c8e4fc63766/onnx/yolo26n.onnx?download=true"
New-Item -ItemType Directory -Force -Path $ModelsRoot | Out-Null
if (-not (Test-Path $ModelPath) -or (Get-Item $ModelPath).Length -lt 1000000) {
    Remove-Item -Force -ErrorAction SilentlyContinue $ModelPath
    try {
        Invoke-WebRequest -Uri $ModelUrl -OutFile $ModelPath -UseBasicParsing
    } catch {
        Remove-Item -Force -ErrorAction SilentlyContinue $ModelPath
        Stop-WithMessage "Download del modello non riuscito. Controlla la connessione e riprova. Dettaglio: $($_.Exception.Message)"
    }
}
if (-not (Test-Path $ModelPath) -or (Get-Item $ModelPath).Length -lt 1000000) {
    Stop-WithMessage "Il modello scaricato e' incompleto o non valido. Riprova con una connessione internet stabile."
}

Write-Host "  Verifico che ONNX Runtime riesca a caricare il modello..."
$ModelPathForPython = $ModelPath.Replace("\", "\\")
& $VenvPython -c "import onnxruntime as ort; ort.InferenceSession(r'$ModelPathForPython', providers=['CPUExecutionProvider']); print('Modello ONNX verificato')"
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Il file del modello non e' caricabile. Riprova il download o segnala l'errore." }

Write-Host ""
Write-Host "[4/4] Installazione completata!" -ForegroundColor Green
Write-Host "Avvia Manga Reader con Avvia_Manga_Reader.bat."
Write-Host "Il modello OCR di manga-ocr potrebbe essere scaricato al primo utilizzo."
Write-Host ""
Read-Host "Premi Invio per chiudere"
