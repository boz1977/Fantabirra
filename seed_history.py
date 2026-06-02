# -*- coding: utf-8 -*-
"""Dati storici della Lega Fantabirra, estratti dal Regolamento 2021-22.
   Tutti i dati sono modificabili dal pannello admin dopo il caricamento."""
import os

# ── Albo d'Oro FantaCampionato (anno, presidente, squadra) ──────────────────
ALBO_CAMPIONATO = [
    ('2000-01', 'Igor',    'Gogheta'),
    ('2001-02', 'Beppe',   'Osama B.L.'),
    ('2002-03', 'Beppe',   'Pitiglia'),
    ('2003-04', "Mighè",   'Cicileo'),
    ('2004-05', 'Beppe',   'Pitiglia'),
    ('2005-06', "Mighè",   'Cicileo'),
    ('2006-07', 'Igor',    'Ciuccia tanto ciuccia forte'),
    ('2007-08', None,      'Sospeso'),
    ('2008-09', 'Boz',     'Eccerto Team'),
    ('2009-10', 'Scatto',  'West Hanema'),
    ('2010-11', 'Beppe',   'Pitiglia'),
    ('2011-12', 'Boz',     'BungaBunga'),
    ('2012-13', 'Calsa',   'I Baucheti'),
    ('2013-14', 'Fausto',  'AC Venetian'),
    ('2014-15', 'Scatto',  'East Hanema'),
    ('2015-16', 'Fausto',  'AC Venetian'),
    ('2016-17', 'Kekko',   'Hellas Madonna'),
    ('2017-18', 'Boz',     'BungaBunga'),
    ('2018-19', 'Antonio', 'Milf Hunters'),
    ('2019-20', 'Daniele', 'Lord Cavallo FC'),
    ('2020-21', 'Massimo', 'Hammerlake F.C.'),
    ('2021-22', 'Igor',    'Eiakulowsky FTM'),
]

# ── Albo d'Oro FantaChampion (anno, presidente, squadra) ────────────────────
ALBO_CHAMPION = [
    ('2002-03', 'Beppe',    'Pitiglia'),
    ('2003-04', 'Stefano',  'Sporting Milingo'),
    ('2004-05', 'Boz',      'Pearl Hunter Team'),
    ('2005-06', 'Beppe',    'Pitiglia'),
    ('2006-07', "Mighè",    'Cicileo'),
    ('2007-08', 'Thomas',   'Zaziziani'),
    ('2008-09', 'Beppe',    'Pitiglia'),
    ('2009-10', 'Boz',      'Eccerto'),
    ('2010-11', "Mighè",    'Cicileo'),
    ('2011-12', 'Boz',      'BungaBunga'),
    ('2012-13', "Donè",     'Pinerolo'),
    ('2013-14', 'Fausto',   'AC Venetian'),
    ('2014-15', 'Boz',      'BungaBunga'),
    ('2015-16', 'Fabrizio', 'Qualunquemente'),
    ('2016-17', 'Stefano',  'Vigili del fuoco di La Spezia'),
    ('2017-18', 'Massimo',  'AS Fidanken'),
    ('2018-19', 'Fausto',   'AC Venetian'),
    ('2019-20', 'Daniele',  'Lord Cavallo FC'),
    ('2020-21', 'Calsa',    'I Baucheti'),
    ('2021-22', 'Liviano',  'Pm Black White'),
]

# ── Classifiche finali FantaCampionato (pos, squadra, presidente, punti) ─────
STANDINGS = {
    '2002-03': [(1,'F.C. Pitiglia','Beppe',48),(2,'A.C. Harley','Fausto',39),(3,'Jigglypuff',"Donè",36),(4,'ElefanTeam','Scatto',34),(5,'Vaffanculo F.C.',"Mighè",33),(6,'Sholin Soccer','Boz',30),(7,'Morte Nera','Igor',25),(8,'United Cavallino','Peo',22),(9,'Sporting Milingo','Stefano',21)],
    '2004-05': [(1,'Pitiglia','Beppe',44),(2,'A.C. Harley','Fausto',42),(3,'Magic Felipe','Thomas',37),(4,'Anemaguay','Scatto',37),(5,'Pearl Hunter Team','Boz',36),(6,'Olympique Fossombrone','Stefano',33),(7,'G.P.S. Team','Peo',25),(8,'Cicileo',"Mighè",22),(9,'Eiakulowsky','Igor',21)],
    '2005-06': [(1,'Cicileo',"Mighè",44),(2,'Real Basovizza','Stefano',43),(3,'Atletic Queimada','Peo',41),(4,'Eccerto Team','Boz',40),(5,'R.A.T.B.','Scatto',40),(6,'Pitiglia','Beppe',36),(7,'Highland',"Donè",35),(8,'Tommy City Ramblers','Thomas',34),(9,'AC Harley','Fausto',34),(10,'Eiakulowsky','Igor',23)],
    '2006-07': [(1,'Ciuccia tanto ciuccia forte','Igor',49),(2,'Eccerto Team','Boz',46),(3,'Dinamo Stramare','Stefano',45),(4,'A.C. Harley','Fausto',40),(5,'Cicileo',"Mighè",39),(6,'Pitiglia','Beppe',37),(7,'Atletic Queimada','Peo',36),(8,'Highland',"Donè",34),(9,'La Bbomba F.C.','Thomas',26),(10,'A.C. Puccina','Scatto',24)],
    '2007-08': [(1,'Eccerto Team','Boz',28),(2,'Duvel FFC',"Donè",28),(3,'Eiakulowsy F.C.','Igor',27),(4,'A.C. Harley','Fausto',25),(5,'Cicileo',"Mighè",25),(6,'Zaziziani','Thomas',24),(7,'A.C. Valkanela','Peo',23),(8,'Cosimomele 1908 F.C.','Stefano',22),(9,'Pitiglia','Beppe',18),(10,'Stella Anema','Scatto',8)],
    '2008-09': [(1,'Eccerto Team','Boz',64),(2,'Pitiglia','Beppe',61),(3,'Eiakulowsy F.C.','Igor',55),(4,'Cicileo',"Mighè",50),(5,'Duvel FFC',"Donè",48),(6,'AC Porceddu','Calsa',47),(7,'Real Babudoia','Stefano',44),(8,'A.C. Harley','Fausto',44),(9,'CSKAnema','Scatto',36),(10,'A.C. Kastro','Peo',34)],
    '2009-10': [(1,'West Hanema','Scatto',54),(2,'Eccerto','Boz',51),(3,'andreablock','Andrea',43),(4,'sarusko',"Mighè",43),(5,'Eiakulowsky F.C.','Igor',42),(6,'USC Escort 1907','Stefano',39),(7,'giuzan','Beppe',31),(8,'lultimo777','Fausto',24),(9,'europeo79','Peo',24),(10,'AC Porceddu','Calsa',16)],
    '2010-11': [(1,'Pitiglia F.C.','Beppe',57),(2,'lultimo777','Fausto',56),(3,'Cicileo F.C.',"Mighè",55),(4,'AC Picchia','Boz',49),(5,'Duvel F.F.C.',"Donè",49),(6,'West Hanema','Scatto',46),(7,"Atl. Manòn'Tropp",'Kekko',40),(8,'Andreablock','Andrea',38),(9,'I Baucheti','Calsa',38),(10,'FC Silviomerda','Stefano',37),(11,'Eiakulowsky F.C.','Igor',32),(12,'Thai Peo','Peo',30)],
    '2011-12': [(1,'BungaBunga','Boz',64),(2,'East Hanema','Scatto',61),(3,'A.C. Venetian','Fausto',61),(4,'AC Scilipotese','Kekko',49),(5,'I Baucheti','Calsa',48),(6,'Capitano','Andrea',47),(7,'Eiakulowsky F.C.','Igor',45),(8,'FC Bayern Marcon','TenTen',43),(9,'Duvel',"Donè",40),(10,'Cicileo',"Mighè",37),(11,'Pitiglia','Beppe',34),(12,'Deportivo Lavitola','Stefano',25)],
    '2012-13': [(1,'I Baucheti','Calsa',66),(2,'Pinerolo',"Donè",55),(3,'BungaBunga','Boz',55),(4,'East Hanema','Scatto',53),(5,'A.C. Venetian','Fausto',44),(6,'Eiakulowsky F.C.','Igor',44),(7,'Federació Catalana de Futbol','TenTen',44),(8,'Pitiglia','Beppe',44),(9,'CSKAPEA','Stefano',42),(10,'Cicileo',"Mighè",25)],
    '2013-14': [(1,'A.C. Venetian','Fausto',66),(2,'BungaBunga','Boz',61),(3,'ThunderStruck','Fabrizio',59),(4,'East Hanema','Scatto',57),(5,'Pinerolo',"Donè",56),(6,'I Baucheti','Calsa',52),(7,'Eiakulowsky F.C.','Igor',43),(8,'Esercito di Silvio','Stefano',39),(9,'Federació Catalana de Futbol','TenTen',35),(10,'Lokomotiv Mosca.rdelli','Kekko',22)],
    '2014-15': [(1,'East Hanema','Scatto',None),(2,'BungaBunga','Boz',None),(3,'FC ICE','Kekko',None),(4,'Pinerolo',"Donè",None),(5,'Fantabirra United','FBU',None),(6,'I Baucheti','Calsa',None),(7,'A.C. Venetian','Fausto',None),(8,'Dinamo Camposampiero','Stefano',None),(9,'Eiakulowsky F.C.','Igor',None),(10,'ThunderStruck','Fabrizio',None)],
    '2015-16': [(1,'AC Venetian','Fausto',67),(2,'Knattspyrnyfelagiofram','Stefano',62),(3,'Real Hanema','Scatto',60),(4,'Qualunquemente','Fabrizio',56),(5,'BungaBunga','Boz',48),(6,'FC ICE','Kekko',46),(7,'Fantabirra United','FBU',39),(8,'FuckYou',"Donè",39),(9,'I Baucheti','Calsa',38),(10,'Eiakulowsky','Igor',24)],
    '2016-17': [(1,'Hellas Madonna','Kekko',76),(2,'BungaBunga','Boz',55),(3,'I Baucheti','Calsa',49),(4,'Senza Hanema','Scatto',47),(5,'Moonbeams','Igor',46),(6,'Vigili del fuoco di La Spezia','Stefano',45),(7,'AS Fidanken','Massimo',42),(8,'AC Venetian','Fausto',35)],
    '2017-18': [(1,'BungaBunga','Boz',61),(2,'Moonbeams','Igor',58),(3,'Senza Hanema','Scatto',56),(4,'AC Venetian','Fausto',52),(5,'PM Black White','Liviano',49),(6,'AS Fidanken','Massimo',48),(7,'Hellas Madonna','Kekko',46),(8,'Fantabirra United','FBU',42),(9,'I Baucheti','Calsa',41),(10,'UnisportAuto Chisinau Fotbal Club','Stefano',38)],
    '2018-19': [(1,'Milf Hunters','Antonio',59),(2,'BungaBunga','Boz',57),(3,'PM Black White','Liviano',55),(4,'FC Hanema 04','Scatto',55),(5,'Lord Cavallo FC','Daniele',47),(6,'SalviniMerda FC','Stefano',46),(7,'Moonbeams','Igor',45),(8,'AS Fidanken','Massimo',41),(9,'AC Venetian','Fausto',39),(10,'I Baucheti','Calsa',36)],
    '2019-20': [(1,'Lord Cavallo FC','Daniele',73),(2,'BungaBunga','Boz',66),(3,'Bibbianese','Stefano',66),(4,'Pm Black White','Liviano',57),(5,'Milf Hunters','Antonio',53),(6,'As Fidanken','Massimo',51),(7,'Anemavaff','Scatto',48),(8,'I Baucheti','Calsa',47),(9,'AC Venetian','Fausto',43),(10,'Moonbeams','Igor',36)],
    '2020-21': [(1,'Hammerlake F.C.','Massimo',60),(2,'Lord Cavallo FC','Daniele',59),(3,'Real Sarruidi','Paolo',56),(4,'NonceneCoviddi','Stefano',54),(5,'Bungabunga','Boz',49),(6,'Eiankulovsky FTM','Igor',49),(7,'AC XOXO','Fausto',49),(8,'I Baucheti','Calsa',43),(9,'ExtraImmunitari','Scatto',41),(10,'Pm Black White','Liviano',33)],
    '2021-22': [(1,'Eiakulowsky FTM','Igor',60),(2,'I Baucheti','Calsa',59),(3,'Hammerlake F.C.','Massimo',56),(4,'Lord Cavallo FC','Daniele',52),(5,'Pm Black White','Liviano',51),(6,'An-ae-m-en-a','Scatto',49),(7,'Monkeypox','Stefano',46),(8,'cepocodastareAllegri','Paolo',45),(9,'Bungabunga','Boz',40),(10,'AC XOXO','Fausto',35)],
}

# ── Curiosità (titolo, valore, dettaglio) ───────────────────────────────────
CURIOSITA = [
    ('Punteggio massimo di una squadra', '99 punti', 'Il punteggio più alto mai realizzato da una squadra in una giornata.'),
    ('Partita con più gol', '9 gol', 'La partita con il maggior numero di gol complessivi.'),
    ('Punteggio più alto di un giocatore', '25 punti', 'Il miglior voto + bonus mai ottenuto da un singolo calciatore.'),
    ('Anno di fondazione', '2000', 'La lega nasce nel 2000 al Bar "Tre Scalini" di Padova con i presidenti Boz, Donè, Mighè e Peo.'),
    ('Campionato sospeso', 'Stagione 2007-08', "L'unica stagione sospesa, interrotta alla 19ª giornata."),
]

# ── Sezioni che diventano titoli nel regolamento ────────────────────────────
_HEADINGS = {
    'introduzione', 'storia della fantalega', 'creazione della rosa', 'fantaasta',
    'asta iniziale', 'inserimento formazione', 'il calcio mercato',
    'il calcio mercato on line', 'il calcolo dei punteggio', 'fantachampion',
    'campionato a 8 squadre', 'campionato a 10 squadre', 'campionato a 12 squadre',
    'premi',
}


def build_regolamento_html(txt_path):
    """Converte il testo del regolamento in HTML pulito (solo sezioni regole)."""
    import html as _html
    if not os.path.exists(txt_path):
        return '<p>Regolamento non disponibile.</p>'
    with open(txt_path, encoding='utf-8', errors='replace') as f:
        lines = [l.rstrip('\n') for l in f]

    out = []
    started = False
    for line in lines:
        s = line.strip()
        key = s.lower().rstrip(":. ").strip()
        if key == 'introduzione':
            started = True
        if not started:
            continue
        # ci fermiamo prima delle tabelle Albo/Classifiche (gestite a parte)
        if key in ("albo d'oro", "albo d'oro fantacampionato"):
            break
        if not s:
            continue
        if key in _HEADINGS:
            out.append(f'<h4 class="reg-heading">{_html.escape(s.rstrip(":. "))}</h4>')
        else:
            out.append(f'<p>{_html.escape(s)}</p>')
    return '\n'.join(out)


def seed(db, regolamento_txt=None):
    """Popola le tabelle storiche. db = connessione sqlite3 aperta."""
    db.execute("DELETE FROM history_standings")
    db.execute("DELETE FROM history_seasons")
    db.execute("DELETE FROM curiosita")

    champ_map = {a: (p, t) for a, p, t in ALBO_CHAMPION}
    order = 0
    for anno, pres, squadra in ALBO_CAMPIONATO:
        order += 1
        cup = champ_map.get(anno)
        sid = db.execute(
            "INSERT INTO history_seasons (season, sort_order, champion, champion_team, champion_cup, champion_cup_team) VALUES (?,?,?,?,?,?)",
            [anno, order, pres, squadra, cup[0] if cup else None, cup[1] if cup else None]
        ).lastrowid
        for pos, team, presidente, punti in STANDINGS.get(anno, []):
            db.execute(
                "INSERT INTO history_standings (season_id, position, team, presidente, points) VALUES (?,?,?,?,?)",
                [sid, pos, team, presidente, punti]
            )

    for o, (titolo, valore, dettaglio) in enumerate(CURIOSITA):
        db.execute("INSERT INTO curiosita (title, value, detail, sort_order) VALUES (?,?,?,?)",
                   [titolo, valore, dettaglio, o])

    if regolamento_txt:
        html = build_regolamento_html(regolamento_txt)
        db.execute("INSERT OR REPLACE INTO settings VALUES ('regolamento_html', ?)", [html])
        db.execute("INSERT OR REPLACE INTO settings VALUES ('regolamento_version', '2021-22')")

    db.commit()
