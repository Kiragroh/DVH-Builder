# DVH Builder Web App

Eine Webanwendung zur Visualisierung von Dosis-Volumen-Histogrammen (DVH) aus DICOM-RT Daten.

## Features

- Upload von DICOM-RT Dateien (RTSTRUCT und RTDOSE)
- Automatische DVH-Berechnung für alle Strukturen
- Interaktive DVH-Visualisierung mit Plotly
- Strukturauswahl über Checkboxen
- Excel-Export der ausgewählten DVH-Daten

## Installation

1. Stellen Sie sicher, dass Python 3.7+ installiert ist
2. Klonen Sie dieses Repository
3. Installieren Sie die erforderlichen Pakete:

```bash
pip install -r requirements.txt
```

## Verwendung

1. Starten Sie die Anwendung:
```bash
python app.py
```

2. Öffnen Sie einen Webbrowser und navigieren Sie zu `http://localhost:5000`

3. Laden Sie Ihre DICOM-RT Dateien hoch:
   - Wählen Sie die RTDOSE-Datei
   - Wählen Sie die RTSTRUCT-Datei
   - Klicken Sie auf "Hochladen"

4. Interagieren Sie mit dem DVH:
   - Wählen Sie Strukturen über die Checkboxen aus/ab
   - Exportieren Sie die ausgewählten DVH-Daten als Excel-Datei

## Technische Details

- Backend: Flask (Python)
- Frontend: HTML, JavaScript, Bootstrap
- DVH-Berechnung: dicompyler-core
- Visualisierung: Plotly.js
- Datenverarbeitung: NumPy, Pandas
