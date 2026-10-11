# Manga Reader — Japanese Manga OCR

Applicazione desktop Python per individuare automaticamente blocchi di testo nelle pagine manga, riconoscere il giapponese con [`manga-ocr`](https://github.com/kha-white/manga_ocr), correggere le trascrizioni e ordinarle manualmente prima dell'esportazione.

> **Stato:** MVP in sviluppo. Il rilevamento automatico usa l'API di `comic-text-detector` quando il repository upstream, le dipendenze e il checkpoint sono installati. Il risultato va sempre verificato: il detector trova blocchi/linee di testo, non garantisce di ricostruire con precisione il contorno di ogni balloon.

## Funzionalità

- Apertura di pagine PNG, JPG/JPEG, WebP, BMP e TIFF.
- **Rilevamento automatico dei blocchi di testo** con [`dmMaze/comic-text-detector`](https://github.com/dmMaze/comic-text-detector).
- Ordine iniziale suggerito dall'alto verso il basso e da destra verso sinistra nelle posizioni simili; l'utente può correggerlo trascinando le voci o usando **Su/Giù**.
- Creazione manuale di regioni con trascinamento sulla pagina; `Maiusc` + trascinamento permette riquadri sovrapposti.
- OCR di una regione o di tutte le regioni tramite `manga-ocr`, eseguito in background.
- Modifica manuale del testo giapponese riconosciuto.
- Identificazione nell'elenco delle regioni generate automaticamente (`AUTO`) e disegnate dall'utente (`MANUALE`).
- Esportazione del testo in un file `.txt` UTF-8 secondo l'ordine corrente; le regioni vuote vengono ignorate.
- La cartella del detector e il percorso del modello vengono ricordati tra gli avvii.

## Installazione su Windows

È consigliato Python 3.11 in un ambiente virtuale. I modelli AI richiedono spazio su disco; il primo avvio di `manga-ocr` può scaricare il proprio modello.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Abilitare il rilevamento automatico

`comic-text-detector` è un repository separato, non un pacchetto pip con API stabile. Il progetto upstream espone `TextDetector` in `inference.py`, che restituisce blocchi (`TextBlock`) con coordinate `xyxy`; Manga Reader usa queste coordinate per creare le regioni selezionabili. Il detector e i suoi pesi non sono inclusi in questo repository.

1. Clona il codice upstream, ad esempio in `C:\AI\comic-text-detector`:

   ```powershell
   git clone https://github.com/dmMaze/comic-text-detector.git C:\AI\comic-text-detector
   ```

2. Installa PyTorch e TorchVision per la tua configurazione (CPU/GPU) usando il selettore ufficiale: <https://pytorch.org/get-started/locally/>. Poi installa le dipendenze aggiuntive nello stesso ambiente virtuale di Manga Reader:

   ```powershell
   pip install -r requirements-detector.txt
   ```

   Il codice upstream importa moduli come PyTorch, OpenCV, Shapely e `torchsummary`. Se una dipendenza manca, controlla anche il README e `requirements.txt` upstream. La compatibilità dipende dalla versione di Python, PyTorch e OpenCV.

3. Scarica un modello pretrained dalla release indicata dal progetto upstream. È consigliata la variante ONNX per evitare il caricamento diretto di checkpoint PyTorch:

   - [Modello ONNX `comictextdetector.pt.onnx` (~90 MB)](https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.2.1/comictextdetector.pt.onnx)
   - [Alternativa PyTorch `comictextdetector.pt` (~76 MB)](https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.2.1/comictextdetector.pt)

   Salva il file dove preferisci, ad esempio in `C:\AI\models\comictextdetector.pt.onnx`. Non aggiungere i pesi al repository Git: sono file grandi e artefatti di terze parti.

4. Avvia Manga Reader, apri una pagina, poi premi **Rileva aree testo…**. Seleziona la cartella che contiene `inference.py` e il checkpoint scaricato. Questi percorsi vengono salvati nelle impostazioni locali.
5. Rivedi le regioni rilevate: elimina falsi positivi, disegna a mano le aree mancanti e riordina le voci per correggere l'ordine di lettura. Quindi premi **OCR di tutte le regioni**, verifica il giapponese e usa **Esporta .txt**.

Il rilevamento viene eseguito in un thread separato per non bloccare la finestra. Il primo caricamento del modello può richiedere tempo. Se il detector fallisce, l'applicazione visualizza un messaggio e consente di tornare alla delimitazione manuale.

### Perché `comic-text-detector`?

Il progetto è stato sviluppato per manga e fumetti e punta a individuare bounding box, linee di testo e maschere. È quindi più adatto di una semplice sogliatura OpenCV come detector principale. Le coordinate qui usate sono quelle dei blocchi di testo restituiti dal modello: non sono necessariamente i contorni geometrici dei balloon, e più balloon possono essere segmentati o raggruppati in modo imperfetto. La revisione e il riordino manuali fanno parte del workflow previsto.

## Test

```powershell
pip install -r requirements-dev.txt
pytest -q
```

I test unitari non scaricano i modelli OCR/detector e non eseguono inferenza.

## Struttura del progetto

```text
manga-reader/
├── main.py
├── manga_reader/
│   ├── app.py                 # GUI e workflow
│   ├── canvas.py              # Visualizzazione e selezione delle regioni
│   ├── detection.py           # Adapter per comic-text-detector e normalizzazione box
│   ├── detection_worker.py    # Inferenza in background
│   ├── export.py              # Esportazione UTF-8
│   ├── models.py              # Modello dati delle regioni
│   └── ocr_worker.py          # OCR in background
├── tests/
├── requirements.txt
├── requirements-detector.txt
└── README.md
```

## Limiti noti

- Il detector produce blocchi di testo, non l'ordine narrativo definitivo e non sempre balloon completi.
- L'ordine iniziale è un suggerimento spaziale. Il lettore deve verificare l'ordine tipico manga da destra verso sinistra e dall'alto verso il basso, adattandolo alla pagina.
- Il riconoscimento può sbagliare furigana, caratteri stilizzati, vertical writing o onomatopee; controllare la trascrizione prima dell'esportazione.
- Il detector non è impacchettato come dipendenza pip stabile; l'adapter usa l'API `TextDetector` del repository upstream e può richiedere aggiornamenti se upstream cambia.
- L'app gestisce una pagina per volta e non salva ancora un progetto riapribile con regioni e trascrizioni.

## Dipendenze e licenze

Il codice originale di Manga Reader è rilasciato sotto licenza MIT (vedi [`LICENSE`](LICENSE)). `manga-ocr` e `comic-text-detector` sono progetti indipendenti con licenze proprie; il repository upstream `comic-text-detector` dichiara GPL-3.0. Prima di ridistribuire un'applicazione integrata o un pacchetto binario, verifica gli obblighi delle licenze e mantieni gli avvisi delle dipendenze. Il codice e i pesi di terze parti non sono copiati in questo repository.
