#!/usr/bin/env python3
"""Simulation de l'exam_5 Python avec moulinette (style examshell 42).

Usage :
    python3 examshell.py            # démarre ou reprend l'examen
    python3 examshell.py --reset    # recommence un nouvel examen
    python3 examshell.py --duration 120 --no-flake8
"""
import argparse
import ast
import copy
import json
import os
import random
import shutil
import subprocess
import sys
import textwrap
import time
from collections import deque

BASE = os.path.dirname(os.path.abspath(__file__))
SUBJECTS = os.path.join(BASE, "subjects")
RENDU = os.path.join(BASE, "rendu")
TRACES = os.path.join(BASE, "traces")
STATE = os.path.join(BASE, ".exam_state.json")
TIMEOUT = 10
RANDOM_TESTS = 60


# ---------------------------------------------------------------------------
# Solutions de référence (servent à calculer les résultats attendus)
# ---------------------------------------------------------------------------

def ref_generate_spiral(n):
    if n <= 0:
        return []
    g = [[0] * n for _ in range(n)]
    top, bottom, left, right = 0, n - 1, 0, n - 1
    val = 1
    while val <= n * n:
        for c in range(left, right + 1):
            g[top][c] = val
            val += 1
        top += 1
        for r in range(top, bottom + 1):
            g[r][right] = val
            val += 1
        right -= 1
        for c in range(right, left - 1, -1):
            g[bottom][c] = val
            val += 1
        bottom -= 1
        for r in range(bottom, top - 1, -1):
            g[r][left] = val
            val += 1
        left += 1
    return g


def ref_compress(s):
    out = ""
    i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        out += s[i] + (str(j - i) if j - i > 1 else "")
        i = j
    return out


def ref_decompress(s):
    out = ""
    i = 0
    while i < len(s):
        c = s[i]
        i += 1
        nb = ""
        while i < len(s) and s[i].isdigit():
            nb += s[i]
            i += 1
        out += c * (int(nb) if nb else 1)
    return out


def ref_island_matrix_counter(matrix):
    if not matrix:
        return 0
    seen = set()
    h, w = len(matrix), len(matrix[0])
    count = 0
    for y in range(h):
        for x in range(w):
            if matrix[y][x] != "1" or (y, x) in seen:
                continue
            count += 1
            q = deque([(y, x)])
            seen.add((y, x))
            while q:
                cy, cx = q.popleft()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if (0 <= ny < h and 0 <= nx < w
                            and matrix[ny][nx] == "1"
                            and (ny, nx) not in seen):
                        seen.add((ny, nx))
                        q.append((ny, nx))
    return count


def ref_graph_cycle(graph):
    state = {}

    def dfs(n):
        state[n] = 1
        for v in graph.get(n, []):
            if state.get(v) == 1:
                return True
            if v not in state and dfs(v):
                return True
        state[n] = 2
        return False
    return any(n not in state and dfs(n) for n in list(graph))


PRISM_DIRS = [("H", 0, 1), ("V", 1, 0), ("D", 1, 1), ("A", -1, 1),
              ("HR", 0, -1), ("VR", -1, 0), ("DR", -1, -1), ("AR", 1, -1)]


def ref_prism_detector(grid, pattern):
    if not grid or not pattern:
        return []
    res = []
    for y in range(len(grid)):
        for x in range(len(grid[y])):
            for code, dy, dx in PRISM_DIRS:
                for k, ch in enumerate(pattern):
                    ny, nx = y + k * dy, x + k * dx
                    if not (0 <= ny < len(grid) and 0 <= nx < len(grid[ny])
                            and grid[ny][nx] == ch):
                        break
                else:
                    res.append((x, y, code))
    return res


def ref_room_scheduler(meetings):
    schedule = []
    for m in sorted(meetings):
        for room in schedule:
            if room[-1][1] <= m[0]:
                room.append(list(m))
                break
        else:
            schedule.append([list(m)])
    return {"total_rooms": len(schedule), "schedule": schedule}


def ref_word_ladder(start, end, words):
    words = set(words)
    if end not in words:
        return 0
    q = deque([(start, 1)])
    seen = {start}
    while q:
        w, d = q.popleft()
        if w == end:
            return d
        for nw in words:
            if (nw not in seen and len(nw) == len(w)
                    and sum(a != b for a, b in zip(nw, w)) == 1):
                seen.add(nw)
                q.append((nw, d + 1))
    return 0


# ---------------------------------------------------------------------------
# Générateurs de tests aléatoires : renvoient (nom_fonction, args)
# ---------------------------------------------------------------------------

def rword(rng, alpha, lo, hi):
    return "".join(rng.choice(alpha) for _ in range(rng.randint(lo, hi)))


def gen_spiral(rng):
    return "generate_spiral", [rng.randint(0, 12)]


def gen_compress(rng):
    s = "".join(rng.choice("abcXY") * rng.choice([1, 1, 2, 3, 9, 10, 13])
                for _ in range(rng.randint(0, 6)))
    if rng.random() < 0.5:
        return "compress", [s]
    return "decompress", [ref_compress(s)]


def gen_island(rng):
    if rng.random() < 0.05:
        return "island_matrix_counter", [[]]
    h, w = rng.randint(1, 8), rng.randint(1, 8)
    p = rng.random()
    return "island_matrix_counter", [
        [["1" if rng.random() < p else "0" for _ in range(w)]
         for _ in range(h)]]


def gen_graph(rng):
    n = rng.randint(0, 8)
    g = {}
    for i in range(n):
        if rng.random() < 0.3:
            targets = range(n + 2)
        else:
            targets = range(i + 1, n + 2)
        g[i] = rng.sample(list(targets), min(len(targets), rng.randint(0, 3)))
    return "py_graph_cycle_detector", [g]


def gen_prism(rng):
    h, w = rng.randint(0, 6), rng.randint(1, 6)
    grid = [rword(rng, "CAT.", w, w) for _ in range(h)]
    pattern = rng.choice(["CAT", "CAT", "AT", "TAC", "C", "", "CATA"])
    return "prism_detector", [grid, pattern]


def gen_rooms(rng):
    ms = []
    for _ in range(rng.randint(0, 8)):
        a = rng.randint(0, 20)
        ms.append([a, a + rng.randint(1, 10)])
    return "py_room_scheduler", [ms]


def gen_ladder(rng):
    words = list({rword(rng, "abcd", 3, 3) for _ in range(rng.randint(0, 25))})
    start = rword(rng, "abcd", 3, 3)
    if words and rng.random() < 0.8:
        end = rng.choice(words)
    else:
        end = rword(rng, "abcd", 3, 3)
    if end == start:
        end = "zzz"
    rng.shuffle(words)
    return "word_ladder", [start, end, words]


# ---------------------------------------------------------------------------
# Banque d'exercices (exam_5)
# ---------------------------------------------------------------------------

def ex_(name, sigs, desc, examples, fixed, refs, gen):
    return dict(name=name, sigs=sigs, desc=desc, ex=examples, fixed=fixed,
                refs=refs, gen=gen)


EXERCISES = {
    1: [
        ex_("py_spiral_matrix", ["def generate_spiral(n: int) "
                                 "-> list[list[int]]:"],
            """Écris une fonction qui génère une matrice 2D `n x n` remplie de
nombres de 1 à `n^2` dans l'ordre d'une spirale dans le sens des
aiguilles d'une montre.

La spirale commence dans la case en haut à gauche (0, 0) vers la droite,
puis vers le bas, la gauche et le haut.
Si `n <= 0`, renvoie `[]`.""",
            [("generate_spiral", [3]), ("generate_spiral", [1])],
            [("generate_spiral", [n]) for n in (0, 2, 4, 5)],
            {"generate_spiral": ref_generate_spiral}, gen_spiral),
        ex_("py_compress_decompress",
            ["def compress(s: str) -> str:", "def decompress(s: str) -> str:"],
            """Écris deux fonctions : `compress` et `decompress`.

compress(s: str) -> str :
    - Compresse les caractères consécutifs répétés en ajoutant leur
      nombre après le caractère.
    - Omets le nombre '1' pour un caractère unique.
    - Renvoie une chaîne vide si l'entrée est vide.

decompress(s: str) -> str :
    - Décompresse une chaîne compressée vers sa forme initiale.
    - Gère les nombres à plusieurs chiffres (ex. "a12" -> 12 'a').

Les chaînes à compresser ne contiennent jamais de chiffres.""",
            [("compress", ["aabcccccaaa"]), ("decompress", ["a2bc5a3"]),
             ("compress", [""])],
            [("compress", ["abc"]), ("compress", ["aaaaaaaaaaaa"]),
             ("decompress", ["a12"]), ("decompress", [""]),
             ("decompress", ["abc"])],
            {"compress": ref_compress, "decompress": ref_decompress},
            gen_compress),
    ],
    2: [
        ex_("py_island_matrix_counter",
            ["def island_matrix_counter(matrix: list[list[str]]) -> int:"],
            """Écris une fonction `island_matrix_counter(matrix)` qui renvoie le
nombre total d'îles dans une matrice 2D contenant des valeurs "1" et "0".

    - Renvoie 0 si la matrice est vide.
    - Une île est un groupe de cases "1" connectées horizontalement ou
      verticalement (les diagonales ne comptent pas).""",
            [("island_matrix_counter", [[["1", "1", "1", "1", "0"],
                                         ["1", "1", "1", "0", "0"],
                                         ["1", "1", "1", "1", "0"],
                                         ["0", "0", "0", "0", "0"]]]),
             ("island_matrix_counter", [[["1", "1", "0", "0", "0"],
                                         ["1", "1", "0", "0", "0"],
                                         ["0", "0", "1", "0", "0"],
                                         ["0", "0", "0", "1", "1"]]]),
             ("island_matrix_counter", [[]])],
            [("island_matrix_counter", [[["0"]]]),
             ("island_matrix_counter", [[["1"]]]),
             ("island_matrix_counter", [[["1", "0", "1"],
                                         ["0", "1", "0"]]])],
            {"island_matrix_counter": ref_island_matrix_counter}, gen_island),
        ex_("py_graph_cycle_detector",
            ["def py_graph_cycle_detector(graph: dict[int, list[int]]) "
             "-> bool:"],
            """Écris une fonction qui détermine si un graphe orienté contient au
moins un cycle.

La fonction prend un dictionnaire représentant une liste d'adjacence.
Un voisin peut ne pas être une clé du dictionnaire (il n'a alors aucun
voisin).
    - Renvoie True si le graphe contient un cycle.
    - Renvoie False si le graphe est acyclique ou vide.""",
            [("py_graph_cycle_detector", [{0: [1], 1: [2], 2: [0]}]),
             ("py_graph_cycle_detector", [{0: [1], 1: [2], 2: []}]),
             ("py_graph_cycle_detector", [{}])],
            [("py_graph_cycle_detector", [{0: [1], 1: [2], 2: [1]}]),
             ("py_graph_cycle_detector", [{0: [1, 2], 1: [2], 2: []}]),
             ("py_graph_cycle_detector", [{0: [0]}]),
             ("py_graph_cycle_detector", [{0: [5], 1: [2], 2: [1]}])],
            {"py_graph_cycle_detector": ref_graph_cycle}, gen_graph),
    ],
    3: [
        ex_("py_room_scheduler",
            ["def py_room_scheduler(meetings: list[list[int]]) "
             "-> dict[str, Any]:"],
            """Écris une fonction qui détermine le nombre minimal de salles de
réunion nécessaires et attribue les créneaux sans chevauchement.

Chaque réunion est une liste `[start_time, end_time]`.

La fonction doit :
    - Renvoyer un dictionnaire avec `"total_rooms"` (nombre de salles)
      et `"schedule"` (liste des salles, chaque salle étant la liste de
      ses réunions).
    - Traiter les réunions triées par heure de début, et placer chaque
      réunion dans la PREMIÈRE salle libre (une salle est libre si sa
      dernière réunion finit avant ou pile au début de la nouvelle).
      Si aucune salle n'est libre, ouvrir une nouvelle salle.
    - Renvoyer `{"total_rooms": 0, "schedule": []}` si la liste est vide.""",
            [("py_room_scheduler", [[[0, 30], [5, 10], [15, 20]]]),
             ("py_room_scheduler", [[]])],
            [("py_room_scheduler", [[[0, 10], [10, 20]]]),
             ("py_room_scheduler", [[[15, 20], [0, 30], [5, 10]]]),
             ("py_room_scheduler", [[[1, 5], [2, 6], [3, 7]]])],
            {"py_room_scheduler": ref_room_scheduler}, gen_rooms),
        ex_("py_prism_detector",
            ["def prism_detector(grid: list[str], pattern: str) "
             "-> list[tuple[int, int, str]]:"],
            """Écris une fonction qui cherche toutes les occurrences d'un mot cible
dans une grille 2D dans les 8 directions.

    - Renvoie une liste de tuples `(x, y, code_direction)` où `x` est la
      colonne et `y` la ligne de la première lettre.
    - Codes de direction :
        "H"  → droite          "HR" → gauche
        "V"  → bas             "VR" → haut
        "D"  → bas-droite      "DR" → haut-gauche
        "A"  → haut-droite     "AR" → bas-gauche
    - Ordre du résultat : ligne par ligne (y croissant), puis colonne
      (x croissant), puis dans l'ordre H, V, D, A, HR, VR, DR, AR.
    - Un mot d'une seule lettre est donc trouvé dans les 8 directions.
    - Renvoie `[]` si la grille ou le mot est vide.""",
            [("prism_detector", [["CAT", "A..", "T.."], "CAT"]),
             ("prism_detector", [[], "CAT"])],
            [("prism_detector", [["CAT"], ""]),
             ("prism_detector", [["TAC", "AA.", "C.C"], "CAT"]),
             ("prism_detector", [["C"], "C"])],
            {"prism_detector": ref_prism_detector}, gen_prism),
    ],
    4: [
        ex_("py_word_ladder",
            ["def word_ladder(start: str, end: str, sentence: list[str]) "
             "-> int:"],
            """Écris une fonction qui calcule la longueur de la séquence de
transformation la plus courte d'un mot de départ à un mot de fin.

À chaque étape, on change exactement une lettre, et le nouveau mot doit
être dans `sentence`. `start` n'a pas besoin d'être dans `sentence`,
mais `end` doit y être.
    - Renvoie le nombre de mots dans l'échelle la plus courte
      (en comptant `start` et `end`).
    - Renvoie 0 si aucune transformation n'est possible.""",
            [("word_ladder", ["hit", "cog",
                              ["hot", "dot", "dog", "lot", "log", "cog"]]),
             ("word_ladder", ["hit", "cog",
                              ["hot", "dot", "dog", "lot", "log"]])],
            [("word_ladder", ["hit", "hot", ["hot"]]),
             ("word_ladder", ["abc", "xyz", []]),
             ("word_ladder", ["aaa", "ccc", ["aab", "abb", "bbb", "ccc"]])],
            {"word_ladder": ref_word_ladder}, gen_ladder),
    ],
}
NB_LEVELS = len(EXERCISES)


def find_ex(name):
    for exs in EXERCISES.values():
        for ex in exs:
            if ex["name"] == name:
                return ex
    raise KeyError(name)


def fmt_call(fname, args):
    return f"{fname}({', '.join(repr(a) for a in args)})"


def subject_text(ex):
    lines = [ex["name"], "", f"Fichier attendu : rendu/{ex['name']}/"
             f"{ex['name']}.py", "", "Énoncé"]
    lines += ["    " + ln if ln else "" for ln in ex["desc"].splitlines()]
    lines += ["", "Signature" + ("s" if len(ex["sigs"]) > 1 else "")
              + " de la fonction"]
    lines += ["    " + s for s in ex["sigs"]]
    lines += ["", "Exemples"]
    for fname, args in ex["ex"]:
        res = ex["refs"][fname](*copy.deepcopy(args))
        lines += ["    Entrée", "        " + fmt_call(fname, args),
                  "    Sortie", "        " + repr(res)]
    lines += ["", "Fonctions autorisées : tout Python standard.",
              "Ton fichier doit respecter flake8."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Moulinette
# ---------------------------------------------------------------------------

RUNNER = r"""
import ast, contextlib, importlib.util, io, json, sys, traceback
path = sys.argv[1]
tests = ast.literal_eval(sys.stdin.read())
out, buf = sys.stdout, io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        spec = importlib.util.spec_from_file_location("student", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
except BaseException:
    out.write(json.dumps({"fatal": traceback.format_exc(limit=4)}))
    sys.exit(0)
res = []
for fname, args in tests:
    f = getattr(mod, fname, None)
    if f is None:
        res.append({"exc": "fonction '" + fname + "' introuvable"})
        continue
    try:
        with contextlib.redirect_stdout(buf):
            r = f(*args)
        res.append({"repr": repr(r)})
    except BaseException:
        res.append({"exc": traceback.format_exc(limit=4)})
out.write(json.dumps({"results": res}))
"""


def canon(x):
    """Forme comparable qui distingue bool/int, tuple/list, etc."""
    if isinstance(x, (bool, int, float, str, type(None))):
        return (type(x).__name__, x)
    if isinstance(x, (list, tuple)):
        return (type(x).__name__, [canon(v) for v in x])
    if isinstance(x, dict):
        return ("dict", sorted(((canon(k), canon(v)) for k, v in x.items()),
                               key=repr))
    if isinstance(x, (set, frozenset)):
        return ("set", sorted((canon(v) for v in x), key=repr))
    return ("other", repr(x))


def grade(ex, path, use_flake8):
    """Renvoie (succès, trace)."""
    if not os.path.isfile(path):
        return False, f"Fichier introuvable : {path}\n"
    if use_flake8 and shutil.which("flake8"):
        p = subprocess.run(["flake8", path], capture_output=True, text=True)
        if p.returncode != 0:
            return False, "=== Erreur de norme (flake8) ===\n" + p.stdout
    rng = random.Random()
    tests = list(ex["ex"]) + list(ex["fixed"])
    tests += [ex["gen"](rng) for _ in range(RANDOM_TESTS)]
    try:
        p = subprocess.run([sys.executable, "-I", "-c", RUNNER, path],
                           input=repr(tests), capture_output=True,
                           text=True, timeout=TIMEOUT,
                           cwd=os.path.dirname(path))
    except subprocess.TimeoutExpired:
        return False, (f"=== TIMEOUT ===\nTon programme a dépassé {TIMEOUT}s "
                       "(boucle infinie ou algo trop lent).\n")
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        return False, ("=== Crash ===\n" + p.stdout[-2000:]
                       + p.stderr[-2000:])
    if "fatal" in data:
        return False, "=== Erreur au chargement ===\n" + data["fatal"]
    for (fname, args), got in zip(tests, data["results"]):
        expected = ex["refs"][fname](*copy.deepcopy(args))
        call = fmt_call(fname, args)
        if "exc" in got:
            return False, (f"=== Exception ===\nTest : {call}\n\n"
                           + got["exc"])
        try:
            value = ast.literal_eval(got["repr"])
            same = canon(value) == canon(expected)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            same = False
        if not same:
            return False, (f"=== Mauvais résultat ===\nTest    : {call}\n"
                           f"Attendu : {expected!r}\nObtenu  : {got['repr']}\n")
    return True, f"{len(tests)} tests passés.\n"


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------

def save(state):
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2)


def pick(state, level):
    done = {h["name"] for h in state["history"]}
    choices = [e for e in EXERCISES[level] if e["name"] not in done]
    ex = random.choice(choices or EXERCISES[level])
    state["current"] = ex["name"]
    state["attempts"] = 0
    d = os.path.join(SUBJECTS, ex["name"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, ex["name"] + ".txt"), "w") as f:
        f.write(subject_text(ex))
    os.makedirs(os.path.join(RENDU, ex["name"]), exist_ok=True)
    save(state)


def remaining(state):
    return state["start"] + state["duration"] * 60 - time.time()


def fmt_time(sec):
    sec = max(0, int(sec))
    return f"{sec // 3600}h{sec % 3600 // 60:02d}m{sec % 60:02d}s"


def score(state):
    return state["level"] * 100 // NB_LEVELS


def status(state):
    print(f"\n  Niveau  : {min(state['level'] + 1, NB_LEVELS)}/{NB_LEVELS}"
          f"   Note actuelle : {score(state)}/100")
    print(f"  Temps restant : {fmt_time(remaining(state))}")
    if state["current"]:
        n = state["current"]
        print(f"  Exercice : {n}  (essais : {state['attempts']})")
        print(f"  Sujet    : subjects/{n}/{n}.txt")
        print(f"  Rendu    : rendu/{n}/{n}.py")
    print()


def do_grademe(state, use_flake8):
    if remaining(state) <= 0:
        print("Temps écoulé ! Tu ne peux plus rendre.")
        return
    if input("Es-tu sûr(e) de vouloir rendre ? (y/n) ").strip() != "y":
        return
    ex = find_ex(state["current"])
    path = os.path.join(RENDU, ex["name"], ex["name"] + ".py")
    print("Moulinette en cours", end="", flush=True)
    for _ in range(3):
        time.sleep(0.4)
        print(".", end="", flush=True)
    ok, trace = grade(ex, path, use_flake8)
    state["attempts"] += 1
    os.makedirs(TRACES, exist_ok=True)
    tname = f"{len(state['history']) + 1}-{state['attempts']}-{ex['name']}"
    tpath = os.path.join(TRACES, tname + ".trace")
    with open(tpath, "w") as f:
        f.write(trace)
    if ok:
        print("\n\033[1;32m>>>>>>>>>> SUCCESS <<<<<<<<<<\033[0m")
        state["history"].append({"name": ex["name"],
                                 "attempts": state["attempts"]})
        state["level"] += 1
        if state["level"] >= NB_LEVELS:
            state["current"] = None
            save(state)
            print("\n🎉 Examen terminé ! Note : 100/100\n")
            return
        pick(state, state["level"] + 1)
        print(f"Nouvel exercice : subjects/{state['current']}/")
    else:
        print("\n\033[1;31m>>>>>>>>>> FAILURE <<<<<<<<<<\033[0m")
        print(f"Trace : traces/{tname}.trace")
        save(state)
    status(state)


HELP = """Commandes :
  status    affiche l'exercice en cours et le temps restant
  subject   affiche le sujet en cours
  grademe   envoie ton rendu à la moulinette
  finish    termine l'examen
  help      affiche cette aide
"""


def main():
    ap = argparse.ArgumentParser(description="Simulation d'examen Python")
    ap.add_argument("--reset", action="store_true",
                    help="recommence un nouvel examen")
    ap.add_argument("--duration", type=int, default=180,
                    help="durée en minutes (défaut 180)")
    ap.add_argument("--no-flake8", action="store_true",
                    help="désactive la vérification flake8")
    a = ap.parse_args()

    if a.reset or not os.path.exists(STATE):
        for d in (SUBJECTS, TRACES):
            shutil.rmtree(d, ignore_errors=True)
        if os.path.isdir(RENDU) and os.listdir(RENDU):
            old = RENDU + time.strftime("_old_%Y%m%d_%H%M%S")
            os.rename(RENDU, old)
            print(f"Anciens rendus déplacés dans {os.path.basename(old)}/")
        state = {"start": time.time(), "duration": a.duration, "level": 0,
                 "current": None, "attempts": 0, "history": []}
        pick(state, 1)
        print("\n=== Nouvel examen lancé (exam_5) ===")
    else:
        with open(STATE) as f:
            state = json.load(f)
        print("\n=== Reprise de l'examen ===")

    print(HELP)
    status(state)
    while True:
        try:
            cmd = input("examshell> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nÀ plus ! (relance le script pour reprendre)")
            return
        if cmd == "status":
            status(state)
        elif cmd == "subject" and state["current"]:
            print()
            print(textwrap.indent(subject_text(find_ex(state["current"])),
                                  "  "))
        elif cmd == "grademe" and state["current"]:
            do_grademe(state, not a.no_flake8)
        elif cmd == "finish":
            if input("Terminer l'examen ? (y/n) ").strip() == "y":
                print(f"\nNote finale : {score(state)}/100")
                for h in state["history"]:
                    print(f"  ✔ {h['name']} ({h['attempts']} essai(s))")
                os.remove(STATE)
                return
        elif cmd in ("help", ""):
            print(HELP) if cmd else None
        else:
            print(f"Commande inconnue : {cmd}")


if __name__ == "__main__":
    main()
