# Manga Reader — Japanese Manga OCR

Applicazione desktop Python per rilevare automaticamente le regioni di testo nelle pagine manga, riconoscere il giapponese con [`manga-ocr`](https://github.com/kha-white/manga-ocr), correggere le trascrizioni e ordinarle manualmente prima dell'esportazione.

Il rilevamento automatico usa [Manga-Bubble-YOLO](https://huggingface.co/Kiuyha/Manga-Bubble-YOLO), modello YOLO26-Nano distribuito in formato ONNX. Il modello trova regioni di testo: non garantisce di ricostruire il contorno esatto di ogni balloon. La revisione manuale resta disponibile.

## Funzionalità

- Apertura di pagine PNG, JPG/JPEG, WebP, BMP e TIFF.
- **Rilevamento automatico delle regioni di testo** tramite Manga-Bubble-YOLO e ONNX Runtime CPU.
- Ordine iniziale suggerito dall'alto verso il basso e da destra verso sinistra; l'utente può correggerlo trascinando le voci o usando **Su/Giù**.
- Creazione manuale di regioni con trascinamento sulla pagina; `Maiusc` + trascinamento permette riquadri sovrapposti.
- OCR di una regione o di tutte le regioni tramite `manga-ocr`, eseguito in background.
- Modifica manuale del testo giapponese riconosciuto.
- Identificazione nell'elenco delle regioni generate automaticamente (`AUTO`) e disegnate dall'utente (`MANUALE`).
- Esportazione del testo in un file `.txt` UTF-8 secondo l'ordine corrente; le regioni vuote vengono ignorate.

## Installazione semplice (Windows)

È consigliato **Python 3.11 a 64 bit**, installato da [python.org](https://www.python.org/downloads/windows/). Durante l'installazione lascia attivo il Python Launcher.

1. Scarica questo repository con **Code → Download ZIP** e decomprimi la cartella.
2. Fai doppio clic su `setup_windows.bat`.
3. Attendi che lo script installi le librerie, verifichi le dipendenze e scarichi il modello ONNX.
4. Avvia il programma con `Avvia_Manga_Reader.bat`.
5. Apri una pagina e premi **Rileva aree testo…**. Il modello viene letto automaticamente da `models/yolo26n.onnx`.

La prima installazione richiede una connessione internet. PyTorch CPU viene installato per `manga-ocr`; il rilevatore, invece, usa ONNX Runtime e **non dipende da PyTorch o OpenCV per l'inferenza**. Il modello di rilevamento pesa circa 6 MB. Al primo utilizzo, `manga-ocr` scarica anche il proprio modello OCR (circa 400 MB). Le pagine manga restano sul computer e non vengono inviate a un servizio web.

### Compatibilità delle dipendenze

Lo script usa un ambiente virtuale locale `.venv` e controlla i pacchetti al termine dell'installazione.

- Python 3.11 a 64 bit è la versione di riferimento per limitare problemi con le librerie native PyTorch su Windows.
- NumPy è fissato a `1.26.4` e ONNX Runtime a `1.20.1`, combinazione compatibile con l'inferenza ONNX su Python 3.11.
- OpenCV è stato rimosso dal rilevatore. Questo evita il conflitto visto con OpenCV 5, che richiede NumPy 2.x mentre il codice del vecchio detector utilizzava l'attributo rimosso `numpy.bool8`.
- `manga-ocr` resta fissato a `0.1.16`; la versione di Transformers è limitata alla serie principale 4.x/5.x per ridurre il rischio di rotture dovute a una futura major release.
- Lo script esegue `pip check` e prova a importare le librerie principali, quindi controlla che il modello ONNX possa essere caricato.

Se riutilizzi una cartella di progetto già installata, lo script rimuove le vecchie varianti di OpenCV installate dal detector precedente. Se l'ambiente `.venv` esistente non usa Python 3.11, elimina quella cartella e riesegui `setup_windows.bat`.

### Installazione manuale / sviluppatori

Da PowerShell, nella cartella del progetto:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
pip install -r requirements-detector.txt
```

Scarica il modello ONNX nella cartella `models`:

[`yolo26n.onnx` — modello Manga-Bubble-YOLO](https://huggingface.co/Kiuyha/Manga-Bubble-YOLO/resolve/fb646500455e8a8a3a807fd27b855c8e4fc63766/onnx/yolo26n.onnx?download=true)

Il nome e il percorso attesi sono `models/yolo26n.onnx`. Poi avvia:

```powershell
python main.py
```

## Rilevamento automatico: note e limiti

Manga Reader usa l'export ONNX di [Kiuyha/Manga-Bubble-YOLO](https://huggingface.co/Kiuyha/Manga-Bubble-YOLO). Il modello è addestrato su pagine manga inglesi, vietnamite e giapponesi e la scheda del modello indica una dimensione d'ingresso di 1280 × 1280. Manga Reader adatta le coordinate dei riquadri alle dimensioni originali della pagina.

Per favorire il richiamo, la soglia iniziale di confidenza è 0,25. Una soglia più bassa può includere più testi piccoli ma anche falsi positivi; una soglia più alta può ridurre regioni spurie ma perdere alcuni testi. In ogni caso, controlla i riquadri prima di eseguire l'OCR.

Limiti noti:

- Il rilevatore restituisce riquadri di regioni di testo, non necessariamente il contorno del balloon completo.
- Furigana, onomatopee, testo decorativo, caratteri molto piccoli o balloon sovrapposti possono essere rilevati in modo imperfetto.
- L'ordine di lettura iniziale è un suggerimento spaziale; va rivisto per ogni pagina.
- L'OCR può sbagliare caratteri stilizzati. Correggi le trascrizioni prima di esportare.
- Le immagini vengono elaborate localmente. Il download del modello richiede internet durante l'installazione, ma l'inferenza non invia la pagina a un servizio remoto.

## Test

```powershell
pip install -r requirements-dev.txt
pytest -q
```

I test unitari verificano la normalizzazione delle coordinate e il parsing dell'output YOLO26. Non scaricano il modello né eseguono inferenza su immagini reali.

## Struttura del progetto

```text
manga-reader/
├── main.py
├── manga_reader/
│   ├── app.py                 # GUI e workflow
│   ├── canvas.py              # Visualizzazione e selezione delle regioni
│   ├── detection.py           # Adapter ONNX per Manga-Bubble-YOLO
│   ├── detection_worker.py    # Inferenza in background
│   ├── export.py              # Esportazione UTF-8
│   ├── models.py              # Modello dati delle regioni
│   └── ocr_worker.py          # OCR in background
├── models/                    # Modello ONNX scaricato dall'installer
├── tests/
├── requirements.txt
├── requirements-detector.txt
└── README.md
```

## Dipendenze e licenze

Il codice originale di Manga Reader è rilasciato sotto licenza MIT (vedi [`LICENSE`](LICENSE)). [Manga-Bubble-YOLO](https://huggingface.co/Kiuyha/Manga-Bubble-YOLO) è pubblicato con licenza Apache-2.0. `manga-ocr`, PyTorch e ONNX Runtime sono progetti indipendenti con licenze proprie. Prima di ridistribuire un'applicazione integrata o un pacchetto binario, verifica gli obblighi delle licenze e mantieni gli avvisi delle dipendenze. Il codice del modello e i pesi non sono copiati nel repository: il setup scarica i pesi dal repository upstream alla versione fissata nello script.
