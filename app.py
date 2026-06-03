from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import sqlite3
import os
import json
import random

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fantabirra-secret-key-2025-change-in-prod')

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fantabirra.db')


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db

def query_db(query, args=(), one=False):
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    db.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    lid = cur.lastrowid
    db.close()
    return lid

def get_setting(key, default=None):
    row = query_db("SELECT value FROM settings WHERE key=?", [key], one=True)
    return row['value'] if row else default

def set_setting(key, value):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", [key, str(value)])
    db.commit()
    db.close()


def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            team_name TEXT NOT NULL,
            budget INTEGER DEFAULT 500,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            team TEXT NOT NULL,
            base_value INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS nominations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (player_id) REFERENCES players(id),
            UNIQUE(user_id, player_id)
        );
        CREATE TABLE IF NOT EXISTS auction_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            opened_at TEXT,
            closed_at TEXT,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS auction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            winner_id INTEGER,
            final_price INTEGER,
            FOREIGN KEY (session_id) REFERENCES auction_sessions(id),
            FOREIGN KEY (player_id) REFERENCES players(id),
            FOREIGN KEY (winner_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_item_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (auction_item_id) REFERENCES auction_items(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(auction_item_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS acquisitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            session_name TEXT,
            acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (player_id) REFERENCES players(id)
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS history_seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            champion TEXT,
            champion_team TEXT,
            champion_cup TEXT,
            champion_cup_team TEXT,
            note TEXT
        );
        CREATE TABLE IF NOT EXISTS history_standings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_id INTEGER NOT NULL,
            position INTEGER,
            team TEXT,
            presidente TEXT,
            points INTEGER,
            FOREIGN KEY (season_id) REFERENCES history_seasons(id)
        );
        CREATE TABLE IF NOT EXISTS curiosita (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            value TEXT,
            detail TEXT,
            sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS user_strategy (
            user_id INTEGER PRIMARY KEY,
            plan_P INTEGER DEFAULT 0,
            plan_D INTEGER DEFAULT 0,
            plan_C INTEGER DEFAULT 0,
            plan_A INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS player_targets (
            user_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            target_price INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, player_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (player_id) REFERENCES players(id)
        );
        CREATE TABLE IF NOT EXISTS item_renounces (
            item_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (item_id, user_id),
            FOREIGN KEY (item_id) REFERENCES auction_items(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS free_phase (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'choosing',     -- choosing | bidding | done
            role TEXT,                          -- reparto della fase (P/D/C/A)
            turn_order TEXT,                    -- JSON list di user_id
            turn_index INTEGER DEFAULT 0,
            current_session_id INTEGER,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    defaults = [
        ('nomination_open', '0'),
        ('max_nom_P', '5'),
        ('max_nom_D', '15'),
        ('max_nom_C', '15'),
        ('max_nom_A', '12'),
        ('initial_budget', '500'),
        ('max_players', '25'),
        ('league_name', 'Fantabirra'),
        ('tie_rule', 'first'),
        ('slots_P', '3'),
        ('slots_D', '8'),
        ('slots_C', '8'),
        ('slots_A', '6'),
    ]
    for k, v in defaults:
        db.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", [k, v])

    # Migrazione: colonne min_bid (pareggi/rilancio) e caller_id (chiamata giocatori liberi)
    cols = [r['name'] for r in db.execute("PRAGMA table_info(auction_items)").fetchall()]
    if 'min_bid' not in cols:
        db.execute("ALTER TABLE auction_items ADD COLUMN min_bid INTEGER")
    if 'caller_id' not in cols:
        db.execute("ALTER TABLE auction_items ADD COLUMN caller_id INTEGER")
    fp_cols = [r['name'] for r in db.execute("PRAGMA table_info(free_phase)").fetchall()]
    if fp_cols and 'role' not in fp_cols:
        db.execute("ALTER TABLE free_phase ADD COLUMN role TEXT")

    admin_exists = db.execute("SELECT id FROM users WHERE is_admin=1").fetchone()
    if not admin_exists:
        db.execute(
            "INSERT OR IGNORE INTO users (username,password,team_name,is_admin,budget) VALUES (?,?,?,?,?)",
            ['admin', generate_password_hash('admin123'), 'Amministratore', 1, 0]
        )

    db.commit()
    db.close()


# ── Auth decorators ────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Effettua il login per continuare.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            flash('Accesso riservato all\'amministratore.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_globals():
    return dict(
        league_name=get_setting('league_name', 'Fantabirra'),
        nomination_open=get_setting('nomination_open', '0') == '1',
        view_mode=session.get('view_mode', 'full'),
        now=datetime.now()
    )


@app.route('/view/<mode>')
def set_view(mode):
    session['view_mode'] = 'light' if mode == 'light' else 'full'
    dest = request.referrer
    if not dest or '/view/' in dest:
        dest = url_for('index')
    return redirect(dest)


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = query_db("SELECT * FROM users WHERE username=?", [username], one=True)
        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['team_name'] = user['team_name']
            session['is_admin'] = bool(user['is_admin'])
            flash(f'Benvenuto, {user["team_name"]}!', 'success')
            return redirect(url_for('admin_dashboard' if user['is_admin'] else 'dashboard'))
        flash('Username o password non validi.', 'danger')
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logout effettuato con successo.', 'info')
    return redirect(url_for('login'))


# ── Manager ───────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    uid = session['user_id']
    user = query_db("SELECT * FROM users WHERE id=?", [uid], one=True)

    my_players = query_db("""
        SELECT a.price, p.role, p.name, p.team, p.base_value
        FROM acquisitions a JOIN players p ON p.id=a.player_id
        WHERE a.user_id=? ORDER BY p.role, p.name
    """, [uid])

    role_counts = {}
    for p in my_players:
        role_counts[p['role']] = role_counts.get(p['role'], 0) + 1

    active_sessions = query_db("""
        SELECT s.id, s.name, s.status, s.opened_at,
               COUNT(DISTINCT ai.id) as total_items,
               COUNT(DISTINCT b.id) as my_bids
        FROM auction_sessions s
        JOIN auction_items ai ON ai.session_id=s.id AND ai.status='pending'
        LEFT JOIN bids b ON b.auction_item_id=ai.id AND b.user_id=?
        WHERE s.status='bidding'
        GROUP BY s.id
    """, [uid])

    my_nominations = query_db("""
        SELECT n.player_id, p.role, p.name, p.team, p.base_value
        FROM nominations n JOIN players p ON p.id=n.player_id
        WHERE n.user_id=? ORDER BY p.role, p.name
    """, [uid])

    nom_by_role = {}
    for n in my_nominations:
        nom_by_role[n['role']] = nom_by_role.get(n['role'], 0) + 1

    settings = {k: int(get_setting(k, v)) for k, v in
                [('max_nom_P','5'),('max_nom_D','15'),('max_nom_C','15'),('max_nom_A','12')]}

    return render_template('manager/dashboard.html',
        user=user, my_players=my_players, role_counts=role_counts,
        active_sessions=active_sessions, my_nominations=my_nominations,
        nom_by_role=nom_by_role, settings=settings)


@app.route('/nominations')
@login_required
def nominations():
    if session.get('is_admin'):
        return redirect(url_for('admin_nominations'))
    uid = session['user_id']
    nomination_open = get_setting('nomination_open', '0') == '1'

    settings = {k: int(get_setting(k, v)) for k, v in
                [('max_nom_P','5'),('max_nom_D','15'),('max_nom_C','15'),('max_nom_A','12')]}

    my_noms = query_db("""
        SELECT n.player_id, p.role, p.name, p.team, p.base_value
        FROM nominations n JOIN players p ON p.id=n.player_id
        WHERE n.user_id=? ORDER BY p.role, p.name
    """, [uid])
    my_nom_ids = {n['player_id'] for n in my_noms}
    nom_by_role = {}
    for n in my_noms:
        nom_by_role[n['role']] = nom_by_role.get(n['role'], 0) + 1

    role_filter = request.args.get('role', 'Tutti')
    search = request.args.get('q', '').strip()

    sql = """
        SELECT p.id, p.role, p.name, p.team, p.base_value,
               COUNT(n2.id) as nom_count
        FROM players p
        LEFT JOIN nominations n2 ON n2.player_id=p.id
    """
    params = []
    where = []
    if role_filter != 'Tutti':
        where.append("p.role=?"); params.append(role_filter)
    if search:
        where.append("(p.name LIKE ? OR p.team LIKE ?)"); params.extend([f'%{search}%', f'%{search}%'])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY p.id ORDER BY p.role, p.base_value DESC, p.name"

    players = query_db(sql, params)
    acquired_ids = {r['player_id'] for r in query_db("SELECT player_id FROM acquisitions")}
    in_session_ids = {r['player_id'] for r in query_db("""
        SELECT DISTINCT ai.player_id FROM auction_items ai
        JOIN auction_sessions s ON s.id=ai.session_id WHERE s.status IN ('pending','bidding')
    """)}

    return render_template('manager/nominations.html',
        players=players, my_noms=my_noms, my_nom_ids=my_nom_ids,
        nom_by_role=nom_by_role, acquired_ids=acquired_ids,
        in_session_ids=in_session_ids, nomination_open=nomination_open,
        settings=settings, role_filter=role_filter, search=search)


@app.route('/nominations/toggle', methods=['POST'])
@login_required
def toggle_nomination():
    if session.get('is_admin'):
        return jsonify({'error': 'Admin non può fare nomination'}), 403
    if get_setting('nomination_open', '0') != '1':
        return jsonify({'error': 'Le nomination sono chiuse'}), 403

    uid = session['user_id']
    pid = int(request.form.get('player_id', 0))
    player = query_db("SELECT * FROM players WHERE id=?", [pid], one=True)
    if not player:
        return jsonify({'error': 'Giocatore non trovato'}), 404

    role = player['role']

    def role_counts():
        rows = query_db("""
            SELECT p.role, COUNT(*) as c FROM nominations n JOIN players p ON p.id=n.player_id
            WHERE n.user_id=? GROUP BY p.role
        """, [uid])
        counts = {r['role']: r['c'] for r in rows}
        counts['total'] = sum(r['c'] for r in rows)
        return counts

    existing = query_db("SELECT id FROM nominations WHERE user_id=? AND player_id=?", [uid, pid], one=True)
    if existing:
        execute_db("DELETE FROM nominations WHERE user_id=? AND player_id=?", [uid, pid])
        return jsonify({'action': 'removed', 'role': role, 'counts': role_counts()})

    max_nom = int(get_setting(f'max_nom_{role}', '8'))
    current = query_db("""
        SELECT COUNT(*) as c FROM nominations n JOIN players p ON p.id=n.player_id
        WHERE n.user_id=? AND p.role=?
    """, [uid, role], one=True)['c']

    if current >= max_nom:
        return jsonify({'error': f'Hai già raggiunto il limite di {max_nom} nomination per il ruolo {role}'}), 400

    execute_db("INSERT OR IGNORE INTO nominations (user_id, player_id) VALUES (?,?)", [uid, pid])
    return jsonify({'action': 'added', 'role': role, 'counts': role_counts()})


# ── Import nomination da Excel ───────────────────────────────────────────────

def _normalize_name(s):
    import unicodedata
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    return ''.join(ch for ch in s.lower() if ch.isalnum())

_KNOWN_COLS = {'id', 'r', 'rm', 'nome', 'squadra', 'qt.a', 'qt.i', 'diff', 'diff.',
               'qt.a m', 'qt.i m', 'diff.m', 'fvm', 'fvm m', 'tot'}

def import_nominations_from_file(file_storage, user_id):
    """Legge un file Excel tipo 'nominations Lord Cavallo' e crea le nomination.
       Un giocatore è nominato se ha un valore in una colonna 'manager' (non standard).
       Ritorna (added, skipped_limit, not_found_list)."""
    import pandas as pd
    xls = pd.ExcelFile(file_storage)
    sheet = 'Tutti' if 'Tutti' in xls.sheet_names else xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]

    name_col = next((c for c in df.columns if c.strip().lower() == 'nome'), None)
    if not name_col:
        raise ValueError("Colonna 'Nome' non trovata nel file.")
    marker_cols = [c for c in df.columns if c.strip().lower() not in _KNOWN_COLS]
    if not marker_cols:
        raise ValueError("Nessuna colonna manager trovata (es. 'Allenatore').")

    # indice giocatori per nome normalizzato
    players = query_db("SELECT id, role, name FROM players")
    by_name = {}
    for p in players:
        by_name.setdefault(_normalize_name(p['name']), p)

    max_by_role = {r: int(get_setting(f'max_nom_{r}', '99')) for r in ['P', 'D', 'C', 'A']}
    cur_by_role = {}
    for r in query_db("""SELECT p.role, COUNT(*) c FROM nominations n JOIN players p ON p.id=n.player_id
                         WHERE n.user_id=? GROUP BY p.role""", [user_id]):
        cur_by_role[r['role']] = r['c']

    db = get_db()
    added, skipped_limit, not_found = 0, 0, []
    for _, row in df.iterrows():
        marked = any(pd.notna(row[c]) and str(row[c]).strip() not in ('', '0', 'nan')
                     for c in marker_cols)
        if not marked:
            continue
        nm = _normalize_name(row[name_col])
        player = by_name.get(nm)
        if not player:
            not_found.append(str(row[name_col]))
            continue
        role = player['role']
        if cur_by_role.get(role, 0) >= max_by_role.get(role, 99):
            skipped_limit += 1
            continue
        cur = db.execute("INSERT OR IGNORE INTO nominations (user_id, player_id) VALUES (?,?)",
                         [user_id, player['id']])
        if cur.rowcount:
            added += 1
            cur_by_role[role] = cur_by_role.get(role, 0) + 1
    db.commit()
    db.close()
    return added, skipped_limit, not_found


@app.route('/nominations/import', methods=['POST'])
@login_required
def import_nominations():
    if session.get('is_admin'):
        return redirect(url_for('admin_nominations'))
    if get_setting('nomination_open', '0') != '1':
        flash('Le nomination sono chiuse: non puoi importare.', 'warning')
        return redirect(url_for('nominations'))
    f = request.files.get('file')
    if not f or not f.filename:
        flash('Nessun file selezionato.', 'danger')
        return redirect(url_for('nominations'))
    try:
        added, skipped, not_found = import_nominations_from_file(f, session['user_id'])
        msg = f'Import completato: {added} nomination aggiunte.'
        if skipped:
            msg += f' {skipped} ignorate (limite ruolo raggiunto).'
        if not_found:
            msg += f' {len(not_found)} non trovate in lista: {", ".join(not_found[:8])}{"…" if len(not_found) > 8 else ""}.'
        flash(msg, 'success' if added else 'warning')
    except Exception as e:
        flash(f'Errore durante l\'import: {e}', 'danger')
    return redirect(url_for('nominations'))


@app.route('/admin/nominations/import', methods=['POST'])
@admin_required
def admin_import_nominations():
    uid = request.form.get('user_id')
    f = request.files.get('file')
    if not uid or not uid.isdigit():
        flash('Seleziona un manager.', 'danger')
        return redirect(url_for('admin_nominations'))
    if not f or not f.filename:
        flash('Nessun file selezionato.', 'danger')
        return redirect(url_for('admin_nominations'))
    try:
        added, skipped, not_found = import_nominations_from_file(f, int(uid))
        msg = f'Import completato: {added} nomination aggiunte.'
        if skipped:
            msg += f' {skipped} ignorate (limite ruolo).'
        if not_found:
            msg += f' {len(not_found)} non trovate: {", ".join(not_found[:8])}{"…" if len(not_found) > 8 else ""}.'
        flash(msg, 'success' if added else 'warning')
    except Exception as e:
        flash(f'Errore durante l\'import: {e}', 'danger')
    return redirect(url_for('admin_nominations'))


@app.route('/auctions')
@login_required
def auctions():
    if session.get('is_admin'):
        return redirect(url_for('admin_auctions'))
    uid = session['user_id']
    user = query_db("SELECT * FROM users WHERE id=?", [uid], one=True)

    active_sessions = query_db("SELECT * FROM auction_sessions WHERE status='bidding' ORDER BY opened_at DESC")
    sessions_data = []
    for s in active_sessions:
        items = query_db("""
            SELECT ai.id, ai.player_id, ai.status, ai.min_bid, ai.caller_id,
                   p.role, p.name, p.team, p.base_value,
                   uc.team_name as caller_name,
                   (SELECT COUNT(*) FROM nominations n WHERE n.player_id=p.id) as nom_count,
                   b.amount as my_bid, b.submitted_at as my_bid_time,
                   EXISTS(SELECT 1 FROM item_renounces ir WHERE ir.item_id=ai.id AND ir.user_id=?) as my_renounce,
                   EXISTS(SELECT 1 FROM nominations n WHERE n.player_id=p.id AND n.user_id=?) as my_nominated
            FROM auction_items ai JOIN players p ON p.id=ai.player_id
            LEFT JOIN bids b ON b.auction_item_id=ai.id AND b.user_id=?
            LEFT JOIN users uc ON uc.id=ai.caller_id
            WHERE ai.session_id=? AND ai.status='pending'
            ORDER BY CASE p.role WHEN 'P' THEN 1 WHEN 'D' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
                     nom_count DESC, p.base_value DESC, p.name
        """, [uid, uid, uid, s['id']])
        sessions_data.append({'session': s, 'items': items})

    past_sessions = query_db("SELECT * FROM auction_sessions WHERE status='revealed' ORDER BY closed_at DESC LIMIT 10")
    past_data = []
    for s in past_sessions:
        items = query_db("""
            SELECT ai.status, ai.final_price,
                   p.role, p.name, p.team, p.base_value,
                   u.team_name as winner_name,
                   b.amount as my_bid
            FROM auction_items ai JOIN players p ON p.id=ai.player_id
            LEFT JOIN users u ON u.id=ai.winner_id
            LEFT JOIN bids b ON b.auction_item_id=ai.id AND b.user_id=?
            WHERE ai.session_id=?
            ORDER BY ai.status DESC, p.role, p.name
        """, [uid, s['id']])
        past_data.append({'session': s, 'items': items})

    # contesto fase liberi a turni
    ph = _active_phase()
    fp = {'active': False, 'signature': 'none'}
    if ph:
        order = json.loads(ph['turn_order'])
        cur_uid = order[ph['turn_index']] if ph['turn_index'] < len(order) else None
        cur = query_db("SELECT team_name FROM users WHERE id=?", [cur_uid], one=True) if cur_uid else None
        fp = {
            'active': True, 'status': ph['status'],
            'is_my_turn': ph['status'] == 'choosing' and cur_uid == uid,
            'turn_name': cur['team_name'] if cur else None,
            'signature': f"{ph['id']}:{ph['status']}:{ph['turn_index']}:{ph['current_session_id']}",
        }

    return render_template('manager/auctions.html',
        user=user, sessions_data=sessions_data, past_data=past_data, fp=fp)


@app.route('/auctions/bid', methods=['POST'])
@login_required
def place_bid():
    if session.get('is_admin'):
        return jsonify({'error': 'Admin non può fare offerte'}), 403

    uid = session['user_id']
    item_id = int(request.form.get('auction_item_id', 0))
    amount = request.form.get('amount', '0').strip()
    if not amount.isdigit():
        return jsonify({'error': 'Importo non valido'}), 400
    amount = int(amount)

    item = query_db("""
        SELECT ai.*, s.status as sess_status, p.base_value, p.name, p.role
        FROM auction_items ai
        JOIN auction_sessions s ON s.id=ai.session_id
        JOIN players p ON p.id=ai.player_id
        WHERE ai.id=? AND ai.status='pending'
    """, [item_id], one=True)

    if not item:
        return jsonify({'error': 'Asta non trovata o già chiusa'}), 404
    if item['sess_status'] != 'bidding':
        return jsonify({'error': 'La fase di offerte è chiusa'}), 403
    # Limite di reparto: non si può puntare su un ruolo già completato in rosa
    if not _can_take_role(uid, item['role']):
        return jsonify({'error': f'Hai già completato il reparto {item["role"]}: non puoi puntare.'}), 403
    if not item['caller_id']:
        # Solo chi ha nominato il giocatore può offrire
        nominated = query_db("SELECT 1 FROM nominations WHERE player_id=? AND user_id=?",
                             [item['player_id'], uid], one=True)
        if not nominated:
            return jsonify({'error': 'Non puoi offrire su questo giocatore: non lo hai nominato.'}), 403
    # Min: rilancio dopo pareggio (min_bid) > prezzo di costo per chiamate liberi (caller_id) > prezzo+1
    if item['min_bid']:
        min_required = item['min_bid']
    elif item['caller_id']:
        min_required = item['base_value']
    else:
        min_required = item['base_value'] + 1
    if amount < min_required:
        return jsonify({'error': f'Offerta minima: {min_required} crediti'}), 400

    user = query_db("SELECT budget FROM users WHERE id=?", [uid], one=True)
    committed = query_db("""
        SELECT COALESCE(SUM(b.amount),0) as total
        FROM bids b JOIN auction_items ai ON ai.id=b.auction_item_id
        JOIN auction_sessions s ON s.id=ai.session_id
        WHERE b.user_id=? AND s.status='bidding' AND ai.status='pending' AND b.auction_item_id!=?
    """, [uid, item_id], one=True)['total']

    available = user['budget'] - committed
    if amount > available:
        return jsonify({'error': f'Budget insufficiente. Disponibile: {available} crediti'}), 400

    db = get_db()
    db.execute("""
        INSERT INTO bids (auction_item_id, user_id, amount) VALUES (?,?,?)
        ON CONFLICT(auction_item_id, user_id) DO UPDATE SET amount=excluded.amount, submitted_at=CURRENT_TIMESTAMP
    """, [item_id, uid, amount])
    # offrire annulla un'eventuale rinuncia
    db.execute("DELETE FROM item_renounces WHERE item_id=? AND user_id=?", [item_id, uid])
    db.commit()
    db.close()
    return jsonify({'success': True, 'amount': amount})


@app.route('/auctions/renounce', methods=['POST'])
@login_required
def renounce_bid():
    if session.get('is_admin'):
        return jsonify({'error': 'Admin non può rinunciare'}), 403
    uid = session['user_id']
    item_id = int(request.form.get('auction_item_id', 0))
    item = query_db("""
        SELECT ai.id, ai.player_id, ai.caller_id, ai.session_id, s.status as sess_status FROM auction_items ai
        JOIN auction_sessions s ON s.id=ai.session_id
        WHERE ai.id=? AND ai.status='pending'
    """, [item_id], one=True)
    if not item:
        return jsonify({'error': 'Asta non trovata o già chiusa'}), 404
    if item['sess_status'] != 'bidding':
        return jsonify({'error': 'La fase di offerte è chiusa'}), 403
    if not item['caller_id']:
        nominated = query_db("SELECT 1 FROM nominations WHERE player_id=? AND user_id=?",
                             [item['player_id'], uid], one=True)
        if not nominated:
            return jsonify({'error': 'Non sei tra chi può puntare su questo giocatore.'}), 403

    db = get_db()
    existing = db.execute("SELECT 1 FROM item_renounces WHERE item_id=? AND user_id=?",
                          [item_id, uid]).fetchone()
    if existing:
        # annulla la rinuncia (torna a "in attesa")
        db.execute("DELETE FROM item_renounces WHERE item_id=? AND user_id=?", [item_id, uid])
        action = 'cancelled'
    else:
        # rinuncia: rimuove anche un'eventuale offerta
        db.execute("DELETE FROM bids WHERE auction_item_id=? AND user_id=?", [item_id, uid])
        db.execute("INSERT OR IGNORE INTO item_renounces (item_id, user_id) VALUES (?,?)", [item_id, uid])
        action = 'renounced'
    db.commit()
    db.close()
    return jsonify({'success': True, 'action': action})


@app.route('/team')
@login_required
def my_team():
    uid = session['user_id']
    user = query_db("SELECT * FROM users WHERE id=?", [uid], one=True)
    players = query_db("""
        SELECT a.price, a.session_name, p.role, p.name, p.team, p.base_value
        FROM acquisitions a JOIN players p ON p.id=a.player_id
        WHERE a.user_id=? ORDER BY p.role, p.name
    """, [uid])
    by_role = {'P': [], 'D': [], 'C': [], 'A': []}
    for p in players:
        by_role.get(p['role'], []).append(p)
    total_spent = sum(p['price'] for p in players)
    return render_template('manager/team.html',
        user=user, by_role=by_role, total_spent=total_spent, total_players=len(players))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    uid = session['user_id']
    user = query_db("SELECT * FROM users WHERE id=?", [uid], one=True)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'team_name':
            name = request.form.get('team_name', '').strip()
            if not name:
                flash('Il nome squadra non può essere vuoto.', 'danger')
            else:
                execute_db("UPDATE users SET team_name=? WHERE id=?", [name, uid])
                session['team_name'] = name
                flash('Nome squadra aggiornato.', 'success')
        elif action == 'password':
            cur = request.form.get('current_password', '')
            new = request.form.get('new_password', '')
            if not check_password_hash(user['password'], cur):
                flash('Password attuale errata.', 'danger')
            elif len(new) < 4:
                flash('La nuova password deve avere almeno 4 caratteri.', 'danger')
            else:
                execute_db("UPDATE users SET password=? WHERE id=?", [generate_password_hash(new), uid])
                flash('Password aggiornata.', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)


# ── Strategia manager ────────────────────────────────────────────────────────

@app.route('/strategia')
@login_required
def strategia():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    uid = session['user_id']
    user = query_db("SELECT * FROM users WHERE id=?", [uid], one=True)

    roles = ['P', 'D', 'C', 'A']
    slots = {r: int(get_setting(f'slots_{r}', '0')) for r in roles}
    plan_row = query_db("SELECT * FROM user_strategy WHERE user_id=?", [uid], one=True)
    plan = {r: (plan_row[f'plan_{r}'] if plan_row else 0) for r in roles}

    acq = query_db("""
        SELECT p.role, COUNT(*) as n, COALESCE(SUM(a.price),0) as spent
        FROM acquisitions a JOIN players p ON p.id=a.player_id
        WHERE a.user_id=? GROUP BY p.role
    """, [uid])
    filled = {r: 0 for r in roles}
    spent = {r: 0 for r in roles}
    for a in acq:
        filled[a['role']] = a['n']
        spent[a['role']] = a['spent']

    total_spent = sum(spent.values())
    total_budget = user['budget'] + total_spent  # budget iniziale residuo + speso = iniziale
    label = {'P': 'Portieri', 'D': 'Difensori', 'C': 'Centrocampisti', 'A': 'Attaccanti'}

    reparti = []
    for r in roles:
        slots_left = max(slots[r] - filled[r], 0)
        plan_left = max(plan[r] - spent[r], 0)
        reparti.append({
            'role': r, 'label': label[r], 'slots': slots[r], 'filled': filled[r],
            'slots_left': slots_left, 'plan': plan[r], 'spent': spent[r],
            'plan_left': plan_left,
            'avg_left': round(plan_left / slots_left, 1) if slots_left else 0,
        })

    # nomination dell'utente con prezzo pianificato
    targets = {t['player_id']: t['target_price'] for t in
               query_db("SELECT player_id, target_price FROM player_targets WHERE user_id=?", [uid])}
    noms = query_db("""
        SELECT p.id, p.role, p.name, p.team, p.base_value
        FROM nominations n JOIN players p ON p.id=n.player_id
        WHERE n.user_id=? ORDER BY p.role, p.base_value DESC, p.name
    """, [uid])
    noms_by_role = {r: [] for r in roles}
    target_tot = {r: 0 for r in roles}
    for n in noms:
        t = targets.get(n['id'], 0)
        noms_by_role[n['role']].append({**dict(n), 'target': t})
        target_tot[n['role']] += t

    return render_template('manager/strategia.html',
        user=user, reparti=reparti, total_budget=total_budget, total_spent=total_spent,
        total_plan=sum(plan.values()), noms_by_role=noms_by_role, target_tot=target_tot,
        label=label, roles=roles)


@app.route('/strategia/budget', methods=['POST'])
@login_required
def save_strategy_budget():
    if session.get('is_admin'):
        return jsonify({'error': 'non disponibile'}), 403
    uid = session['user_id']
    vals = {}
    for r in ['P', 'D', 'C', 'A']:
        v = request.form.get(f'plan_{r}', '0').strip()
        vals[r] = int(v) if v.isdigit() else 0
    db = get_db()
    db.execute("""
        INSERT INTO user_strategy (user_id, plan_P, plan_D, plan_C, plan_A) VALUES (?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET plan_P=excluded.plan_P, plan_D=excluded.plan_D,
            plan_C=excluded.plan_C, plan_A=excluded.plan_A
    """, [uid, vals['P'], vals['D'], vals['C'], vals['A']])
    db.commit()
    db.close()
    flash('Piano budget salvato.', 'success')
    return redirect(url_for('strategia'))


@app.route('/strategia/target', methods=['POST'])
@login_required
def save_target():
    if session.get('is_admin'):
        return jsonify({'error': 'non disponibile'}), 403
    uid = session['user_id']
    pid = request.form.get('player_id', '')
    price = request.form.get('target_price', '0').strip()
    if not pid.isdigit():
        return jsonify({'error': 'giocatore non valido'}), 400
    price = int(price) if price.isdigit() else 0
    db = get_db()
    if price > 0:
        db.execute("""
            INSERT INTO player_targets (user_id, player_id, target_price) VALUES (?,?,?)
            ON CONFLICT(user_id, player_id) DO UPDATE SET target_price=excluded.target_price
        """, [uid, int(pid), price])
    else:
        db.execute("DELETE FROM player_targets WHERE user_id=? AND player_id=?", [uid, int(pid)])
    db.commit()
    db.close()
    return jsonify({'success': True, 'target': price})


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = {
        'users': query_db("SELECT COUNT(*) as c FROM users WHERE is_admin=0", one=True)['c'],
        'players': query_db("SELECT COUNT(*) as c FROM players", one=True)['c'],
        'nominations': query_db("SELECT COUNT(*) as c FROM nominations", one=True)['c'],
        'active': query_db("SELECT COUNT(*) as c FROM auction_sessions WHERE status='bidding'", one=True)['c'],
        'acquisitions': query_db("SELECT COUNT(*) as c FROM acquisitions", one=True)['c'],
    }
    users = query_db("""
        SELECT u.id, u.username, u.team_name, u.budget,
               COUNT(DISTINCT n.id) as nominations,
               COUNT(DISTINCT a.id) as players_won
        FROM users u
        LEFT JOIN nominations n ON n.user_id=u.id
        LEFT JOIN acquisitions a ON a.user_id=u.id
        WHERE u.is_admin=0
        GROUP BY u.id ORDER BY u.team_name
    """)
    sessions = query_db("SELECT * FROM auction_sessions ORDER BY created_at DESC LIMIT 5")
    return render_template('admin/dashboard.html', stats=stats, users=users, sessions=sessions)


@app.route('/admin/users')
@admin_required
def admin_users():
    users = query_db("""
        SELECT u.id, u.username, u.team_name, u.budget, u.is_admin, u.created_at,
               COUNT(DISTINCT n.id) as nominations,
               COUNT(DISTINCT a.id) as players_won
        FROM users u
        LEFT JOIN nominations n ON n.user_id=u.id
        LEFT JOIN acquisitions a ON a.user_id=u.id
        GROUP BY u.id ORDER BY u.is_admin DESC, u.team_name
    """)
    initial_budget = int(get_setting('initial_budget', '500'))
    return render_template('admin/users.html', users=users, initial_budget=initial_budget)

@app.route('/admin/users/create', methods=['POST'])
@admin_required
def create_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    team_name = request.form.get('team_name', '').strip()
    if not all([username, password, team_name]):
        flash('Tutti i campi sono obbligatori.', 'danger')
        return redirect(url_for('admin_users'))
    try:
        budget = int(get_setting('initial_budget', '500'))
        execute_db("INSERT INTO users (username,password,team_name,budget) VALUES (?,?,?,?)",
                   [username, generate_password_hash(password), team_name, budget])
        flash(f'Utente "{username}" ({team_name}) creato con budget {budget} crediti.', 'success')
    except Exception as e:
        flash('Username già esistente.' if 'UNIQUE' in str(e) else str(e), 'danger')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:uid>/reset-password', methods=['POST'])
@admin_required
def reset_password(uid):
    pw = request.form.get('new_password', '')
    if not pw:
        flash('Inserisci una nuova password.', 'danger')
        return redirect(url_for('admin_users'))
    execute_db("UPDATE users SET password=? WHERE id=?", [generate_password_hash(pw), uid])
    flash('Password aggiornata.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:uid>/budget', methods=['POST'])
@admin_required
def edit_budget(uid):
    budget = request.form.get('budget', '0')
    if not budget.isdigit():
        flash('Importo non valido.', 'danger')
        return redirect(url_for('admin_users'))
    execute_db("UPDATE users SET budget=? WHERE id=?", [int(budget), uid])
    flash('Budget aggiornato.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:uid>/team-name', methods=['POST'])
@admin_required
def edit_team_name(uid):
    name = request.form.get('team_name', '').strip()
    if not name:
        flash('Il nome squadra non può essere vuoto.', 'danger')
        return redirect(url_for('admin_users'))
    execute_db("UPDATE users SET team_name=? WHERE id=?", [name, uid])
    if uid == session.get('user_id'):
        session['team_name'] = name
    flash('Nome squadra aggiornato.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:uid>/delete', methods=['POST'])
@admin_required
def delete_user(uid):
    execute_db("DELETE FROM nominations WHERE user_id=?", [uid])
    execute_db("DELETE FROM bids WHERE user_id=?", [uid])
    execute_db("DELETE FROM users WHERE id=? AND is_admin=0", [uid])
    flash('Utente eliminato.', 'success')
    return redirect(url_for('admin_users'))


# ── Acquisti: annulla un'assegnazione (rimborso + giocatore libero) ──────────

@app.route('/admin/acquisti')
@admin_required
def admin_acquisti():
    rows = query_db("""
        SELECT a.id, a.price, a.session_name, a.acquired_at,
               u.id as uid, u.team_name,
               p.role, p.name, p.team
        FROM acquisitions a
        JOIN users u ON u.id=a.user_id
        JOIN players p ON p.id=a.player_id
        ORDER BY u.team_name,
                 CASE p.role WHEN 'P' THEN 1 WHEN 'D' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
                 a.acquired_at
    """)
    by_user = {}
    for r in rows:
        by_user.setdefault((r['uid'], r['team_name']), []).append(r)
    managers = [{'uid': k[0], 'team_name': k[1], 'players': v,
                 'spent': sum(x['price'] for x in v)} for k, v in by_user.items()]
    return render_template('admin/acquisti.html', managers=managers, total=len(rows))


@app.route('/admin/acquisti/<int:acq_id>/cancel', methods=['POST'])
@admin_required
def cancel_acquisition(acq_id):
    acq = query_db("""SELECT a.*, p.name as pname, u.team_name FROM acquisitions a
                      JOIN players p ON p.id=a.player_id JOIN users u ON u.id=a.user_id
                      WHERE a.id=?""", [acq_id], one=True)
    if not acq:
        flash('Acquisto non trovato.', 'danger')
        return redirect(request.referrer or url_for('admin_acquisti'))
    db = get_db()
    # rimborso al manager
    db.execute("UPDATE users SET budget=budget+? WHERE id=?", [acq['price'], acq['user_id']])
    # elimina l'acquisto
    db.execute("DELETE FROM acquisitions WHERE id=?", [acq_id])
    # libera il giocatore: l'eventuale item venduto torna 'unsold' (disponibile)
    db.execute("""UPDATE auction_items SET status='unsold', winner_id=NULL, final_price=NULL
                  WHERE player_id=? AND status='sold'""", [acq['player_id']])
    db.commit()
    db.close()
    flash(f'Acquisto annullato: {acq["pname"]} torna libero e {acq["price"]} crediti '
          f'restituiti a {acq["team_name"]}.', 'success')
    return redirect(request.referrer or url_for('admin_acquisti'))


@app.route('/admin/players')
@admin_required
def admin_players():
    players = query_db("SELECT * FROM players ORDER BY role, base_value DESC, name")
    return render_template('admin/players.html', players=players)

@app.route('/admin/players/load', methods=['POST'])
@admin_required
def load_players():
    import pandas as pd
    excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'Documenti', '0-Quotazioni_Fantacalcio_Stagione_2025_26.xlsx')
    if not os.path.exists(excel_path):
        flash('File non trovato: Documenti/0-Quotazioni_Fantacalcio_Stagione_2025_26.xlsx', 'danger')
        return redirect(url_for('admin_players'))
    try:
        df = pd.read_excel(excel_path)[['Id', 'R', 'Nome', 'Squadra', 'Qt.A']].dropna(subset=['Id', 'Nome'])
        df['Qt.A'] = df['Qt.A'].fillna(1).astype(int)
        db = get_db()
        count = 0
        for _, row in df.iterrows():
            db.execute("INSERT OR REPLACE INTO players (id,role,name,team,base_value) VALUES (?,?,?,?,?)",
                       [int(row['Id']), str(row['R']), str(row['Nome']), str(row['Squadra']), int(row['Qt.A'])])
            count += 1
        db.commit()
        db.close()
        flash(f'{count} giocatori caricati con successo.', 'success')
    except Exception as e:
        flash(f'Errore: {e}', 'danger')
    return redirect(url_for('admin_players'))

@app.route('/admin/players/clear', methods=['POST'])
@admin_required
def clear_players():
    execute_db("DELETE FROM nominations")
    execute_db("DELETE FROM players")
    flash('Giocatori e nomination cancellati.', 'success')
    return redirect(url_for('admin_players'))


@app.route('/admin/nominations')
@admin_required
def admin_nominations():
    nom_open = get_setting('nomination_open', '0') == '1'
    # Mentre le nomination sono aperte sono SEGRETE anche per l'admin
    nominated = [] if nom_open else query_db("""
        SELECT p.id, p.role, p.name, p.team, p.base_value,
               COUNT(n.id) as nom_count,
               GROUP_CONCAT(u.team_name, ', ') as nominators
        FROM players p JOIN nominations n ON n.player_id=p.id
        JOIN users u ON u.id=n.user_id
        GROUP BY p.id ORDER BY nom_count DESC, p.role, p.name
    """)
    users = query_db("""
        SELECT u.id, u.username, u.team_name,
               COUNT(n.id) as total,
               SUM(CASE WHEN p.role='P' THEN 1 ELSE 0 END) as nP,
               SUM(CASE WHEN p.role='D' THEN 1 ELSE 0 END) as nD,
               SUM(CASE WHEN p.role='C' THEN 1 ELSE 0 END) as nC,
               SUM(CASE WHEN p.role='A' THEN 1 ELSE 0 END) as nA
        FROM users u
        LEFT JOIN nominations n ON n.user_id=u.id
        LEFT JOIN players p ON p.id=n.player_id
        WHERE u.is_admin=0 GROUP BY u.id ORDER BY u.team_name
    """)
    settings = {k: int(get_setting(k, v)) for k, v in
                [('max_nom_P','5'),('max_nom_D','15'),('max_nom_C','15'),('max_nom_A','12')]}
    return render_template('admin/nominations.html',
        nominated=nominated, users=users, settings=settings, nom_open=nom_open)

@app.route('/admin/nominations/toggle', methods=['POST'])
@admin_required
def toggle_nominations():
    cur = get_setting('nomination_open', '0')
    new = '0' if cur == '1' else '1'
    set_setting('nomination_open', new)
    flash(f'Nomination {"aperte" if new=="1" else "chiuse"}.', 'success')
    return redirect(url_for('admin_nominations'))

@app.route('/admin/nominations/clear-user', methods=['POST'])
@admin_required
def clear_user_nominations():
    uid = int(request.form.get('user_id', 0))
    execute_db("DELETE FROM nominations WHERE user_id=?", [uid])
    flash('Nomination utente cancellate.', 'success')
    return redirect(url_for('admin_nominations'))


@app.route('/admin/auctions')
@admin_required
def admin_auctions():
    sessions = query_db("""
        SELECT s.*, u.team_name as creator,
               COUNT(ai.id) as total,
               SUM(CASE WHEN ai.status='sold' THEN 1 ELSE 0 END) as sold,
               SUM(CASE WHEN ai.status='unsold' THEN 1 ELSE 0 END) as unsold,
               SUM(CASE WHEN ai.status='pending' THEN 1 ELSE 0 END) as pending
        FROM auction_sessions s
        LEFT JOIN users u ON u.id=s.created_by
        LEFT JOIN auction_items ai ON ai.session_id=s.id
        GROUP BY s.id ORDER BY s.created_at DESC
    """)
    return render_template('admin/auctions.html', sessions=sessions)

@app.route('/admin/auctions/create', methods=['GET', 'POST'])
@admin_required
def create_auction():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        pids = request.form.getlist('player_ids')
        if not name or not pids:
            flash('Nome e almeno un giocatore sono obbligatori.', 'danger')
            return redirect(url_for('create_auction'))
        open_now = request.form.get('open_now') == '1'
        db = get_db()
        if open_now:
            sid = db.execute(
                "INSERT INTO auction_sessions (name,created_by,status,opened_at) VALUES (?,?,'bidding',CURRENT_TIMESTAMP)",
                [name, session['user_id']]).lastrowid
        else:
            sid = db.execute("INSERT INTO auction_sessions (name,created_by) VALUES (?,?)",
                             [name, session['user_id']]).lastrowid
        for pid in pids:
            db.execute("INSERT INTO auction_items (session_id,player_id) VALUES (?,?)", [sid, int(pid)])
        db.commit()
        db.close()
        if open_now:
            flash(f'Asta "{name}" creata e APERTA con {len(pids)} giocatori. I manager possono già fare offerte.', 'success')
        else:
            flash(f'Asta "{name}" creata con {len(pids)} giocatori. Clicca "Apri Offerte" per renderla visibile ai manager.', 'success')
        return redirect(url_for('manage_auction', session_id=sid))

    in_session = {r['player_id'] for r in query_db("""
        SELECT DISTINCT ai.player_id FROM auction_items ai
        JOIN auction_sessions s ON s.id=ai.session_id WHERE s.status IN ('pending','bidding')
    """)}
    acquired = {r['player_id'] for r in query_db("SELECT player_id FROM acquisitions")}
    excluded = in_session | acquired

    nominated = query_db("""
        SELECT p.id, p.role, p.name, p.team, p.base_value, COUNT(n.id) as nom_count
        FROM players p JOIN nominations n ON n.player_id=p.id
        GROUP BY p.id
        ORDER BY CASE p.role WHEN 'P' THEN 1 WHEN 'D' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
                 nom_count DESC, p.base_value DESC, p.name
    """)

    return render_template('admin/auction_create.html', nominated=nominated, excluded=excluded)


@app.route('/admin/auctions/<int:session_id>')
@admin_required
def manage_auction(session_id):
    s = query_db("SELECT * FROM auction_sessions WHERE id=?", [session_id], one=True)
    if not s:
        abort(404)
    items = query_db("""
        SELECT ai.id, ai.status, ai.final_price, ai.winner_id, ai.caller_id,
               p.id as pid, p.role, p.name, p.team, p.base_value,
               uw.team_name as winner_name, uc.team_name as caller_name,
               COUNT(b.id) as bid_count,
               (SELECT COUNT(*) FROM nominations n WHERE n.player_id=p.id) as nom_count,
               (SELECT acq.id FROM acquisitions acq WHERE acq.player_id=p.id AND acq.user_id=ai.winner_id) as acq_id
        FROM auction_items ai JOIN players p ON p.id=ai.player_id
        LEFT JOIN users uw ON uw.id=ai.winner_id
        LEFT JOIN users uc ON uc.id=ai.caller_id
        LEFT JOIN bids b ON b.auction_item_id=ai.id
        WHERE ai.session_id=? GROUP BY ai.id
        ORDER BY CASE p.role WHEN 'P' THEN 1 WHEN 'D' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
                 nom_count DESC, p.base_value DESC, p.name
    """, [session_id])

    items_with_bids = []
    for item in items:
        bids = query_db("""
            SELECT b.amount, b.submitted_at, u.team_name
            FROM bids b JOIN users u ON u.id=b.user_id
            WHERE b.auction_item_id=? ORDER BY b.amount DESC, b.submitted_at ASC
        """, [item['id']])
        items_with_bids.append({'item': item, 'bids': bids})

    # ── Prontezza alla chiusura ──
    # Possono puntare su un giocatore SOLO i manager che lo hanno nominato (item normali);
    # per i giocatori liberi (caller_id) sono coinvolti il chiamante e chi ha mostrato interesse.
    pending_items = [it for it in items if it['status'] == 'pending']
    total_pending = len(pending_items)
    item_ids = [it['id'] for it in pending_items]
    pids = [it['pid'] for it in pending_items]

    bidders, renouncers = {}, {}
    if item_ids:
        qm = ','.join('?' * len(item_ids))
        for r in query_db(f"SELECT auction_item_id aid, user_id uid FROM bids WHERE auction_item_id IN ({qm})", item_ids):
            bidders.setdefault(r['aid'], set()).add(r['uid'])
        for r in query_db(f"SELECT item_id aid, user_id uid FROM item_renounces WHERE item_id IN ({qm})", item_ids):
            renouncers.setdefault(r['aid'], set()).add(r['uid'])
    noms = {}
    if pids:
        qm = ','.join('?' * len(pids))
        for r in query_db(f"SELECT player_id pid, user_id uid FROM nominations WHERE player_id IN ({qm})", pids):
            noms.setdefault(r['pid'], set()).add(r['uid'])

    def eligible_for(uid, it):
        if it['caller_id']:
            return (uid == it['caller_id'] or uid in bidders.get(it['id'], set())
                    or uid in renouncers.get(it['id'], set()))
        return uid in noms.get(it['pid'], set())

    # Prontezza: ogni item normale è pronto se tutti i suoi nominatori hanno agito.
    waiting_ids = set()
    all_ready = True
    for it in pending_items:
        if it['caller_id']:
            continue  # i liberi non bloccano la chiusura (interesse dichiarato dall'offerta)
        elig = noms.get(it['pid'], set())
        acted = bidders.get(it['id'], set()) | renouncers.get(it['id'], set())
        not_acted = elig - acted
        if not_acted:
            all_ready = False
            waiting_ids |= not_acted
    all_acted = total_pending > 0 and all_ready

    urows = query_db("SELECT id, team_name, budget FROM users WHERE is_admin=0 ORDER BY team_name")
    users = []
    for u in urows:
        elig_cnt = acted_cnt = nb = nr = 0
        for it in pending_items:
            if not eligible_for(u['id'], it):
                continue
            elig_cnt += 1
            did_bid = u['id'] in bidders.get(it['id'], set())
            did_ren = u['id'] in renouncers.get(it['id'], set())
            nb += 1 if did_bid else 0
            nr += 1 if did_ren else 0
            if did_bid or did_ren:
                acted_cnt += 1
        if elig_cnt == 0:
            continue  # questo manager non può puntare su nessun giocatore in asta
        users.append({'id': u['id'], 'team_name': u['team_name'], 'budget': u['budget'],
                      'eligible': elig_cnt, 'acted': acted_cnt, 'n_bids': nb, 'n_renounces': nr,
                      'complete': acted_cnt >= elig_cnt})
    waiting = [u['team_name'] for u in urows if u['id'] in waiting_ids]

    return render_template('admin/auction_manage.html',
        s=s, items_with_bids=items_with_bids, users=users,
        total_pending=total_pending, all_acted=all_acted, waiting=waiting)


@app.route('/admin/auctions/<int:session_id>/open', methods=['POST'])
@admin_required
def open_auction(session_id):
    execute_db("UPDATE auction_sessions SET status='bidding', opened_at=CURRENT_TIMESTAMP WHERE id=?",
               [session_id])
    flash('Fase di offerte aperta! I manager possono inserire le loro offerte.', 'success')
    return redirect(url_for('manage_auction', session_id=session_id))

@app.route('/admin/auctions/<int:session_id>/reopen', methods=['POST'])
@admin_required
def reopen_auction(session_id):
    s = query_db("SELECT status FROM auction_sessions WHERE id=?", [session_id], one=True)
    if s and s['status'] == 'pending':
        execute_db("UPDATE auction_sessions SET status='bidding', opened_at=CURRENT_TIMESTAMP WHERE id=?",
                   [session_id])
        flash('Asta riaperta.', 'success')
    return redirect(url_for('manage_auction', session_id=session_id))

@app.route('/admin/auctions/<int:session_id>/close', methods=['POST'])
@admin_required
def close_auction(session_id):
    db = get_db()
    items = db.execute("""
        SELECT ai.*, p.base_value FROM auction_items ai JOIN players p ON p.id=ai.player_id
        WHERE ai.session_id=? AND ai.status='pending'
    """, [session_id]).fetchall()
    sess_name = db.execute("SELECT name FROM auction_sessions WHERE id=?", [session_id]).fetchone()['name']

    def _sell(item, user_id, price):
        db.execute("UPDATE auction_items SET status='sold', winner_id=?, final_price=? WHERE id=?",
                   [user_id, price, item['id']])
        db.execute("UPDATE users SET budget=budget-? WHERE id=?", [price, user_id])
        db.execute("INSERT INTO acquisitions (user_id,player_id,price,session_name) VALUES (?,?,?,?)",
                   [user_id, item['player_id'], price, sess_name])

    sold, ties = 0, 0
    for item in items:
        bids = db.execute("""
            SELECT b.user_id, b.amount FROM bids b
            WHERE b.auction_item_id=? ORDER BY b.amount DESC, b.submitted_at ASC
        """, [item['id']]).fetchall()

        if not bids:
            # nessuna offerta (tutti hanno rinunciato): il giocatore resta libero
            db.execute("UPDATE auction_items SET status='unsold' WHERE id=?", [item['id']])
            continue

        base = item['base_value']
        top_amount = bids[0]['amount']
        top_bidders = [b for b in bids if b['amount'] == top_amount]
        caller_id = item['caller_id']
        caller_in_top = caller_id and any(b['user_id'] == caller_id for b in top_bidders)

        if caller_id:
            # Giocatori liberi: in caso di parità vince chi ha chiamato; uno solo paga la sua offerta
            if len(top_bidders) == 1 or caller_in_top:
                w = next((b for b in top_bidders if b['user_id'] == caller_id), top_bidders[0])
                _sell(item, w['user_id'], w['amount'])
                sold += 1
            else:
                db.execute("UPDATE auction_items SET status='tie', final_price=? WHERE id=?",
                           [top_amount, item['id']])
                ties += 1
        else:
            if len(bids) == 1:
                # unico offerente (tutti gli altri hanno rinunciato): si aggiudica a prezzo +1
                _sell(item, bids[0]['user_id'], base + 1)
                sold += 1
            elif len(top_bidders) == 1:
                _sell(item, top_bidders[0]['user_id'], top_amount)
                sold += 1
            else:
                # pareggio: monetina o rilancio. final_price = importo pareggio.
                db.execute("UPDATE auction_items SET status='tie', final_price=? WHERE id=?",
                           [top_amount, item['id']])
                ties += 1

    new_status = 'resolving' if ties else 'revealed'
    db.execute("UPDATE auction_sessions SET status=?, closed_at=CURRENT_TIMESTAMP WHERE id=?",
               [new_status, session_id])
    db.commit()
    db.close()
    if ties:
        flash(f'Offerte chiuse: {sold} aggiudicati, {ties} pareggi da risolvere (monetina o rilancio).', 'warning')
        return redirect(url_for('manage_auction', session_id=session_id))
    flash(f'Asta chiusa! {sold} giocatori aggiudicati. Budget aggiornati.', 'success')
    # mostra subito l'animazione di rivelazione vincitori
    return redirect(url_for('manage_auction', session_id=session_id, reveal=1))


def _maybe_finalize_session(db, session_id):
    """Se non ci sono più pareggi aperti, la sessione passa a 'revealed'."""
    remaining = db.execute(
        "SELECT COUNT(*) c FROM auction_items WHERE session_id=? AND status='tie'",
        [session_id]).fetchone()['c']
    if remaining == 0:
        db.execute("UPDATE auction_sessions SET status='revealed' WHERE id=?", [session_id])
    return remaining


@app.route('/admin/auctions/item/<int:item_id>/coinflip', methods=['POST'])
@admin_required
def coinflip_item(item_id):
    db = get_db()
    item = db.execute("""
        SELECT ai.*, s.name as sess_name, p.name as player_name
        FROM auction_items ai JOIN auction_sessions s ON s.id=ai.session_id
        JOIN players p ON p.id=ai.player_id WHERE ai.id=? AND ai.status='tie'
    """, [item_id]).fetchone()
    if not item:
        db.close()
        return jsonify({'error': 'Pareggio non trovato o già risolto'}), 404

    tie_amount = item['final_price']
    bidders = db.execute("""
        SELECT b.user_id, u.team_name FROM bids b JOIN users u ON u.id=b.user_id
        WHERE b.auction_item_id=? AND b.amount=? ORDER BY u.team_name
    """, [item_id, tie_amount]).fetchall()

    import random
    winner = random.choice(bidders)
    final_price = tie_amount + 1

    db.execute("UPDATE auction_items SET status='sold', winner_id=?, final_price=? WHERE id=?",
               [winner['user_id'], final_price, item_id])
    db.execute("UPDATE users SET budget=budget-? WHERE id=?", [final_price, winner['user_id']])
    db.execute("INSERT INTO acquisitions (user_id,player_id,price,session_name) VALUES (?,?,?,?)",
               [winner['user_id'], item['player_id'], final_price, item['sess_name']])
    _maybe_finalize_session(db, item['session_id'])
    db.commit()
    db.close()
    return jsonify({
        'player': item['player_name'],
        'participants': [b['team_name'] for b in bidders],
        'winner': winner['team_name'],
        'amount': final_price,
        'tie_amount': tie_amount,
    })


@app.route('/admin/auctions/item/<int:item_id>/continue', methods=['POST'])
@admin_required
def continue_item(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM auction_items WHERE id=? AND status='tie'", [item_id]).fetchone()
    if not item:
        db.close()
        flash('Pareggio non trovato o già risolto.', 'danger')
        return redirect(url_for('admin_auctions'))
    tie_amount = item['final_price']
    new_min = tie_amount + 1
    # riapri il giocatore: i partecipanti dovranno rilanciare di almeno +1
    db.execute("UPDATE auction_items SET status='pending', min_bid=?, final_price=NULL, winner_id=NULL WHERE id=?",
               [new_min, item_id])
    db.execute("DELETE FROM bids WHERE auction_item_id=?", [item_id])
    db.execute("UPDATE auction_sessions SET status='bidding' WHERE id=?", [item['session_id']])
    db.commit()
    db.close()
    flash(f'Asta riaperta per il giocatore: offerta minima {new_min} crediti. I manager possono rilanciare.', 'success')
    return redirect(url_for('manage_auction', session_id=item['session_id']))

# ── Assegnazione diretta (giocatori nominati da un solo allenatore) ──────────

def _free_player_filter():
    """ID di giocatori già acquistati o in sessioni attive (da escludere)."""
    acquired = {r['player_id'] for r in query_db("SELECT player_id FROM acquisitions")}
    in_sess = {r['player_id'] for r in query_db("""
        SELECT DISTINCT ai.player_id FROM auction_items ai
        JOIN auction_sessions s ON s.id=ai.session_id WHERE s.status IN ('pending','bidding','resolving')
    """)}
    return acquired | in_sess


@app.route('/admin/single-noms')
@admin_required
def single_noms():
    in_sess = {r['player_id'] for r in query_db("""
        SELECT DISTINCT ai.player_id FROM auction_items ai
        JOIN auction_sessions s ON s.id=ai.session_id WHERE s.status IN ('pending','bidding','resolving')
    """)}
    # info acquisti (per mostrare la riga "comprato")
    acq = {r['player_id']: r for r in query_db("""
        SELECT a.player_id, a.price, u.team_name FROM acquisitions a JOIN users u ON u.id=a.user_id
    """)}
    rows = query_db("""
        SELECT p.id, p.role, p.name, p.team, p.base_value,
               COUNT(n.id) as nom_count,
               MIN(u.id) as nominator_id, MIN(u.team_name) as nominator_name
        FROM players p JOIN nominations n ON n.player_id=p.id
        JOIN users u ON u.id=n.user_id
        GROUP BY p.id HAVING COUNT(n.id)=1
        ORDER BY CASE p.role WHEN 'P' THEN 1 WHEN 'D' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
                 p.base_value DESC, p.name
    """)
    by_role = {'P': [], 'D': [], 'C': [], 'A': []}
    for r in rows:
        if r['id'] in in_sess:
            continue  # in asta: non gestire qui
        d = dict(r)
        bought = acq.get(r['id'])
        d['bought_by'] = bought['team_name'] if bought else None
        d['bought_price'] = bought['price'] if bought else None
        by_role[r['role']].append(d)
    return render_template('admin/single_noms.html', by_role=by_role)


@app.route('/admin/single-noms/release', methods=['POST'])
@admin_required
def release_single_nom():
    pid = int(request.form.get('player_id', 0))
    player = query_db("SELECT * FROM players WHERE id=?", [pid], one=True)
    if not player:
        flash('Giocatore non trovato.', 'danger')
        return redirect(url_for('single_noms'))
    if pid in _free_player_filter():
        flash(f'{player["name"]} non è più disponibile.', 'warning')
        return redirect(url_for('single_noms'))
    # abbandono: rimuove la nomination → il giocatore diventa libero per tutti
    execute_db("DELETE FROM nominations WHERE player_id=?", [pid])
    flash(f'{player["name"]} lasciato libero: ora è acquistabile da tutti nella fase Giocatori liberi.', 'success')
    return redirect(url_for('single_noms'))


@app.route('/admin/single-noms/assign', methods=['POST'])
@admin_required
def assign_single_nom():
    pid = int(request.form.get('player_id', 0))
    uid = int(request.form.get('user_id', 0))
    player = query_db("SELECT * FROM players WHERE id=?", [pid], one=True)
    user = query_db("SELECT * FROM users WHERE id=?", [uid], one=True)
    if not player or not user:
        flash('Dati non validi.', 'danger')
        return redirect(url_for('single_noms'))
    if pid in _free_player_filter():
        flash(f'{player["name"]} non è più disponibile.', 'warning')
        return redirect(url_for('single_noms'))
    # limite di reparto (es. max 3 portieri): non assegnare se la rosa del ruolo è già piena
    if not _can_take_role(uid, player['role']):
        slots = _roster_slots()
        rc = _roster_counts(uid)
        if rc.get('total', 0) >= sum(slots.values()):
            flash(f'{user["team_name"]} ha già la rosa completa.', 'warning')
        else:
            flash(f'{user["team_name"]} ha già {rc.get(player["role"], 0)}/{slots.get(player["role"], 0)} '
                  f'nel reparto {player["role"]}: non può prenderne altri.', 'warning')
        return redirect(url_for('single_noms'))
    db = get_db()
    db.execute("UPDATE users SET budget=budget-? WHERE id=?", [player['base_value'], uid])
    db.execute("INSERT INTO acquisitions (user_id,player_id,price,session_name) VALUES (?,?,?,?)",
               [uid, pid, player['base_value'], 'Nomination singola'])
    db.commit()
    db.close()
    flash(f'{player["name"]} assegnato a {user["team_name"]} per {player["base_value"]} crediti.', 'success')
    return redirect(url_for('single_noms'))


# ── Fase giocatori liberi (chiamata + monetina ordine + asta) ────────────────

@app.route('/admin/free-players')
@admin_required
def free_players():
    excluded = _free_player_filter()
    nominated = {r['player_id'] for r in query_db("SELECT DISTINCT player_id FROM nominations")}
    # giocatori andati all'asta ma invenduti (tutti hanno rinunciato): tornano liberi
    unsold = {r['player_id'] for r in query_db("SELECT DISTINCT player_id FROM auction_items WHERE status='unsold'")}
    role_filter = request.args.get('role', 'P')
    sql = "SELECT id, role, name, team, base_value FROM players"
    params = []
    if role_filter in ('P', 'D', 'C', 'A'):
        sql += " WHERE role=?"
        params.append(role_filter)
    sql += " ORDER BY base_value DESC, name"
    # liberi = non acquistati, non in sessione attiva, e (mai nominati OPPURE andati invenduti)
    players = [p for p in query_db(sql, params)
               if p['id'] not in excluded and (p['id'] not in nominated or p['id'] in unsold)]
    coaches = query_db("SELECT id, team_name FROM users WHERE is_admin=0 ORDER BY team_name")

    ph = _active_phase()
    phase = None
    label = {'P': 'Portieri', 'D': 'Difensori', 'C': 'Centrocampisti', 'A': 'Attaccanti'}
    if ph:
        order = json.loads(ph['turn_order'])
        names = {u['id']: u['team_name'] for u in query_db("SELECT id, team_name FROM users")}
        cur_uid = order[ph['turn_index']] if ph['turn_index'] < len(order) else None
        call = None
        if ph['status'] == 'bidding' and ph['current_session_id']:
            call = _free_call_state(ph['current_session_id'], ph['role'], cur_uid)
        # quanti hanno ancora bisogno di questo reparto
        remaining = [names.get(i) for i in order if ph['role'] and _can_take_role(i, ph['role'])]
        phase = {
            'status': ph['status'],
            'role': ph['role'],
            'role_label': label.get(ph['role'], ph['role']),
            'order': [names.get(i, '?') for i in order],
            'turn_name': names.get(cur_uid),
            'session_id': ph['current_session_id'],
            'call': call,
            'remaining': remaining,
            'signature': f"{ph['id']}:{ph['status']}:{ph['turn_index']}:{ph['current_session_id']}",
        }
    return render_template('admin/free_players.html',
        players=players, coaches=coaches, role_filter=role_filter, phase=phase)


@app.route('/admin/free-players/call-order', methods=['POST'])
@admin_required
def call_order():
    import random
    coaches = [dict(c) for c in query_db("SELECT id, team_name FROM users WHERE is_admin=0")]
    random.shuffle(coaches)
    return jsonify({'order': coaches})


@app.route('/admin/free-players/call', methods=['POST'])
@admin_required
def free_call():
    pid = int(request.form.get('player_id', 0))
    caller_id = int(request.form.get('caller_id', 0))
    player = query_db("SELECT * FROM players WHERE id=?", [pid], one=True)
    caller = query_db("SELECT * FROM users WHERE id=?", [caller_id], one=True)
    if not player or not caller:
        flash('Seleziona giocatore e allenatore chiamante.', 'danger')
        return redirect(url_for('free_players'))
    if pid in _free_player_filter():
        flash(f'{player["name"]} non è più disponibile.', 'warning')
        return redirect(url_for('free_players'))
    db = get_db()
    sid = db.execute(
        "INSERT INTO auction_sessions (name,created_by,status,opened_at) VALUES (?,?,'bidding',CURRENT_TIMESTAMP)",
        [f'Chiamata: {player["name"]} ({caller["team_name"]})', session['user_id']]).lastrowid
    db.execute("INSERT INTO auction_items (session_id,player_id,caller_id,min_bid) VALUES (?,?,?,?)",
               [sid, pid, caller_id, player['base_value']])
    db.commit()
    db.close()
    flash(f'Chiamata aperta su {player["name"]} da {caller["team_name"]}. '
          f'Gli interessati possono offrire (min {player["base_value"]}); '
          f'in caso di parità vince il chiamante.', 'success')
    return redirect(url_for('manage_auction', session_id=sid))


# ── Fase liberi a turni (guidata dai manager, polling) ───────────────────────

def _roster_slots():
    return {r: int(get_setting(f'slots_{r}', '0')) for r in ['P', 'D', 'C', 'A']}

def _roster_counts(uid):
    rows = query_db("""SELECT p.role, COUNT(*) c FROM acquisitions a JOIN players p ON p.id=a.player_id
                       WHERE a.user_id=? GROUP BY p.role""", [uid])
    d = {r['role']: r['c'] for r in rows}
    d['total'] = sum(r['c'] for r in rows)
    return d

def _roster_complete(uid):
    slots = _roster_slots()
    return _roster_counts(uid).get('total', 0) >= sum(slots.values())

def _can_take_role(uid, role):
    slots = _roster_slots()
    rc = _roster_counts(uid)
    return rc.get('total', 0) < sum(slots.values()) and rc.get(role, 0) < slots.get(role, 0)

def _eligible_ids_for_role(role):
    return [u['id'] for u in query_db("SELECT id FROM users WHERE is_admin=0 ORDER BY id")
            if _can_take_role(u['id'], role)]

def _active_phase():
    return query_db("SELECT * FROM free_phase WHERE active=1 ORDER BY id DESC LIMIT 1", one=True)

def _free_pool_ids():
    excluded = _free_player_filter()
    nominated = {r['player_id'] for r in query_db("SELECT DISTINCT player_id FROM nominations")}
    unsold = {r['player_id'] for r in query_db("SELECT DISTINCT player_id FROM auction_items WHERE status='unsold'")}
    return excluded, nominated, unsold


@app.route('/admin/free-phase/start', methods=['POST'])
@admin_required
def free_phase_start():
    role = (request.form.get('role') or '').strip().upper()
    if role not in ('P', 'D', 'C', 'A'):
        return jsonify({'error': 'Seleziona il reparto (P/D/C/A).'}), 400
    # ordine = manager (non-admin) che possono ancora prendere quel reparto, mescolati
    coaches = [dict(u) for u in query_db("SELECT id, team_name FROM users WHERE is_admin=0")
               if _can_take_role(u['id'], role)]
    if not coaches:
        return jsonify({'error': 'Tutti i manager hanno già completato questo reparto.'}), 400
    random.shuffle(coaches)
    order = [c['id'] for c in coaches]
    db = get_db()
    db.execute("UPDATE free_phase SET active=0 WHERE active=1")
    db.execute("INSERT INTO free_phase (status, role, turn_order, turn_index, active) VALUES ('choosing', ?, ?, 0, 1)",
               [role, json.dumps(order)])
    db.commit()
    db.close()
    return jsonify({'order': coaches, 'role': role})


@app.route('/admin/free-phase/stop', methods=['POST'])
@admin_required
def free_phase_stop():
    execute_db("UPDATE free_phase SET active=0, status='done' WHERE active=1")
    flash('Fase giocatori liberi terminata.', 'success')
    return redirect(url_for('free_players'))


@app.route('/admin/free-phase/advance', methods=['POST'])
@admin_required
def free_phase_advance():
    db = get_db()
    ph = db.execute("SELECT * FROM free_phase WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
    if ph:
        _advance_turn(db, ph)
        db.commit()
    db.close()
    return redirect(url_for('free_players'))


def _advance_turn(db, ph):
    order = json.loads(ph['turn_order'])
    role = ph['role']
    n = len(order)
    idx = ph['turn_index']
    for step in range(1, n + 1):
        cand = order[(idx + step) % n]
        # prossimo manager che può ancora prendere un giocatore di questo reparto
        if (not role) or _can_take_role(cand, role):
            db.execute("UPDATE free_phase SET status='choosing', turn_index=?, current_session_id=NULL WHERE id=?",
                       [(idx + step) % n, ph['id']])
            return True
    # tutti hanno completato il reparto → fine fase
    db.execute("UPDATE free_phase SET status='done', active=0, current_session_id=NULL WHERE id=?", [ph['id']])
    return False


@app.route('/free-phase/status')
@login_required
def free_phase_status():
    ph = _active_phase()
    if not ph:
        return jsonify({'active': False, 'signature': 'none'})
    order = json.loads(ph['turn_order'])
    uid = session['user_id']
    cur_uid = order[ph['turn_index']] if ph['turn_index'] < len(order) else None
    cur = query_db("SELECT team_name FROM users WHERE id=?", [cur_uid], one=True) if cur_uid else None
    sig = f"{ph['id']}:{ph['status']}:{ph['turn_index']}:{ph['current_session_id']}"
    return jsonify({
        'active': True,
        'status': ph['status'],
        'is_my_turn': (ph['status'] == 'choosing' and cur_uid == uid and not session.get('is_admin')),
        'current_turn_name': cur['team_name'] if cur else None,
        'session_id': ph['current_session_id'],
        'signature': sig,
    })


@app.route('/free-phase/choose', methods=['GET', 'POST'])
@login_required
def free_phase_choose():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    uid = session['user_id']
    ph = _active_phase()
    if not ph or ph['status'] != 'choosing':
        flash('Non è il momento di scegliere un giocatore.', 'warning')
        return redirect(url_for('auctions'))
    order = json.loads(ph['turn_order'])
    if order[ph['turn_index']] != uid:
        flash('Non è il tuo turno.', 'warning')
        return redirect(url_for('auctions'))

    phase_role = ph['role']
    if request.method == 'POST':
        pid = int(request.form.get('player_id', 0))
        player = query_db("SELECT * FROM players WHERE id=?", [pid], one=True)
        excluded, nominated, unsold = _free_pool_ids()
        is_free = player and pid not in excluded and (pid not in nominated or pid in unsold)
        if not player or not is_free:
            flash('Giocatore non disponibile.', 'danger')
            return redirect(url_for('free_phase_choose'))
        if phase_role and player['role'] != phase_role:
            flash('Devi chiamare un giocatore del reparto in corso.', 'warning')
            return redirect(url_for('free_phase_choose'))
        if not _can_take_role(uid, player['role']):
            flash('Hai già completato questo reparto.', 'warning')
            return redirect(url_for('free_phase_choose'))
        db = get_db()
        sid = db.execute(
            "INSERT INTO auction_sessions (name,created_by,status,opened_at) VALUES (?,?,'bidding',CURRENT_TIMESTAMP)",
            [f'Chiamata: {player["name"]}', uid]).lastrowid
        db.execute("INSERT INTO auction_items (session_id,player_id,caller_id,min_bid) VALUES (?,?,?,?)",
                   [sid, pid, uid, player['base_value']])
        db.execute("UPDATE free_phase SET status='bidding', current_session_id=? WHERE id=?", [sid, ph['id']])
        db.commit()
        db.close()
        flash(f'Hai chiamato {player["name"]}! Gli altri possono puntare o rinunciare.', 'success')
        return redirect(url_for('auctions'))

    # GET: lista giocatori liberi del reparto in corso
    excluded, nominated, unsold = _free_pool_ids()
    label = {'P': 'Portieri', 'D': 'Difensori', 'C': 'Centrocampisti', 'A': 'Attaccanti'}
    rows = query_db("SELECT id, role, name, team, base_value FROM players WHERE role=? ORDER BY base_value DESC, name",
                    [phase_role])
    free = [p for p in rows if p['id'] not in excluded and (p['id'] not in nominated or p['id'] in unsold)]
    return render_template('manager/free_choose.html', players=free,
                           role=phase_role, role_label=label.get(phase_role, phase_role))


def _free_call_state(session_id, role, caller_id):
    """Stato della chiamata in corso: giocatore, manager idonei e loro stato, prontezza."""
    item = query_db("""SELECT ai.id, ai.player_id, p.name, p.team, p.base_value
                       FROM auction_items ai JOIN players p ON p.id=ai.player_id
                       WHERE ai.session_id=? AND ai.status='pending'""", [session_id], one=True)
    if not item:
        return None
    bidders = {r['user_id'] for r in query_db("SELECT user_id FROM bids WHERE auction_item_id=?", [item['id']])}
    renouncers = {r['user_id'] for r in query_db("SELECT user_id FROM item_renounces WHERE item_id=?", [item['id']])}
    eligible_ids = set(_eligible_ids_for_role(role)) | ({caller_id} if caller_id else set())
    managers = []
    for u in query_db("SELECT id, team_name FROM users WHERE is_admin=0 ORDER BY team_name"):
        if u['id'] not in eligible_ids:
            continue
        if u['id'] in bidders:
            st = 'offerta'
        elif u['id'] in renouncers:
            st = 'rinuncia'
        else:
            st = 'attesa'
        managers.append({'id': u['id'], 'team_name': u['team_name'],
                         'is_caller': u['id'] == caller_id, 'status': st})
    all_responded = bool(managers) and all(m['status'] != 'attesa' for m in managers)
    waiting = [m['team_name'] for m in managers if m['status'] == 'attesa']
    n_bids = sum(1 for m in managers if m['status'] == 'offerta')
    return {'item': item, 'managers': managers, 'all_responded': all_responded,
            'waiting': waiting, 'n_bids': n_bids}


@app.route('/admin/free-phase/close', methods=['POST'])
@admin_required
def free_phase_close():
    db = get_db()
    ph = db.execute("SELECT * FROM free_phase WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
    if not ph or ph['status'] != 'bidding' or not ph['current_session_id']:
        db.close()
        flash('Nessuna chiamata da chiudere.', 'warning')
        return redirect(url_for('free_players'))
    sid = ph['current_session_id']
    _conclude_call_session(db, sid)
    # esito
    res = db.execute("""SELECT ai.status, ai.final_price, p.name as player, u.team_name as winner
                        FROM auction_items ai JOIN players p ON p.id=ai.player_id
                        LEFT JOIN users u ON u.id=ai.winner_id WHERE ai.session_id=?""", [sid]).fetchone()
    still_tie = res and res['status'] == 'tie'
    if not still_tie:
        ph2 = db.execute("SELECT * FROM free_phase WHERE id=?", [ph['id']]).fetchone()
        _advance_turn(db, ph2)
    db.commit()
    db.close()
    if still_tie:
        flash('Pareggio da risolvere con la monetina.', 'warning')
        return redirect(url_for('manage_auction', session_id=sid))
    # parametri per l'animazione di rivelazione sulla pagina
    from urllib.parse import urlencode
    if res and res['status'] == 'sold':
        q = urlencode({'rv_player': res['player'], 'rv_winner': res['winner'] or '—', 'rv_price': res['final_price']})
        return redirect(url_for('free_players') + '?' + q)
    flash(f'{res["player"] if res else "Giocatore"} è rimasto libero (nessuna offerta).', 'info')
    return redirect(url_for('free_players'))


def _conclude_call_session(db, session_id):
    """Chiude una sessione-chiamata (1 item). Offerta unica → prezzo di mercato (base);
       parità → vince il chiamante (caller); altrimenti la più alta."""
    sess_name = db.execute("SELECT name FROM auction_sessions WHERE id=?", [session_id]).fetchone()['name']
    item = db.execute("""SELECT ai.*, p.base_value FROM auction_items ai JOIN players p ON p.id=ai.player_id
                         WHERE ai.session_id=? AND ai.status='pending'""", [session_id]).fetchone()
    if not item:
        db.execute("UPDATE auction_sessions SET status='revealed', closed_at=CURRENT_TIMESTAMP WHERE id=?", [session_id])
        return
    bids = db.execute("""SELECT user_id, amount FROM bids WHERE auction_item_id=?
                         ORDER BY amount DESC, submitted_at ASC""", [item['id']]).fetchall()
    base = item['base_value']
    caller_id = item['caller_id']

    def _sell(uid, price):
        db.execute("UPDATE auction_items SET status='sold', winner_id=?, final_price=? WHERE id=?",
                   [uid, price, item['id']])
        db.execute("UPDATE users SET budget=budget-? WHERE id=?", [price, uid])
        db.execute("INSERT INTO acquisitions (user_id,player_id,price,session_name) VALUES (?,?,?,?)",
                   [uid, item['player_id'], price, sess_name])

    status = 'revealed'
    if not bids:
        db.execute("UPDATE auction_items SET status='unsold' WHERE id=?", [item['id']])
    elif len(bids) == 1:
        # un solo offerente → prezzo di mercato (base), non l'offerta
        _sell(bids[0]['user_id'], base)
    else:
        top = bids[0]['amount']
        top_bidders = [b for b in bids if b['amount'] == top]
        caller_in_top = caller_id and any(b['user_id'] == caller_id for b in top_bidders)
        if caller_in_top:
            _sell(caller_id, top)
        elif len(top_bidders) == 1:
            _sell(top_bidders[0]['user_id'], top)
        else:
            db.execute("UPDATE auction_items SET status='tie', final_price=? WHERE id=?", [top, item['id']])
            status = 'resolving'
    db.execute("UPDATE auction_sessions SET status=?, closed_at=CURRENT_TIMESTAMP WHERE id=?", [status, session_id])


# ── Reset stagione ───────────────────────────────────────────────────────────

@app.route('/admin/reset-season', methods=['POST'])
@admin_required
def reset_season():
    if request.form.get('confirm', '') != 'RESET':
        flash('Reset annullato: digita RESET per confermare.', 'warning')
        return redirect(url_for('admin_settings'))
    db = get_db()
    db.execute("DELETE FROM bids")
    db.execute("DELETE FROM item_renounces")
    db.execute("DELETE FROM auction_items")
    db.execute("DELETE FROM auction_sessions")
    db.execute("DELETE FROM acquisitions")
    db.execute("DELETE FROM nominations")
    db.execute("DELETE FROM player_targets")
    db.execute("DELETE FROM user_strategy")
    db.execute("DELETE FROM free_phase")
    ib = int(get_setting('initial_budget', '500'))
    db.execute("UPDATE users SET budget=? WHERE is_admin=0", [ib])
    db.execute("INSERT OR REPLACE INTO settings VALUES ('nomination_open','0')")
    db.commit()
    db.close()
    flash('Stagione resettata: aste, offerte, acquisti, nomination e strategie azzerati, budget ripristinati. '
          'Giocatori, utenti e storico mantenuti.', 'success')
    return redirect(url_for('admin_settings'))


@app.route('/admin/auctions/<int:session_id>/delete', methods=['POST'])
@admin_required
def delete_auction(session_id):
    s = query_db("SELECT status FROM auction_sessions WHERE id=?", [session_id], one=True)
    if s and s['status'] == 'revealed':
        flash('Non puoi eliminare un\'asta già completata.', 'danger')
        return redirect(url_for('admin_auctions'))
    db = get_db()
    db.execute("DELETE FROM bids WHERE auction_item_id IN (SELECT id FROM auction_items WHERE session_id=?)", [session_id])
    db.execute("DELETE FROM auction_items WHERE session_id=?", [session_id])
    db.execute("DELETE FROM auction_sessions WHERE id=?", [session_id])
    db.commit()
    db.close()
    flash('Asta eliminata.', 'success')
    return redirect(url_for('admin_auctions'))


@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        for key in ['max_nom_P','max_nom_D','max_nom_C','max_nom_A',
                    'slots_P','slots_D','slots_C','slots_A',
                    'initial_budget','max_players','league_name','tie_rule']:
            v = request.form.get(key)
            if v is not None:
                set_setting(key, v.strip())
        flash('Impostazioni salvate.', 'success')
        return redirect(url_for('admin_settings'))
    settings = {k: get_setting(k, v) for k, v in [
        ('max_nom_P','5'),('max_nom_D','15'),('max_nom_C','15'),('max_nom_A','12'),
        ('slots_P','3'),('slots_D','8'),('slots_C','8'),('slots_A','6'),
        ('initial_budget','500'),('max_players','25'),('league_name','Fantabirra'),('tie_rule','first'),
    ]}
    return render_template('admin/settings.html', settings=settings)


@app.route('/classifica')
@login_required
def classifica():
    users = query_db("""
        SELECT u.id, u.team_name, u.budget,
               COUNT(a.id) as players_won,
               COALESCE(SUM(a.price),0) as spent
        FROM users u
        LEFT JOIN acquisitions a ON a.user_id=u.id
        WHERE u.is_admin=0 GROUP BY u.id ORDER BY spent DESC, players_won DESC
    """)
    initial_budget = int(get_setting('initial_budget', '500'))
    return render_template('classifica.html', users=users, initial_budget=initial_budget)


# ── Storico / Albo d'Oro ────────────────────────────────────────────────────

@app.route('/storico')
@login_required
def storico():
    seasons = query_db("SELECT * FROM history_seasons ORDER BY sort_order DESC")

    # Albo: conteggio trofei per presidente
    camp = query_db("""
        SELECT champion as pres, COUNT(*) as c FROM history_seasons
        WHERE champion IS NOT NULL AND champion != '' GROUP BY champion
    """)
    cup = query_db("""
        SELECT champion_cup as pres, COUNT(*) as c FROM history_seasons
        WHERE champion_cup IS NOT NULL AND champion_cup != '' GROUP BY champion_cup
    """)
    albo = {}
    for r in camp:
        albo.setdefault(r['pres'], {'camp': 0, 'cup': 0})['camp'] = r['c']
    for r in cup:
        albo.setdefault(r['pres'], {'camp': 0, 'cup': 0})['cup'] = r['c']
    albo_list = sorted(
        [{'pres': p, 'camp': v['camp'], 'cup': v['cup'], 'tot': v['camp'] + v['cup']}
         for p, v in albo.items()],
        key=lambda x: (-x['tot'], -x['camp'], x['pres'])
    )

    return render_template('history/storico.html', seasons=seasons, albo=albo_list)


@app.route('/storico/<int:season_id>')
@login_required
def storico_stagione(season_id):
    s = query_db("SELECT * FROM history_seasons WHERE id=?", [season_id], one=True)
    if not s:
        abort(404)
    standings = query_db(
        "SELECT * FROM history_standings WHERE season_id=? ORDER BY position", [season_id])
    return render_template('history/stagione.html', s=s, standings=standings)


@app.route('/statistiche')
@login_required
def statistiche():
    seasons = query_db("SELECT * FROM history_seasons")
    standings = query_db("SELECT * FROM history_standings")

    season_by_id = {s['id']: s for s in seasons}
    stats = {}

    def ensure(p):
        if p not in stats:
            stats[p] = {'pres': p, 'presenze': 0, 'camp': 0, 'cup': 0,
                        'podi': 0, 'vittorie_pos': 0, 'punti_tot': 0, 'punti_n': 0,
                        'best': None, 'worst': None, 'positions': []}
        return stats[p]

    for s in seasons:
        if s['champion']:
            ensure(s['champion'])['camp'] += 1
        if s['champion_cup']:
            ensure(s['champion_cup'])['cup'] += 1

    for r in standings:
        p = r['presidente']
        if not p:
            continue
        d = ensure(p)
        d['presenze'] += 1
        pos = r['position']
        d['positions'].append(pos)
        if pos == 1:
            d['vittorie_pos'] += 1
        if pos and pos <= 3:
            d['podi'] += 1
        if d['best'] is None or pos < d['best']:
            d['best'] = pos
        if d['worst'] is None or pos > d['worst']:
            d['worst'] = pos
        if r['points'] is not None:
            d['punti_tot'] += r['points']
            d['punti_n'] += 1

    rows = []
    for d in stats.values():
        d['trofei'] = d['camp'] + d['cup']
        d['pos_media'] = round(sum(d['positions']) / len(d['positions']), 1) if d['positions'] else None
        d['punti_media'] = round(d['punti_tot'] / d['punti_n'], 1) if d['punti_n'] else None
        rows.append(d)
    rows.sort(key=lambda x: (-x['trofei'], -x['camp'], -(x['podi']), x['pres']))

    return render_template('history/statistiche.html', rows=rows, n_stagioni=len(seasons))


@app.route('/curiosita')
@login_required
def curiosita():
    items = query_db("SELECT * FROM curiosita ORDER BY sort_order, id")

    # curiosità calcolate dai dati
    derived = []
    top_pres = query_db("""
        SELECT champion as p, COUNT(*) c FROM history_seasons
        WHERE champion IS NOT NULL GROUP BY champion ORDER BY c DESC LIMIT 1
    """, one=True)
    if top_pres:
        derived.append(('Presidente più titolato (Campionato)', f"{top_pres['p']}",
                        f"{top_pres['c']} titoli di FantaCampionato vinti."))
    top_cup = query_db("""
        SELECT champion_cup as p, COUNT(*) c FROM history_seasons
        WHERE champion_cup IS NOT NULL GROUP BY champion_cup ORDER BY c DESC LIMIT 1
    """, one=True)
    if top_cup:
        derived.append(('Re della FantaChampion', f"{top_cup['p']}",
                        f"{top_cup['c']} FantaChampion vinte."))
    rec = query_db("""
        SELECT s.season, st.team, st.presidente, st.points
        FROM history_standings st JOIN history_seasons s ON s.id=st.season_id
        WHERE st.points IS NOT NULL ORDER BY st.points DESC LIMIT 1
    """, one=True)
    if rec:
        derived.append(('Record di punti in una stagione', f"{rec['points']} punti",
                        f"{rec['team']} ({rec['presidente']}) nella stagione {rec['season']}."))

    return render_template('history/curiosita.html', items=items, derived=derived)


@app.route('/regolamento')
@login_required
def regolamento():
    html = get_setting('regolamento_html', '')
    version = get_setting('regolamento_version', '')
    return render_template('history/regolamento.html', regolamento_html=html, version=version)


# ── Admin: dati storici e regolamento ───────────────────────────────────────

@app.route('/admin/storico/load', methods=['POST'])
@admin_required
def load_history():
    import seed_history
    txt = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'Documenti', '_regolamento_utf8.txt')
    db = get_db()
    seed_history.seed(db, regolamento_txt=txt if os.path.exists(txt) else None)
    db.close()
    flash('Dati storici e regolamento caricati con successo.', 'success')
    return redirect(url_for('admin_storico'))

@app.route('/admin/storico')
@admin_required
def admin_storico():
    seasons = query_db("""
        SELECT s.*, COUNT(st.id) as n_teams
        FROM history_seasons s LEFT JOIN history_standings st ON st.season_id=s.id
        GROUP BY s.id ORDER BY s.sort_order DESC
    """)
    return render_template('admin/storico.html', seasons=seasons)

@app.route('/admin/storico/season', methods=['POST'])
@admin_required
def save_season():
    sid = request.form.get('season_id')
    fields = ['season', 'champion', 'champion_team', 'champion_cup', 'champion_cup_team', 'note']
    vals = {f: request.form.get(f, '').strip() for f in fields}
    if not vals['season']:
        flash('Il campo "Stagione" è obbligatorio.', 'danger')
        return redirect(url_for('admin_storico'))
    if sid:
        execute_db("""UPDATE history_seasons SET season=?, champion=?, champion_team=?,
                      champion_cup=?, champion_cup_team=?, note=? WHERE id=?""",
                   [vals['season'], vals['champion'], vals['champion_team'],
                    vals['champion_cup'], vals['champion_cup_team'], vals['note'], int(sid)])
        flash('Stagione aggiornata.', 'success')
    else:
        order = request.form.get('sort_order', '0')
        execute_db("""INSERT INTO history_seasons (season, sort_order, champion, champion_team,
                      champion_cup, champion_cup_team, note) VALUES (?,?,?,?,?,?,?)""",
                   [vals['season'], int(order) if order.isdigit() else 0, vals['champion'],
                    vals['champion_team'], vals['champion_cup'], vals['champion_cup_team'], vals['note']])
        flash('Stagione aggiunta.', 'success')
    return redirect(url_for('admin_storico'))

@app.route('/admin/storico/season/<int:sid>/delete', methods=['POST'])
@admin_required
def delete_season(sid):
    execute_db("DELETE FROM history_standings WHERE season_id=?", [sid])
    execute_db("DELETE FROM history_seasons WHERE id=?", [sid])
    flash('Stagione eliminata.', 'success')
    return redirect(url_for('admin_storico'))

@app.route('/admin/storico/season/<int:sid>/standings', methods=['GET', 'POST'])
@admin_required
def edit_standings(sid):
    s = query_db("SELECT * FROM history_seasons WHERE id=?", [sid], one=True)
    if not s:
        abort(404)
    if request.method == 'POST':
        rows = request.form.get('standings_data', '').strip()
        db = get_db()
        db.execute("DELETE FROM history_standings WHERE season_id=?", [sid])
        pos = 0
        for line in rows.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [x.strip() for x in line.split('|')]
            team = parts[0] if len(parts) > 0 else ''
            pres = parts[1] if len(parts) > 1 else ''
            pts = parts[2] if len(parts) > 2 else ''
            if not team:
                continue
            pos += 1
            db.execute("INSERT INTO history_standings (season_id, position, team, presidente, points) VALUES (?,?,?,?,?)",
                       [sid, pos, team, pres, int(pts) if pts.isdigit() else None])
        db.commit()
        db.close()
        flash('Classifica salvata.', 'success')
        return redirect(url_for('admin_storico'))
    standings = query_db("SELECT * FROM history_standings WHERE season_id=? ORDER BY position", [sid])
    return render_template('admin/standings_edit.html', s=s, standings=standings)

@app.route('/admin/regolamento', methods=['GET', 'POST'])
@admin_required
def admin_regolamento():
    if request.method == 'POST':
        set_setting('regolamento_html', request.form.get('regolamento_html', ''))
        set_setting('regolamento_version', request.form.get('regolamento_version', '').strip())
        flash('Regolamento aggiornato.', 'success')
        return redirect(url_for('admin_regolamento'))
    html = get_setting('regolamento_html', '')
    version = get_setting('regolamento_version', '')
    return render_template('admin/regolamento_edit.html', regolamento_html=html, version=version)

@app.route('/admin/curiosita', methods=['GET', 'POST'])
@admin_required
def admin_curiosita():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            execute_db("INSERT INTO curiosita (title, value, detail, sort_order) VALUES (?,?,?,?)",
                       [request.form.get('title', '').strip(), request.form.get('value', '').strip(),
                        request.form.get('detail', '').strip(),
                        query_db("SELECT COALESCE(MAX(sort_order),0)+1 c FROM curiosita", one=True)['c']])
            flash('Curiosità aggiunta.', 'success')
        elif action == 'delete':
            execute_db("DELETE FROM curiosita WHERE id=?", [request.form.get('id')])
            flash('Curiosità eliminata.', 'success')
        return redirect(url_for('admin_curiosita'))
    items = query_db("SELECT * FROM curiosita ORDER BY sort_order, id")
    return render_template('admin/curiosita_edit.html', items=items)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
