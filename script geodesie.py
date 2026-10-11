"""
Convertisseur de coordonnées géodésiques  ⇄  cartésiennes

  →  (φ, λ, h)  devient  (X, Y, Z)
  ←  (X, Y, Z)  devient  (φ, λ, h)

On tape les valeurs d'un côté, on clique sur la flèche, et le résultat apparaît de l'autre côté.
Chaque point converti est dessiné sur un schéma 3D et sur un globe qu'on fait tourner à la souris.
"""
# Le programme en deux mots :
#   - φ (phi) = la latitude, λ (lambda) = la longitude, h = la hauteur au-dessus de la surface ;
#   - X, Y, Z = la même position, mais mesurée en mètres à partir du centre de la Terre.
# Il passe de l'une à l'autre, puis dessine le résultat.
# (Dans les calculs on utilise des radians, mais à l'écran on affiche des degrés, plus parlants.)
#
# Les modules utilisés :
#   math = les maths (sin, cos...) ; random = hasard (étoiles, rotation de départ) ;
#   re = lire les angles tapés en degrés-minutes-secondes ; sys = lire le thème donné au lancement ;
#   time = faire « battre » les points ; tkinter = la fenêtre et le dessin.
import math
import random
import re
import sys
import time
import tkinter as tk
from tkinter import ttk

# ====================================================================== 1. LES CALCULS
# La Terre n'est pas une boule parfaite : elle est un peu aplatie aux pôles. On la représente
# donc par un « ballon écrasé » (un ellipsoïde), décrit par deux rayons en mètres :
#   a = le rayon à l'équateur, b = le rayon aux pôles.
# Clarke 1880 est l'ellipsoïde du système Merchich, utilisé au Maroc.
ELLIPSOIDES = {
    "Clarke 1880 (Merchich)": (6378249.145, 6356515.0),
    "GRS 80": (6378137.0, 6356752.314),
    "WGS 84": (6378137.0, 6356752.314245),
    "Hayford 1909": (6378388.0, 6356911.946),
}


# e² (l'excentricité au carré) dit « à quel point le ballon est écrasé » : 0 = boule parfaite.
# Presque toutes les formules en ont besoin, donc on la calcule ici une fois pour toutes.
def e2_of(a, b):
    return (a * a - b * b) / (a * a)


# N = la distance entre un point de la surface et l'axe des pôles, mesurée en suivant la
# verticale du lieu. Sur une boule ce serait simplement le rayon ; ici N change avec la latitude.
def N_of(phi, a, e2):
    return a / math.sqrt(1 - e2 * math.sin(phi) ** 2)


# Conversion → : on connaît φ, λ et h, on veut X, Y, Z (origine au centre de la Terre).
# Les angles arrivent déjà en radians. Pas de boucle : c'est une formule directe.
def geo_to_cart(phi, lam, h, a, b):
    e2 = e2_of(a, b)
    # On commence par N à la latitude du point, car X, Y et Z en ont besoin.
    N = N_of(phi, a, e2)
    # X et Y : on prend la distance (N + h), on la ramène dans le plan de l'équateur (cos φ),
    #          puis on la tourne de l'angle λ (cos λ et sin λ).
    # Z :      sin φ donne la hauteur par rapport au plan de l'équateur. Le facteur (1 - e²) vient
    #          de l'aplatissement : sur un ellipsoïde, la verticale du lieu ne passe pas par le centre.
    return ((N + h) * math.cos(phi) * math.cos(lam),
            (N + h) * math.cos(phi) * math.sin(lam),
            (N * (1 - e2) + h) * math.sin(phi))


# Conversion ← (méthode directe) : on connaît X, Y, Z et on cherche φ, λ, h.
# Difficulté : φ et h dépendent l'un de l'autre. Ici, une formule toute faite donne φ d'un seul coup.
def cart_to_geo_directe(X, Y, Z, a, b):
    # e² et l'aplatissement f = (a - b) / a.
    e2, f = e2_of(a, b), (a - b) / a
    # p = distance du point à l'axe des pôles (on regarde la Terre de dessus).
    # r = distance du point au centre de la Terre.
    p, r = math.hypot(X, Y), math.sqrt(X * X + Y * Y + Z * Z)
    # µ est un angle intermédiaire : une très bonne première idée de la latitude, qui sert juste à calculer la vraie.
    mu = math.atan((Z / p) * ((1 - f) + a * e2 / r))
    # Grâce à µ, on obtient la vraie latitude φ.
    phi = math.atan((Z * (1 - f) + e2 * a * math.sin(mu) ** 3)
                    / ((1 - f) * (p - e2 * a * math.cos(mu) ** 3)))
    # Avec φ connue, on en déduit la hauteur h.
    # La longitude, c'est simplement atan2(Y, X) : atan2 choisit tout seul le bon quart de cercle
    # d'après les signes de X et de Y (ce que ne ferait pas atan(Y/X)).
    h = p * math.cos(phi) + Z * math.sin(phi) - a * math.sqrt(1 - e2 * math.sin(phi) ** 2)
    return phi, math.atan2(Y, X), h


# Conversion ← (méthode itérative) : on part d'une latitude approximative, puis on l'améliore
# en boucle jusqu'à ce qu'elle ne bouge presque plus. Plus facile à comprendre : on voit la valeur
# se stabiliser.
def cart_to_geo_iterative(X, Y, Z, a, b, eps=1e-12):
    e2 = e2_of(a, b)
    p = math.hypot(X, Y)
    # Premier essai : on fait comme si le point était sur une boule, sans la hauteur. Pas exact, mais c'est un bon départ.
    phi = math.atan2(Z, p)
    # Avec ce premier φ, on calcule N et une première hauteur h (fausse, mais suffisante pour démarrer).
    N = N_of(phi, a, e2)
    h = p / math.cos(phi) - N
    # On répète 50 fois au maximum, mais en pratique 4 ou 5 tours suffisent.
    for _ in range(50):
        # On recalcule φ en tenant compte du N et du h qu'on vient de trouver : c'est la correction.
        new = math.atan((Z / p) / (1 - e2 * N / (N + h)))
        # On remet N et h à jour avec ce nouveau φ, pour le tour suivant.
        N = N_of(new, a, e2)
        h = p / math.cos(new) - N
        # Si φ a à peine changé (moins de eps), la valeur est stable : on arrête la boucle.
        done = abs(new - phi) < eps * max(abs(new), 1e-12)
        phi = new
        if done:
            break
    return phi, math.atan2(Y, X), h


# Lit un angle tapé par la personne : en degrés décimaux (35.7595) ou en degrés-minutes-secondes
# (35 45 34.2 N, 5°50'01"W). Renvoie toujours des degrés décimaux.
def parse_angle(txt):
    # On met tout en majuscules, et la virgule devient un point.
    s = txt.strip().upper().replace(",", ".")
    # Les lettres S (sud), W ou O (ouest) veulent dire « angle négatif ».
    neg = bool(re.search(r"[SWO]", s))
    # On récupère les nombres écrits : un seul (décimal) ou trois (degrés, minutes, secondes).
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", re.sub(r"[NSEWO]", " ", s))
    if not 1 <= len(nums) <= 3:
        raise ValueError(f"angle illisible : « {txt} »")
    neg = neg or nums[0].startswith("-")
    # Conversion en degrés décimaux : degrés + minutes/60 + secondes/3600 (le 60**i vaut 1, puis 60, puis 3600).
    v = sum(abs(float(n)) / 60 ** i for i, n in enumerate(nums))
    return -v if neg else v


# L'inverse : de degrés décimaux vers degrés, minutes, secondes (plus lisible à l'écran).
def dms(x):
    sg, x = ("-" if x < 0 else ""), abs(x)
    d = int(x)
    m = int((x - d) * 60)
    return f"{sg}{d}° {m:02d}' {(x - d - m / 60) * 3600:06.3f}\""


# ====================================================================== 2. LE GLOBE
# Contours des continents, très simplifiés (longitude, latitude), notés à la main.
# Ce n'est pas précis du tout : c'est juste pour se repérer sur le globe.
CONTINENTS = [
    # Afrique
    [(-17, 21), (-13, 28), (-9.5, 32), (-6, 35.8), (-2, 35), (3, 36.8), (10, 37.2), (11, 33), (15, 32),
     (20, 31), (25, 32), (32, 31.2), (34, 28), (37, 22), (39, 16), (43, 12), (51, 12), (48, 5), (41, -2),
     (39, -7), (40, -15), (35, -24), (32, -29), (27, -34), (20, -35), (18, -32), (14, -23), (12, -14),
     (13, -6), (9, -1), (9.5, 4), (5, 6), (-2, 5), (-8, 4.5), (-13, 8), (-17, 14.5)],
    # Eurasie
    [(-9, 37), (-9, 43), (-2, 43.5), (-1.5, 46), (-4.5, 48.5), (2, 51), (5, 53.5), (8, 55), (10, 57.5),
     (12, 56), (14, 54.5), (20, 54.5), (24, 57), (30, 60), (23, 60), (21, 64), (25, 65.5), (18, 69),
     (28, 71), (40, 67), (44, 68), (60, 69), (70, 73), (90, 76), (110, 77), (130, 72), (160, 70),
     (180, 69), (180, 65), (170, 60), (163, 58), (156, 51), (142, 59), (135, 54), (141, 48), (130, 42),
     (129, 35), (126, 35), (125, 40), (121, 40), (122, 37), (119, 35), (122, 31), (121, 28), (117, 23),
     (110, 21), (107, 17), (109, 12), (105, 9), (101, 13), (100, 7), (103, 2), (98, 8), (97, 17),
     (94, 17), (92, 22), (88, 22), (80, 15), (77, 8), (73, 17), (72, 21), (67, 24), (62, 25), (57, 26),
     (56.5, 27), (52, 28), (48, 30), (50, 27), (56, 25), (59, 22.5), (55, 17), (52, 16), (45, 13),
     (43, 13), (39, 21), (35, 28), (34.5, 31), (36, 36), (30, 36.5), (27, 37), (26, 40), (23, 40.5),
     (23, 37), (21, 38), (19.5, 41), (13.5, 45.5), (12.3, 44.5), (16, 41.5), (18.5, 40), (16, 38),
     (15.5, 40), (12, 42), (9, 44.3), (4, 43.4), (3, 42), (0, 39), (-1, 37.5), (-5, 36)],
    # Amérique du Nord
    [(-168, 66), (-165, 69), (-155, 71), (-140, 70), (-128, 70), (-115, 68), (-95, 72), (-85, 69),
     (-82, 63), (-93, 59), (-92, 57), (-85, 55), (-80, 51), (-78, 58), (-78, 62), (-70, 60), (-65, 60),
     (-62, 57), (-56, 52), (-60, 47), (-66, 45), (-70, 43), (-70, 41.5), (-74, 40), (-76, 37), (-76, 35),
     (-81, 31), (-80, 26), (-81, 25.5), (-83, 29), (-85, 30), (-90, 29), (-94, 29.5), (-97, 27),
     (-97.5, 22), (-95, 18.5), (-91, 19), (-90, 21), (-87, 21), (-88, 16), (-84, 15.5), (-83, 11),
     (-80, 9), (-77.5, 8.5), (-80, 7.5), (-82, 8), (-85, 10), (-87, 13), (-92, 14.5), (-96, 15.7),
     (-102, 18), (-105.5, 20), (-105.5, 23), (-109, 26), (-112.5, 29.5), (-114.5, 31), (-113, 28),
     (-110, 23), (-112, 25), (-115, 28), (-117, 32.5), (-120.5, 34.5), (-122.5, 37.5), (-124, 40.5),
     (-124, 46), (-124.5, 48), (-128, 51), (-133, 55), (-138, 59), (-145, 60.5), (-152, 59), (-158, 57),
     (-163, 55), (-158, 58.5), (-162, 60), (-165, 62), (-161, 64.5)],
    # Amérique du Sud
    [(-77, 8.5), (-72, 12), (-65, 10.5), (-60, 8.5), (-52, 5), (-50, 0), (-44, -2.5), (-35, -5.5),
     (-35, -9), (-39, -15), (-41, -22), (-48, -26), (-48.5, -28), (-53, -34), (-58, -34.5), (-57, -38),
     (-62, -39), (-65, -41), (-64, -45), (-67.5, -46.5), (-69, -51), (-68.5, -54), (-72, -53.5),
     (-75, -50), (-74, -44), (-73.5, -37), (-71.5, -30), (-70.5, -18), (-76, -14), (-81, -5), (-80, -1),
     (-78.5, 2), (-77.5, 7)],
    # Australie
    [(114, -22), (122, -18), (130, -12), (136, -12), (137, -16), (141, -12), (143, -14), (146, -19),
     (153, -26), (151, -34), (150, -37.5), (146, -39), (141, -38), (138, -35), (135, -34.5), (131, -31.5),
     (124, -33.5), (115, -34), (115, -30), (113, -26)],
    # Groenland
    [(-73, 78), (-60, 82), (-30, 83.5), (-20, 80), (-18, 75), (-22, 70), (-33, 66), (-42, 60), (-50, 63),
     (-54, 67), (-58, 75)],
]


# Ce point est-il à l'intérieur de ce contour ? L'astuce : on trace une droite horizontale depuis
# le point et on compte combien de fois elle traverse le contour. Impair = dedans, pair = dehors.
def _inside(lon, lat, poly):
    ins, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            ins = not ins
        j = i
    return ins


# Donne un « type de terrain » à un point d'après sa position, donc une couleur :
#   0 = glace, 1 = désert, 2 = terre rouge (Australie), 3 = forêt tropicale,
#   4 = plaines tempérées, 5 = forêt du nord.
# C'est très approximatif : ça sert uniquement à colorer le globe.
def land_cat(lat, lon):
    if lat < -66 or lat > 68:
        return 0
    if 14 < lat < 32 and -16 < lon < 60:
        return 1
    if 36 < lat < 46 and 88 < lon < 112:
        return 1
    if 25 < lat < 37 and -118 < lon < -103:
        return 1
    if -30 < lat < -17 and 14 < lon < 26:
        return 1
    if -33 < lat < -18 and 115 < lon < 142:
        return 2
    if abs(lat) < 12:
        return 3
    if lat > 52:
        return 5
    return 4


# On quadrille toute la Terre avec des points régulièrement espacés, et on garde seulement ceux
# qui tombent sur un continent. Ce sont ces points qu'on affiche sur le globe.
def build_land_dots(step=2.2):
    dots = []
    lat = -88.0
    while lat <= 88:
        # Près des pôles les méridiens se rapprochent : on met moins de points pour garder un espacement régulier.
        n = max(1, int(360 / step * math.cos(math.radians(lat))))
        for i in range(n):
            lon = -180 + 360 * (i + 0.5) / n
            # Un point est « sur terre » s'il est dans un continent, ou en Antarctique (sous 72° sud, qu'on n'a pas dessiné).
            if lat < -72 or any(_inside(lon, lat, p) for p in CONTINENTS):
                la, lo = math.radians(lat), math.radians(lon)
                dots.append((math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la),
                             land_cat(lat, lon)))
        lat += step
    return dots


# ====================================================================== 3. LES COULEURS
# Pour changer l'apparence : modifier THEME un peu plus bas, ou lancer le programme avec le nom
# du thème :   python conversion_geodesique.py sombre
# Thèmes disponibles : sombre, clair, foret, violet, chaud.
# Chaque thème donne une couleur à tout : fond, cartes, champs, texte, globe, axes, quadrillage...
THEMES = {
    "sombre": dict(BG="#0f172a", CARD="#1b2740", FIELD="#0b1220", LINE="#334155", FG="#e5e9f0",
                   MUTED="#94a3b8", ACC="#2dd4bf", ERR="#f87171", OK="#34d399",
                   PALETTE=["#fbbf24", "#f472b6", "#60a5fa", "#a78bfa", "#34d399", "#fb923c"],
                   SPACE="#070d1a", SEL="#1f3a66", STAR="#9fb3d9", ACC_TXT="#04201c", HINT="#5b6b8c",
                   GRID="#5aa2d8", GRID_BACK="#1f3a5e", AX_X="#f87171", AX_Y="#4ade80", AX_Z="#60a5fa",
                   GUIDE="#8ea0c0", DISK="#0c1c38", DISK_EDGE="#2b4a7a", HILITE="#fbbf24",
                   HCOL="#ec4899", HALO="#38bdf8", GREENWICH="#f59e0b", LBL="#bfe0ff",
                   LABEL_BG="#0b1426", LAND_LO="#16424a", LAND_HI="#7ff0dc"),
    "clair": dict(BG="#eef2f7", CARD="#ffffff", FIELD="#f1f5f9", LINE="#cbd5e1", FG="#0f172a",
                  MUTED="#64748b", ACC="#0d9488", ERR="#dc2626", OK="#059669",
                  PALETTE=["#d97706", "#db2777", "#2563eb", "#7c3aed", "#059669", "#ea580c"],
                  SPACE="#dde7f5", SEL="#cfe3fb", STAR="#7b93bd", ACC_TXT="#ffffff", HINT="#64748b",
                  GRID="#6f9bd1", GRID_BACK="#c5d3ea", AX_X="#dc2626", AX_Y="#16a34a", AX_Z="#2563eb",
                  GUIDE="#64748b", DISK="#cfe0f7", DISK_EDGE="#8fb0dc", HILITE="#d97706",
                  HCOL="#db2777", HALO="#7fb4ee", GREENWICH="#c2410c", LBL="#1e3a5f",
                  LABEL_BG="#ffffff", LAND_LO="#b6d9d3", LAND_HI="#0f766e"),
    "foret": dict(BG="#0c1a14", CARD="#14271e", FIELD="#0a1510", LINE="#2c4a3b", FG="#e6f2ea",
                  MUTED="#8fb09f", ACC="#4ade80", ERR="#f87171", OK="#86efac",
                  PALETTE=["#facc15", "#f472b6", "#38bdf8", "#c084fc", "#fb923c", "#2dd4bf"],
                  SPACE="#06100b", SEL="#22503a", STAR="#a7d4b8", ACC_TXT="#052e16", HINT="#5f8573",
                  GRID="#4fa57a", GRID_BACK="#1c3a2c", AX_X="#f87171", AX_Y="#a3e635", AX_Z="#38bdf8",
                  GUIDE="#8fb09f", DISK="#0f2a1f", DISK_EDGE="#2f6b4d", HILITE="#facc15",
                  HCOL="#f472b6", HALO="#34d399", GREENWICH="#fb923c", LBL="#cdeedb",
                  LABEL_BG="#0a1510", LAND_LO="#1a5a3a", LAND_HI="#a7f3c4"),
    "violet": dict(BG="#14101f", CARD="#211a35", FIELD="#0f0b19", LINE="#3d3260", FG="#ece8f7",
                   MUTED="#a79fc4", ACC="#c084fc", ERR="#fb7185", OK="#86efac",
                   PALETTE=["#fbbf24", "#f472b6", "#60a5fa", "#34d399", "#fb923c", "#2dd4bf"],
                   SPACE="#0b0814", SEL="#3b2d66", STAR="#c4b5fd", ACC_TXT="#2e1065", HINT="#7a6fa3",
                   GRID="#8b6fd0", GRID_BACK="#2e2450", AX_X="#fb7185", AX_Y="#4ade80", AX_Z="#60a5fa",
                   GUIDE="#a79fc4", DISK="#1b1433", DISK_EDGE="#5b46a3", HILITE="#fbbf24",
                   HCOL="#f472b6", HALO="#a78bfa", GREENWICH="#fb923c", LBL="#e0d7fb",
                   LABEL_BG="#0f0b19", LAND_LO="#3a2a6b", LAND_HI="#d8b4fe"),
    "chaud": dict(BG="#1c1410", CARD="#2a1e17", FIELD="#150f0b", LINE="#4d3a2c", FG="#f5ece4",
                  MUTED="#b8a595", ACC="#fb923c", ERR="#f87171", OK="#a3e635",
                  PALETTE=["#fde047", "#f472b6", "#60a5fa", "#a78bfa", "#34d399", "#2dd4bf"],
                  SPACE="#0f0a07", SEL="#5a3d27", STAR="#e8c9ab", ACC_TXT="#2b1300", HINT="#8c7561",
                  GRID="#c08a5c", GRID_BACK="#3a2a1f", AX_X="#f87171", AX_Y="#a3e635", AX_Z="#60a5fa",
                  GUIDE="#b8a595", DISK="#241a13", DISK_EDGE="#7a5632", HILITE="#fde047",
                  HCOL="#f472b6", HALO="#fdba74", GREENWICH="#38bdf8", LBL="#fde8d2",
                  LABEL_BG="#150f0b", LAND_LO="#5a3a22", LAND_HI="#fdba74"),
}
# (LAND_LO et LAND_HI ne servent plus : les continents ont leurs propres couleurs, voir LAND_BASE.)
# Thème par défaut, remplacé par celui donné au lancement s'il existe.
THEME = "clair"
if len(sys.argv) > 1 and sys.argv[1] in THEMES:
    THEME = sys.argv[1]
# Après cette ligne, BG, CARD, FG, ACC... sont de simples variables utilisables partout.
globals().update(THEMES[THEME])


# Mélange deux couleurs : t = 0 donne la première, t = 1 la seconde, entre les deux un dégradé.
def blend(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# Couleur de base de chaque type de terrain : glace, désert, terre rouge, tropical, tempéré, forêt du nord.
LAND_BASE = ["#eef5fb", "#e0b862", "#d9763f", "#1f9d45", "#7cc04a", "#2f7a5c"]
# Pour chaque couleur, 12 nuances préparées à l'avance : vive au centre du globe, fondue dans l'océan sur les bords (effet de relief).
LAND_SHADES = [[blend(DISK, col, 0.30 + 0.70 * i / 11) for i in range(12)] for col in LAND_BASE]
# Couleurs de l'océan : sombre sur le bord, plus claire au centre.
OCEAN_EDGE = blend(DISK, "#06214f", 0.55)
OCEAN_CENTER = blend(DISK, "#2f8cf0", 0.65)


# ====================================================================== 4. LA FENÊTRE
# La classe App est la fenêtre du programme : la conversion à gauche, le globe à droite.
class App(tk.Tk):
    def __init__(self):
        # On crée la fenêtre, avec son titre et ses marges.
        super().__init__()
        self.title("Conversion de coordonnées géodésiques")
        self.configure(bg=BG, padx=16, pady=14)
        # Variables reliées aux champs : ellipsoïde choisi, valeurs de a et b, méthode utilisée pour ←.
        self.var_ell = tk.StringVar(value="Clarke 1880 (Merchich)")
        self.var_a, self.var_b = tk.StringVar(), tk.StringVar()
        self.var_meth = tk.StringVar(value="Itérative")

        # --- Ce qu'il faut pour dessiner le globe ---
        # Les points de terre, calculés une seule fois au démarrage.
        self.land = build_land_dots()
        # La liste des points convertis : (φ, λ, couleur). À côté, on garde h et (X, Y, Z) pour les afficher sur le schéma.
        self.points = []
        self.hs, self.xyz = [], []
        # Comment on regarde le globe : spin = rotation autour de l'axe des pôles, tilt = inclinaison (vers nous ou vers l'arrière).
        self.spin, self.tilt = random.uniform(0, 6.28), 0.3
        # follow = la vue se tourne toute seule vers le point choisi ; dragging = on est en train de glisser la souris.
        self.follow, self.dragging = False, False
        # focus = numéro du point choisi (None tant qu'il n'y en a pas).
        self.focus = None
        # _last = dernière position de la souris ; cw/ch = taille du dessin ; born = moment où le dernier point est apparu (pour le faire « battre »).
        self._last = (0, 0)
        self.cw = self.ch = 440
        self.born = 0.0

        # Couleurs des listes déroulantes, pour qu'elles suivent le thème.
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("TCombobox", fieldbackground=FIELD, background=CARD, foreground=FG,
                     arrowcolor=ACC, bordercolor=LINE, lightcolor=CARD, darkcolor=CARD)
        st.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", FG)])
        self.option_add("*TCombobox*Listbox.background", FIELD)
        self.option_add("*TCombobox*Listbox.foreground", FG)

        # --- Barre du haut : choix de l'ellipsoïde, avec ses valeurs a et b ---
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", pady=(0, 12))
        tk.Label(top, text="Ellipsoïde", bg=BG, fg=MUTED).pack(side="left")
        cb = ttk.Combobox(top, textvariable=self.var_ell, state="readonly", width=22,
                          values=list(ELLIPSOIDES) + ["Personnalisé"])
        cb.pack(side="left", padx=(8, 18))
        cb.bind("<<ComboboxSelected>>", lambda e: self.maj_ell())
        tk.Label(top, text="a", bg=BG, fg=MUTED).pack(side="left")
        self.e_a = self.entry(top, 13, self.var_a)
        self.e_a.pack(side="left", padx=(5, 12))
        tk.Label(top, text="b", bg=BG, fg=MUTED).pack(side="left")
        self.e_b = self.entry(top, 13, self.var_b)
        self.e_b.pack(side="left", padx=5)

        # --- Sous la barre, deux colonnes : la conversion à gauche (elle s'étire), le globe à droite ---
        cols = tk.Frame(self, bg=BG)
        cols.pack(fill="both", expand=True)
        left = tk.Frame(cols, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(cols, bg=BG)
        right.pack(side="left", fill="y", padx=(14, 0))

        # --- La carte de conversion : (φ, λ, h)  ⇄  (X, Y, Z) ---
        # On remplit un côté, puis on clique sur la flèche qui va vers l'autre côté.
        # Tous les champs sont modifiables : on peut donc réutiliser un résultat tel quel.
        c = self.card(left, "(φ, λ, h)   ⇄   (X, Y, Z)")
        c.pack(fill="both", expand=True)
        # Un cadre, centré dans la carte, qui contient trois colonnes : φ λ h | flèches | X Y Z.
        body = tk.Frame(c, bg=CARD)
        body.pack(expand=True)

        # Colonne de gauche : latitude, longitude, hauteur. (Entrée dans un de ces champs = conversion →)
        g = tk.Frame(body, bg=CARD)
        g.pack(side="left", anchor="n")
        self.phi = self.field(g, "φ  (°)", self.to_xyz)
        self.lam = self.field(g, "λ  (°)", self.to_xyz)
        self.h = self.field(g, "h  (m)", self.to_xyz)
        tk.Label(g, text="Décimal ou DMS (35 45 34.2 N)", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 0))
        self.dms_lbl = tk.Label(g, text="", bg=CARD, fg=ACC, font=("Consolas", 12, "bold"),
                                justify="left", anchor="w")
        self.dms_lbl.pack(anchor="w", pady=(8, 0))

        # Colonne du milieu : les deux flèches (petites, centrées) et le choix de la méthode pour ←.
        outer = tk.Frame(body, bg=CARD)
        outer.pack(side="left", padx=20, fill="y")
        mid = tk.Frame(outer, bg=CARD)
        mid.pack(expand=True)
        for txt, cmd in (("→", self.to_xyz), ("←", self.to_geo)):
            tk.Button(mid, text=txt, command=cmd, bg=ACC, fg=ACC_TXT, relief="flat",
                      font=("Segoe UI", 15, "bold"), cursor="hand2", width=3,
                      activebackground=blend(ACC, "#ffffff", 0.3)).pack(pady=5)
        tk.Label(mid, text="Méthode (←)", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 10)).pack(pady=(12, 2))
        ttk.Combobox(mid, textvariable=self.var_meth, state="readonly", width=10,
                     values=["Directe", "Itérative"]).pack()

        # Colonne de droite : X, Y, Z. (Entrée dans un de ces champs = conversion ←)
        k = tk.Frame(body, bg=CARD)
        k.pack(side="left", anchor="n")
        self.X = self.field(k, "X  (m)", self.to_geo)
        self.Y = self.field(k, "Y  (m)", self.to_geo)
        self.Z = self.field(k, "Z  (m)", self.to_geo)

        # --- Le panneau du globe : boutons de vue, zone de dessin, liste des points ---
        gf = tk.Frame(right, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        gf.pack()
        # La vue affichée : « schema » (schéma géodésique) ou « terre » (le globe).
        self.mode = tk.StringVar(value="schema")
        mb = tk.Frame(gf, bg=CARD)
        mb.pack(fill="x", padx=8, pady=(6, 2))
        for txt, val in (("Schéma géodésique", "schema"), ("Terre", "terre")):
            tk.Radiobutton(mb, text=txt, variable=self.mode, value=val, indicatoron=0, bg=CARD,
                           fg=MUTED, selectcolor=SEL, activebackground=CARD, relief="flat",
                           bd=0, padx=10, pady=3, cursor="hand2").pack(side="left", padx=(0, 6))
        # La case « Lat / Long » (montrer le quadrillage) et le pas du quadrillage (10°, 15° ou 30°).
        self.var_grid = tk.BooleanVar(value=True)
        self.var_pas = tk.StringVar(value="15°")
        tk.Checkbutton(mb, text="Lat / Long", variable=self.var_grid, bg=CARD, fg=FG,
                       selectcolor=FIELD, activebackground=CARD, activeforeground=ACC, bd=0,
                       highlightthickness=0).pack(side="left", padx=(10, 4))
        ttk.Combobox(mb, textvariable=self.var_pas, values=["10°", "15°", "30°"], width=4,
                     state="readonly").pack(side="left")
        # La zone de dessin : tout le globe est redessiné ici, environ 30 fois par seconde.
        self.canvas = tk.Canvas(gf, width=440, height=440, bg=SPACE, highlightthickness=0,
                                cursor="fleur")
        self.canvas.pack()
        # Souris : appuyer, glisser, relâcher = faire tourner le globe à la main.
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "dragging", False))
        # Fond uni (couleur SPACE du thème) + 70 petites étoiles placées au hasard.
        # Elles sont dessinées une seule fois : sans le tag « fx », le redessin ne les efface pas.
        for x, y, s in [(random.random(), random.random(), random.random()) for _ in range(70)]:
            r = 0.6 + s
            self.canvas.create_oval(x * 440 - r, y * 440 - r, x * 440 + r, y * 440 + r,
                                    fill=blend(SPACE, STAR, 0.25 + 0.5 * s), width=0)
        # Le titre de la liste + le bouton « Effacer ».
        bar = tk.Frame(gf, bg=CARD)
        bar.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(bar, text="Points convertis", bg=CARD, fg=ACC,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(bar, text="Effacer", command=self.effacer, bg=CARD, fg=MUTED, relief="flat",
                  bd=0, cursor="hand2", activebackground=CARD).pack(side="right")
        # La liste des points convertis. Cliquer sur une ligne tourne la vue vers ce point.
        self.lb = tk.Listbox(gf, height=5, bg=FIELD, fg=FG, relief="flat", bd=0,
                             font=("Consolas", 9), selectbackground=SEL, selectforeground=FG,
                             highlightthickness=0, activestyle="none")
        self.lb.pack(fill="x", padx=8, pady=(0, 8))
        self.lb.bind("<<ListboxSelect>>", self._select)

        # La ligne d'état, tout en bas : message vert si tout va bien, rouge en cas d'erreur.
        self.status = tk.Label(self, text="", bg=BG, fg=MUTED, anchor="w")
        self.status.pack(fill="x", pady=(10, 0))
        # On remplit a et b avec l'ellipsoïde par défaut, puis on lance l'animation.
        self.maj_ell()
        self.tick()

    # ------------------------------------------------------------ petits outils
    # Ces fonctions évitent de recopier le même code pour chaque champ, bouton, etc.
    # Crée un champ de saisie aux couleurs du thème (size = taille du texte).
    def entry(self, parent, width, var=None, size=11):
        return tk.Entry(parent, width=width, textvariable=var, bg=FIELD, fg=FG, relief="flat",
                        insertbackground=ACC, font=("Consolas", size), highlightthickness=1,
                        highlightbackground=LINE, highlightcolor=ACC)

    # Crée une « carte » : un cadre avec une bordure et un titre en couleur.
    def card(self, parent, titre):
        f = tk.Frame(parent, bg=CARD, padx=26, pady=22, highlightbackground=LINE,
                     highlightthickness=1)
        tk.Label(f, text=titre, bg=CARD, fg=ACC, font=("Segoe UI", 16, "bold")).pack(
            anchor="w", pady=(0, 14))
        return f

    # Crée une ligne « nom + champ de saisie ». La fonction cmd est lancée quand on appuie sur Entrée.
    def field(self, parent, label, cmd):
        r = tk.Frame(parent, bg=CARD)
        r.pack(fill="x", pady=9)
        tk.Label(r, text=label, bg=CARD, fg=MUTED, width=7, anchor="w",
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        e = self.entry(r, 17, size=15)
        e.pack(side="left", ipady=9)
        e.bind("<Return>", lambda ev: cmd())
        return e

    # Écrit une valeur dans un champ. Un résultat calculé s'affiche en couleur d'accent, pour le distinguer de ce qu'on a tapé soi-même.
    @staticmethod
    def put(e, txt, out=True):
        e.delete(0, "end")
        e.insert(0, txt)
        e.config(fg=ACC if out else FG)

    # Affiche un message en bas : ✔ vert si ça va, ✖ rouge sinon.
    def say(self, msg, ok=True):
        self.status.config(text=("✔ " if ok else "✖ ") + msg, fg=OK if ok else ERR)

    # ------------------------------------------------------------ la logique
    # Quand on change d'ellipsoïde, on affiche ses valeurs a et b.
    # On ne peut les modifier à la main que si on choisit « Personnalisé ».
    def maj_ell(self):
        nom = self.var_ell.get()
        if nom in ELLIPSOIDES:
            a, b = ELLIPSOIDES[nom]
            self.var_a.set(repr(a))
            self.var_b.set(repr(b))
            for e in (self.e_a, self.e_b):
                e.config(state="readonly", readonlybackground=FIELD, fg=MUTED)
        else:
            for e in (self.e_a, self.e_b):
                e.config(state="normal", fg=FG)

    # Lit a et b et vérifie qu'ils ont du sens : des nombres, avec a plus grand que b.
    def ab(self):
        try:
            a = float(self.var_a.get().replace(",", "."))
            b = float(self.var_b.get().replace(",", "."))
        except ValueError:
            raise ValueError("a et b doivent être numériques")
        if not a > b > 0:
            raise ValueError("il faut a > b > 0")
        return a, b

    # Lit un nombre dans un champ (la virgule marche comme le point). Message clair si ce n'est pas un nombre.
    @staticmethod
    def num(e):
        try:
            return float(e.get().replace(",", ".").strip())
        except ValueError:
            raise ValueError("valeur numérique invalide")

    # Flèche → : on lit φ, λ, h, on calcule X, Y, Z, on les écrit à droite, et on ajoute le point au globe.
    def to_xyz(self):
        try:
            a, b = self.ab()
            phi, lam = parse_angle(self.phi.get()), parse_angle(self.lam.get())
            h = self.num(self.h)
            # Une latitude va de -90° à 90°, une longitude de -180° à 180°.
            if abs(phi) > 90 or abs(lam) > 180:
                raise ValueError("φ ∈ [-90°, 90°] et λ ∈ [-180°, 180°]")
            # On tape des degrés, mais les formules veulent des radians : on convertit.
            X, Y, Z = geo_to_cart(math.radians(phi), math.radians(lam), h, a, b)
        except ValueError as err:
            return self.say(f"→ {err}", False)
        # On écrit les résultats dans les champs de droite...
        for e, v in zip((self.X, self.Y, self.Z), (X, Y, Z)):
            self.put(e, f"{v:.4f}")
        # ...et ce qu'on a tapé à gauche reprend la couleur normale.
        for e in (self.phi, self.lam, self.h):
            e.config(fg=FG)
        # On rappelle φ et λ en degrés-minutes-secondes.
        self.dms_lbl.config(text=f"φ = {dms(phi)}\nλ = {dms(lam)}")
        self.ajouter_point(math.radians(phi), math.radians(lam), "→", h, (X, Y, Z))
        self.say("Conversion (φ, λ, h) → (X, Y, Z) effectuée.")

    # Flèche ← : on lit X, Y, Z, on calcule φ, λ, h avec la méthode choisie, on les écrit à gauche, et on ajoute le point au globe.
    def to_geo(self):
        try:
            a, b = self.ab()
            X, Y, Z = self.num(self.X), self.num(self.Y), self.num(self.Z)
            # Si X et Y valent 0, on est pile sur l'axe des pôles : la longitude n'a plus de sens.
            # On refuse ce cas avec un message.
            if math.hypot(X, Y) < 1e-6:
                raise ValueError("cas des pôles (X = Y = 0) non traité")
            # On prend la méthode demandée : directe ou itérative.
            f = cart_to_geo_directe if self.var_meth.get() == "Directe" else cart_to_geo_iterative
            phi, lam, h = f(X, Y, Z, a, b)
        except ValueError as err:
            return self.say(f"← {err}", False)
        # Les calculs donnent des radians : on remet en degrés pour l'affichage.
        p, l = math.degrees(phi), math.degrees(lam)
        self.put(self.phi, f"{p:.9f}")
        self.put(self.lam, f"{l:.9f}")
        self.put(self.h, f"{h:.4f}")
        # ...et ce qu'on a tapé à droite reprend la couleur normale.
        for e in (self.X, self.Y, self.Z):
            e.config(fg=FG)
        # On rappelle φ et λ en degrés-minutes-secondes.
        self.dms_lbl.config(text=f"φ = {dms(p)}\nλ = {dms(l)}")
        self.ajouter_point(phi, lam, "←", h, (X, Y, Z))
        self.say("Conversion (X, Y, Z) → (φ, λ, h) effectuée.")

    # ------------------------------------------------------------ les points sur la Terre
    # On enregistre le point converti : on lui donne une couleur, on l'ajoute à la liste sous le
    # globe, et la vue se tourne vers lui.
    def ajouter_point(self, phi, lam, op, h=0.0, xyz=(0.0, 0.0, 0.0)):
        col = PALETTE[len(self.points) % len(PALETTE)]
        self.points.append((phi, lam, col))
        self.hs.append(h)
        self.xyz.append(xyz)
        n = len(self.points)
        self.lb.insert("end", f"{n:>2} {op}  φ={math.degrees(phi):9.4f}°  λ={math.degrees(lam):10.4f}°")
        self.lb.itemconfig("end", fg=col)
        self.lb.see("end")
        self.focus, self.follow, self.born = n - 1, True, time.time()

    # Vide la liste et enlève les points du globe.
    def effacer(self):
        self.points.clear()
        self.hs.clear()
        self.xyz.clear()
        self.lb.delete(0, "end")
        self.focus, self.follow = None, False

    # Un clic sur une ligne de la liste : la vue se tourne vers ce point.
    def _select(self, ev):
        s = self.lb.curselection()
        if s:
            self.focus, self.follow, self.born = s[0], True, time.time()

    # On appuie sur la souris : on arrête le suivi automatique, pour laisser la personne tourner le globe elle-même.
    def _press(self, ev):
        self.dragging, self._last, self.follow = True, (ev.x, ev.y), False

    # La souris bouge bouton enfoncé : de gauche à droite le globe tourne autour des pôles, de haut en bas il s'incline.
    def _drag(self, ev):
        dx, dy = ev.x - self._last[0], ev.y - self._last[1]
        self._last = (ev.x, ev.y)
        self.spin += dx * 0.01
        self.tilt = max(-1.4, min(1.4, self.tilt + dy * 0.01))

    # ------------------------------------------------------------ le dessin du globe
    # On calcule une seule fois par image les cos et sin de la rotation, pour ne pas les refaire à chaque point.
    def _rot(self):
        return (math.cos(self.spin), math.sin(self.spin), math.cos(self.tilt), math.sin(self.tilt))

    # Transforme un point 3D en position sur l'écran (2D) : on le tourne autour de l'axe Z, on l'incline,
    # puis on garde x et z comme position. La 3e valeur (la profondeur) dit si le point est devant
    # le globe (négatif) ou derrière.
    @staticmethod
    def _proj(x, y, z, r, k, cx, cy):
        cs, sn, ct, st = r
        xp, yp = x * cs - y * sn, x * sn + y * cs
        return cx + k * xp, cy - k * (yp * st + z * ct), yp * ct - z * st

    # Trace une ligne en gardant seulement la partie visible, c'est-à-dire celle du côté tourné vers nous.
    def _lines(self, c, pts_list, front_col, back_col, wf=1):
        for pts in pts_list:
            cur, vis = [], None
            for x, y, d in pts:
                v = d < 0
                if vis is None:
                    cur, vis = [(x, y)], v
                elif v == vis:
                    cur.append((x, y))
                else:
                    cur.append((x, y))
                    if vis:
                        c.create_line(*[q for p in cur for q in p], fill=front_col, width=wf, tags="fx")
                    cur, vis = [(x, y)], v
            if len(cur) > 1 and vis:
                c.create_line(*[q for p in cur for q in p], fill=front_col, width=wf, tags="fx")

    # Redessine la vue choisie : schéma géodésique ou Terre.
    def draw(self):
        (self.draw_schema if self.mode.get() == "schema" else self.draw_terre)()

    # Le schéma « pédagogique » : pour un point P, il montre l'ellipsoïde, les axes X Y Z, la normale,
    # les angles φ et λ, la hauteur h, et les projections de P sur les axes.
    def draw_schema(self):
        c = self.canvas
        c.delete("fx")
        cx, cy, k = 220, 218, 150
        # Tant qu'il n'y a aucun point, on affiche juste un petit message d'invitation.
        if not self.points:
            c.create_text(cx, cy, fill=HINT, font=("Segoe UI", 11), tags="fx", justify="center",
                          text="Faites une conversion → ou ←\npour voir le point sur l'ellipsoïde")
            return
        # i = le point à dessiner : le point choisi, sinon le dernier converti.
        i = self.focus if self.focus is not None else len(self.points) - 1
        phi, lam, col = self.points[i]
        hh, (X, Y, Z) = self.hs[i], self.xyz[i]
        try:
            a, b = self.ab()
        except ValueError:
            return
        # Pour le dessin, on prend un ellipsoïde de rayon 1 et on exagère son aplatissement ×40, sinon
        # on ne verrait pas qu'il est aplati (il ne l'est que de 0,3 %).
        # Attention : seul le dessin est exagéré, les nombres affichés sont exacts.
        f = (a - b) / a
        bd = max(0.4, 1 - 40 * f)
        e2d = 1 - bd * bd
        # Le même N que plus haut, mais pour l'ellipsoïde dessiné.
        Nd = 1 / math.sqrt(1 - e2d * math.sin(phi) ** 2)
        # n = la normale en P : la direction « perpendiculaire à la surface », écrite avec φ et λ.
        n = (math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi))
        # P0 = le point sur la surface de l'ellipsoïde (c'est la conversion → avec h = 0).
        P0 = tuple(Nd * n[j] * ((1 - e2d) if j == 2 else 1) for j in range(3))
        # P = P0 décalé le long de la normale. Sur le dessin, h a toujours la même petite longueur, sinon on ne le verrait pas.
        P = tuple(P0[j] + 0.16 * n[j] for j in range(3))
        # r = la rotation actuelle ; pr(...) place un point 3D à l'écran.
        r = self._rot()
        pr = lambda v: self._proj(v[0], v[1], v[2], r, k, cx, cy)
        # Raccourcis de couleurs : quadrillage devant / derrière, et couleurs des axes X, Y, Z.
        WIRE, BACK, CX, CY, CZ = GRID, GRID_BACK, AX_X, AX_Y, AX_Z
        GREY = GUIDE

        # seg : trace une courbe segment par segment. Un segment est « devant » s'il est du côté visible du globe.
        # only=True : seulement l'avant ; only=False : seulement l'arrière ; None : tout.
        # La partie arrière est tracée plus fine et plus discrète.
        def seg(pts, fc, bc, wf=1.0, only=None):
            prev = None
            for q in pts:
                if prev:
                    A, B = pr(prev), pr(q)
                    fr = (A[2] + B[2]) / 2 < 0
                    if only is None or only == fr:
                        c.create_line(A[0], A[1], B[0], B[1], fill=fc if fr else bc,
                                      width=wf if fr else 1, tags="fx")
                prev = q

        # ln : trace une ligne droite entre deux points 3D (dash = pointillés).
        def ln(p1, p2, colr, wd=1.0, dash=None):
            A, B = pr(p1), pr(p2)
            c.create_line(A[0], A[1], B[0], B[1], fill=colr, width=wd, dash=dash, tags="fx")

        # tx : écrit un texte à côté d'un point 3D (dx, dy = petit décalage en pixels).
        def tx(t, v, colr, dx=6, dy=-6, size=10):
            A = pr(v)
            c.create_text(A[0] + dx, A[1] + dy, text=t, fill=colr, anchor="w",
                          font=("Segoe UI", size, "bold"), tags="fx")

        # mer(L) = un méridien (longitude L), de pôle à pôle. par(t) = un parallèle (latitude t).
        # Dans les deux cas, z est multiplié par bd : c'est ce qui aplatit l'ellipsoïde.
        mer = lambda L: [(math.cos(math.radians(t)) * math.cos(L), math.cos(math.radians(t)) * math.sin(L),
                          bd * math.sin(math.radians(t))) for t in range(-90, 91, 4)]
        par = lambda t: [(math.cos(math.radians(t)) * math.cos(math.radians(L)),
                          math.cos(math.radians(t)) * math.sin(math.radians(L)),
                          bd * math.sin(math.radians(t))) for L in range(0, 361, 5)]
        # Le disque de fond de l'ellipsoïde : plus on l'incline, plus il paraît plat.
        c.create_oval(cx - k, cy - k * math.sqrt((bd * math.cos(self.tilt)) ** 2 + math.sin(self.tilt) ** 2),
                      cx + k, cy + k * math.sqrt((bd * math.cos(self.tilt)) ** 2 + math.sin(self.tilt) ** 2),
                      fill=DISK, outline=DISK_EDGE, tags="fx")
        # Le pas du quadrillage en degrés (« 15° » devient 15).
        st = int(self.var_pas.get().rstrip("°"))
        # Toutes les courbes du quadrillage (méridiens + parallèles) ; liste vide si la case est décochée.
        grid = ([mer(math.radians(L)) for L in range(0, 360, st)]
                + [par(t) for t in range(-90 + st, 90, st)]) if self.var_grid.get() else []
        # 1) Le quadrillage de l'arrière, dessiné en premier donc tout au fond.
        for g in grid:
            seg(g, WIRE, BACK, only=False)
        # 2) Les axes X, Y, Z : un trait depuis le centre, avec sa lettre au bout.
        for ax, ay, az, t, cc in ((1.38, 0, 0, "X", CX), (0, 1.38, 0, "Y", CY), (0, 0, 1.3, "Z", CZ)):
            ln((0, 0, 0), (ax, ay, az), cc, 1.6)
            tx(t, (ax * 1.05, ay * 1.05, az * 1.05), cc, 3, 3, 12)
        # 3) Le quadrillage de l'avant, par-dessus les axes.
        for g in grid:
            seg(g, WIRE, BACK, only=True)
        # L'équateur, en couleur d'accent et plus épais.
        seg(par(0), ACC, ACC, 2, only=True)
        # Le méridien de P, puis l'arc qui montre l'angle λ sur l'équateur.
        seg(mer(lam), HILITE, HILITE, 2.2)
        seg([(math.cos(t * lam / 90), math.sin(t * lam / 90), 0) for t in range(91)], ACC, ACC, 3)
        tx("λ", (.55 * math.cos(lam / 2), .55 * math.sin(lam / 2), 0), ACC, 0, -6, 12)
        # Point intéressant : la verticale du lieu (la normale) ne passe pas par le centre de la Terre !
        # Elle coupe l'axe des pôles un peu plus bas, à z = -N·e²·sin φ. C'est de là qu'on mesure l'angle φ.
        ez = -Nd * e2d * math.sin(phi)
        A0, u = (0, 0, ez), (math.cos(lam), math.sin(lam), 0)
        # On trace la normale (de A0 jusqu'à P), la hauteur h (trait rose épais entre P0 et P) et l'arc de l'angle φ.
        ln(A0, P, HILITE, 2)
        ln(P0, P, HCOL, 4)
        seg([(A0[0] + .22 * math.cos(phi * j / 24) * u[0], A0[1] + .22 * math.cos(phi * j / 24) * u[1],
              ez + .22 * math.sin(phi * j / 24)) for j in range(25)], HILITE, HILITE, 2.5)
        ln(A0, (A0[0] + .3 * u[0], A0[1] + .3 * u[1], ez), GREY, 1, (3, 3))
        tx("φ", (A0[0] + .28 * math.cos(phi / 2) * u[0], A0[1] + .28 * math.cos(phi / 2) * u[1],
                 ez + .28 * math.sin(phi / 2)), HILITE, 2, 4, 12)
        # Le rayon du centre jusqu'à P0 : son angle avec l'équateur est la latitude géocentrique ψ,
        # un peu différente de φ à cause de l'aplatissement.
        ln((0, 0, 0), P0, GREY, 1.3, (5, 4))
        tx("ψ", tuple(.35 * v for v in P0), GREY, 4, -4, 11)
        # Les pointillés montrent comment on « lit » X, Y et Z : on descend de P jusqu'au plan de l'équateur,
        # puis on rejoint chaque axe.
        pe = (P0[0], P0[1], 0)
        ln(P0, pe, GREY, 1, (2, 3))
        ln(pe, (P0[0], 0, 0), GREY, 1, (2, 3))
        ln(pe, (0, P0[1], 0), GREY, 1, (2, 3))
        ln(P0, (0, 0, P0[2]), GREY, 1, (2, 3))
        # Les valeurs de X, Y, Z écrites sur chaque axe (un espace sépare les milliers).
        tx(f"X={X:,.0f}".replace(",", " "), (P0[0], 0, 0), CX, -30, 14, 9)
        tx(f"Y={Y:,.0f}".replace(",", " "), (0, P0[1], 0), CY, 6, 14, 9)
        tx(f"Z={Z:,.0f}".replace(",", " "), (0, 0, P0[2]), CZ, -80, -4, 9)
        # Le point P lui-même.
        px, py, _ = pr(P)
        # pulse va et vient entre 0 et 1 : c'est ce qui fait grossir et rétrécir le marqueur en continu.
        pulse = 0.5 + 0.5 * math.sin((time.time() - self.born) * 5)
        c.create_oval(px - 7 - 5 * pulse, py - 7 - 5 * pulse, px + 7 + 5 * pulse, py + 7 + 5 * pulse,
                      outline=blend(DISK, col, 0.7 * (1 - pulse)), width=2, tags="fx")
        c.create_oval(px - 5, py - 5, px + 5, py + 5, fill=col, outline="white", tags="fx")
        tx(f"P{i + 1}", P, col, 9, -9, 11)
        tx("h", tuple((P0[j] + P[j]) / 2 for j in range(3)), HCOL, 8, 10, 10)
        # Petit texte en bas : les valeurs exactes du point (×40 = aplatissement exagéré).
        c.create_text(10, 424, anchor="sw", fill=HINT, font=("Segoe UI", 8), tags="fx",
                      text=f"P{i + 1} :  φ {math.degrees(phi):.4f}°  λ {math.degrees(lam):.4f}°  h {hh:.2f} m"
                           "  ·  ×40")

    # La vue Terre : les continents (en points), les lignes de latitude et de longitude, et les points convertis.
    def draw_terre(self):
        c = self.canvas
        c.delete("fx")
        w = h = 440
        # cx, cy = le centre du globe à l'écran ; k = son rayon en pixels.
        cx, cy, k = w / 2, h / 2 - 2, 178
        r = self._rot()
        # Un halo lumineux autour du globe : trois grands cercles très transparents.
        for g, t in ((16, 0.05), (10, 0.09), (5, 0.15)):
            c.create_oval(cx - k - g, cy - k - g, cx + k + g, cy + k + g,
                          fill=blend(SPACE, HALO, t), width=0, tags="fx")
        # L'océan : un grand cercle sombre, puis des cercles de plus en plus petits et clairs, décalés
        # vers le haut-gauche. Ça imite la lumière sur une boule.
        c.create_oval(cx - k, cy - k, cx + k, cy + k, fill=OCEAN_EDGE, outline=DISK_EDGE, tags="fx")
        for j in range(1, 15):
            fr = j / 14
            rr = k * (1 - 0.82 * fr)
            ox, oy = -0.16 * k * fr, -0.16 * k * fr
            c.create_oval(cx + ox - rr, cy + oy - rr, cx + ox + rr, cy + oy + rr, width=0,
                          fill=blend(OCEAN_EDGE, OCEAN_CENTER, fr), tags="fx")

        # Les continents : on applique ici la même rotation que dans _proj, mais directement, pour aller plus vite.
        cs, sn, ct, st = r
        # Pour chaque point de terre : s'il est devant le globe (y2 < 0), on le dessine. Plus il est vers le centre, plus sa couleur est vive.
        for x, y, z, cat in self.land:
            yp = x * sn + y * cs
            y2 = yp * ct - z * st
            if y2 < 0:
                xp = x * cs - y * sn
                z2 = yp * st + z * ct
                px, py = cx + k * xp, cy - k * z2
                c.create_rectangle(px - 1.0, py - 1.0, px + 1.0, py + 1.0,
                                   fill=LAND_SHADES[cat][min(11, int(-y2 * 12))], width=0, tags="fx")

        # P(...) place un point 3D à l'écran ; sph(lat, lon) fait pareil à partir d'une latitude et d'une longitude en degrés.
        P = lambda x, y, z: self._proj(x, y, z, r, k, cx, cy)
        sph = lambda bb, L: P(math.cos(math.radians(bb)) * math.cos(math.radians(L)),
                              math.cos(math.radians(bb)) * math.sin(math.radians(L)),
                              math.sin(math.radians(bb)))
        # Le quadrillage et ses étiquettes (seulement si la case est cochée).
        if self.var_grid.get():
            st_ = int(self.var_pas.get().rstrip("°"))
            # lons = les longitudes à tracer ; lats = les latitudes (sans 0 : l'équateur est tracé à part, en gras).
            lons = list(range(-180, 180, st_))
            lats = [bb for bb in range(-90 + st_, 90, st_) if bb != 0]
            GR = GRID
            # Les méridiens, les parallèles, puis Greenwich (longitude 0) et l'équateur en plus épais.
            self._lines(c, [[sph(bb, L) for bb in range(-90, 91, 3)] for L in lons if L != 0], GR, None)
            self._lines(c, [[sph(bb, L) for L in range(-180, 181, 3)] for bb in lats], GR, None)
            self._lines(c, [[sph(bb, 0) for bb in range(-90, 91, 3)]], GREENWICH, None, 2)
            self._lines(c, [[sph(0, L) for L in range(-180, 181, 3)]], ACC, None, 2)
            # Les étiquettes de longitude, le long de l'équateur.
            fnt = ("Consolas", 8, "bold")
            for L in lons:
                x, y, d = sph(0, L)
                if d < -0.2:
                    t = f"{abs(L)}°{'E' if L > 0 else 'W' if L < 0 else ''}"
                    c.create_text(x, y + 9, text=t, fill=GREENWICH if L == 0 else LBL,
                                  font=fnt, tags="fx")
            # Les étiquettes de latitude : on les place le long du méridien qui est juste en face de nous.
            lc = math.degrees(-math.pi / 2 - self.spin)
            for bb in lats + [0]:
                x, y, d = sph(bb, lc)
                if d < -0.2:
                    t = "0° (équateur)" if bb == 0 else f"{abs(bb)}°{'N' if bb > 0 else 'S'}"
                    c.create_text(x + 5, y - 7, text=t, fill=ACC if bb == 0 else LBL,
                                  font=fnt, anchor="w", tags="fx")
            # Pour le point choisi : on trace son méridien et son parallèle, dans sa couleur.
            if self.focus is not None and self.points:
                fp, fl, fc = self.points[self.focus]
                self._lines(c, [[sph(bb, math.degrees(fl)) for bb in range(-90, 91, 3)]], fc, None, 2)
                self._lines(c, [[sph(math.degrees(fp), L) for L in range(-180, 181, 3)]], fc, None, 2)

        # Même effet de battement que sur le schéma, pour le point choisi.
        pulse = 0.5 + 0.5 * math.sin((time.time() - self.born) * 5)
        # Pour chaque point converti : sa direction, puis sa place à l'écran.
        # Devant le globe : un disque plein avec son numéro (et une étiquette pour le point choisi).
        # Derrière le globe : juste un petit cercle creux.
        for i, (phi, lam, col) in enumerate(self.points):
            n = (math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi))
            px, py, d = self._proj(*n, r, k, cx, cy)
            last = i == len(self.points) - 1 or i == self.focus
            if d < 0:
                if last:
                    rr = 7 + 6 * pulse
                    c.create_oval(px - rr, py - rr, px + rr, py + rr,
                                  outline=blend(DISK, col, 0.7 * (1 - pulse)), width=2, tags="fx")
                c.create_oval(px - 5, py - 5, px + 5, py + 5, fill=col, outline="white", tags="fx")
                c.create_text(px, py - 14, text=str(i + 1), fill=col,
                              font=("Segoe UI", 9, "bold"), tags="fx")
                if i == self.focus:
                    txt = f"{i + 1}   φ {math.degrees(phi):.4f}°   λ {math.degrees(lam):.4f}°"
                    tx = min(max(px + 12, 6), w - 250)
                    ty = min(max(py + 20, 18), h - 20)
                    c.create_rectangle(tx - 5, ty - 10, tx + 240, ty + 10, fill=LABEL_BG,
                                       outline=col, tags="fx")
                    c.create_text(tx, ty, text=txt, fill=col, anchor="w",
                                  font=("Consolas", 9, "bold"), tags="fx")
            else:
                c.create_oval(px - 4, py - 4, px + 4, py + 4,
                              outline=blend(DISK, col, 0.35), tags="fx")

        # Un rappel d'utilisation, en bas à gauche.
        c.create_text(10, h - 8, anchor="sw", fill=HINT, font=("Segoe UI", 8),
                      text="Glisser pour faire tourner  ·  équateur en turquoise", tags="fx")

    # La boucle d'animation : elle tourne environ 30 fois par seconde. À chaque tour, elle met à jour
    # l'orientation du globe puis le redessine. C'est ce qui donne le mouvement.
    def tick(self):
        # Si un point est choisi, on tourne doucement le globe pour l'amener face à nous.
        if self.follow and self.focus is not None and not self.dragging and self.points:
            phi, lam, _ = self.points[self.focus]
            # En vue schéma, on ajoute 1 radian de plus pour avoir une vue de biais, plus lisible.
            schema = self.mode.get() == "schema"
            target = -math.pi / 2 - lam + (1.0 if schema else 0.0)
            d = (target - self.spin + math.pi) % (2 * math.pi) - math.pi
            self.spin += d * 0.10
            tt = 0.45 if schema else max(-0.3, min(1.1, 0.3 + 0.5 * phi))
            self.tilt += (tt - self.tilt) * 0.08
        # Tant qu'il n'y a aucun point, le globe tourne tout doucement tout seul.
        elif not self.points and not self.dragging:
            self.spin += 0.006
        self.draw()
        self.after(33, self.tick)


# On lance le programme quand on exécute ce fichier.
if __name__ == "__main__":
    App().mainloop()
