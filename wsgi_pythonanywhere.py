# WSGI per PythonAnywhere.
# Su PythonAnywhere, nella scheda "Web", apri il file WSGI indicato e incolla questo contenuto,
# correggendo USER e il percorso del progetto.

import sys, os

# 1) percorso della cartella del progetto (dove sta app.py)
project_home = '/home/USER/Fantacalcio'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 2) chiave segreta robusta (NON lasciare quella di default in produzione)
os.environ.setdefault('SECRET_KEY', 'CAMBIA-QUESTA-CON-UNA-STRINGA-CASUALE-LUNGA')

# 3) importa l'app e inizializza il database (crea le tabelle se non esistono)
from app import app as application, init_db
init_db()
