# Come aggiornare / pubblicare Fantabirra

Sito online: **https://bungabunga.pythonanywhere.com**
Repo GitHub: **https://github.com/boz1977/Fantabirra**
Username PythonAnywhere: **bungabunga**

---

## 🔄 A. Aggiornamento normale (quello che usi di solito)

**1) Dal PC** (cartella `C:\Claude\Fantacalcio`) — pubblica le modifiche:
```bash
git add -A
git commit -m "descrizione della modifica"
git push
```
> Se le modifiche le ha già committate e pushate Claude, salta questo passo.

**2) Su PythonAnywhere** — scarica e riavvia:
- pythonanywhere.com → accedi
- **Consoles** → apri una **Bash** e lancia:
```bash
cd ~/Fantabirra && git pull
```
- Scheda **Web** → pulsante verde **Reload**

✅ Le modifiche sono online.

---

## ⚠️ B. Passo extra SOLO se sono cambiati Regolamento / Storico / Albo d'Oro / Curiosità

Dopo aver fatto il punto A:
- Entra nel sito come **admin**
- Menu **Storico → Gestisci Storico** → premi **"Carica dati dal Regolamento"**

(Per le normali modifiche al codice NON serve.)

---

## 🗓️ C. Ogni ~mese (piano gratuito)

PythonAnywhere disattiva i siti gratuiti se non accedi:
- Scheda **Web** → premi **"Run until 1 month from today"**
- (Ti avvisano via email una settimana prima della scadenza.)

---

## 🆕 D. Prima installazione da zero (solo se serve rifare tutto)

1. Account gratuito su pythonanywhere.com (Beginner).
2. Console **Bash**:
   ```bash
   git clone https://github.com/boz1977/Fantabirra.git
   pip3.10 install --user -r ~/Fantabirra/requirements.txt
   ```
3. Scheda **Web** → **Add a new web app** → **Manual configuration** → **Python 3.10**.
4. Apri il file WSGI `/var/www/bungabunga_pythonanywhere_com_wsgi.py`, cancella tutto e incolla:
   ```python
   import sys, os
   project_home = '/home/bungabunga/Fantabirra'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)
   os.environ.setdefault('SECRET_KEY', 'metti-una-stringa-casuale-lunga')
   from app import app as application, init_db
   init_db()
   ```
5. Sezione **Static files**: URL `/static/` → Directory `/home/bungabunga/Fantabirra/static`
6. **Reload** → apri il sito (admin / admin123 → cambia subito la password).

---

## Promemoria rapido

Il 90% delle volte bastano:
```bash
cd ~/Fantabirra && git pull
```
poi **Web → Reload**.
