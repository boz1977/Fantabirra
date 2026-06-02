# Pubblicare Fantabirra online (gratis)

## Opzione consigliata: PythonAnywhere (gratis, dati persistenti)

### 1. Crea l'account
- Vai su https://www.pythonanywhere.com → **Pricing & signup** → **Create a Beginner account** (gratis).

### 2. Carica il progetto
Due modi:

**A) Da GitHub (consigliato)**
1. Metti il progetto su GitHub (vedi sotto).
2. Su PythonAnywhere apri una **Bash console** (scheda *Consoles*) e clona:
   ```
   git clone https://github.com/TUO-UTENTE/Fantacalcio.git
   ```

**B) Caricamento manuale (senza GitHub)**
1. Scheda *Files* → crea la cartella `Fantacalcio`.
2. Carica `app.py`, `seed_history.py`, `requirements.txt`, e le cartelle `templates/`, `static/`, `Documenti/`.
   (Per le cartelle conviene caricare uno zip e scompattarlo da console: `unzip Fantacalcio.zip`.)
3. NON caricare `fantabirra.db` se vuoi partire pulito (verrà creato al primo avvio). Caricalo solo se
   vuoi portare i dati attuali.

### 3. Installa le dipendenze
Nella **Bash console**:
```
pip3.10 install --user -r ~/Fantacalcio/requirements.txt
```
(Flask, pandas e openpyxl sono spesso già presenti; il comando installa ciò che manca.)

### 4. Crea la Web App
1. Scheda **Web** → **Add a new web app** → **Manual configuration** → scegli Python (es. 3.10).
2. Cliccando crea un file WSGI: aprilo (link nella sezione *Code*) e **sostituisci tutto** con il contenuto
   di `wsgi_pythonanywhere.py` (in questo progetto), cambiando:
   - `USER` → il tuo username PythonAnywhere
   - la `SECRET_KEY` con una stringa lunga e casuale
3. Nella sezione *Virtualenv* puoi lasciare vuoto (usa i pacchetti installati con `--user`).
4. (Static files) opzionale ma consigliato: aggiungi mapping
   - URL: `/static/`  →  Directory: `/home/USER/Fantacalcio/static`
5. Premi **Reload** (pulsante verde in alto).

### 5. Apri il sito
`https://USER.pythonanywhere.com` → login admin: **admin / admin123**
➡️ **Cambia subito la password admin** e crea i 12 utenti dalla sezione Utenti.

### 6. Aggiornamenti futuri
Dopo ogni modifica: aggiorna i file (git pull o upload) e premi **Reload** nella scheda Web.

---

## Mettere il progetto su GitHub (per l'opzione A)
Dal tuo PC, nella cartella del progetto:
```
git init
git add .
git commit -m "Fantabirra"
```
Crea un repo vuoto su github.com, poi:
```
git remote add origin https://github.com/TUO-UTENTE/Fantacalcio.git
git branch -M main
git push -u origin main
```
> Suggerimento: aggiungi un file `.gitignore` con `__pycache__/`, `*.pyc`, `fantabirra.db`, `Documenti/_regolamento*.txt`
> se non vuoi versionare il database e i file temporanei.

---

## Alternative (note)
- **Render.com** (free): facile, ma il filesystem è *effimero* → il database SQLite si azzera a ogni
  riavvio/deploy. Andrebbe usato un database esterno (es. Postgres). Più lavoro.
- **Fly.io** (free allowance): funziona ma richiede un *volume* per SQLite e configurazione Docker. Più complesso.
- **PythonAnywhere**: scelta più semplice per Flask + SQLite con dati che restano. ✅

## Note di produzione
- La `SECRET_KEY` deve essere impostata via variabile d'ambiente (lo fa il file WSGI). Non usare quella di default.
- Su PythonAnywhere NON si usa `app.run()`: l'app viene servita dal loro server WSGI (il blocco
  `if __name__ == '__main__'` resta solo per l'esecuzione locale).
- La conversione del regolamento `.doc` (Word) è solo locale/Windows: in produzione si usa il testo già
  convertito in `Documenti/_regolamento_utf8.txt` (caricalo se vuoi usare "Carica dati dal Regolamento").
