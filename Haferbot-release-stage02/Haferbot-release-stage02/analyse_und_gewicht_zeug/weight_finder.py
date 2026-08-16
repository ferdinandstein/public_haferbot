import json
import subprocess
import time
import re
import random
import string

RESULT_PATH = r"../haferbot/analyse_und_gewicht_zeug/result.json"
STATISTICS_PATH = r"../haferbot/analyse_und_gewicht_zeug/statistics.json"
BOT_FILE_PATH = r"../haferbot/analyse_und_gewicht_zeug/weight.py"  # <-- Anpassen!
VARIABLE_NAME = "WEIGHT"  # <-- Anpassen!
SEED_NAME = "SEED"


# ------------------------------------------
# Gewicht direkt im Python-Code ersetzen
# ------------------------------------------
def set_bot_weight(weight):
    with open(BOT_FILE_PATH, "r", encoding="utf-8") as f:
        code = f.read()

    # Regex: VARIABLE_NAME = <zahl>
    pattern = rf"{VARIABLE_NAME}\s*=\s*[-+]?\d*\.?\d+"
    replacement = f"{VARIABLE_NAME} = {weight}"

    new_code = re.sub(pattern, replacement, code)

    with open(BOT_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(new_code)


def set_seed(seed):
    with open(BOT_FILE_PATH, "r", encoding="utf-8") as f:
        code = f.read()

    # Regex: alles zwischen SEED = und dem finalen String ersetzen
    pattern = rf'{SEED_NAME}\s*=\s*.*?["\'].*?["\']'
    replacement = f'{SEED_NAME} = "{seed}"'

    new_code, count = re.subn(pattern, replacement, code)

    if count == 0:
        print(repr(code))  # Zeige Inhalt, um zu debuggen
        raise RuntimeError(f"{SEED_NAME} nicht im Bot-Code gefunden!")

    with open(BOT_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(new_code)


def write_statistics(seed, best_weight, best_score):
    infos = {
        "best_weight": best_weight,
        "best_score": best_score,
    }

    try:
        with open(STATISTICS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
            if not isinstance(stats, list):
                stats = []
    except (FileNotFoundError, json.JSONDecodeError):
        stats = []

    # Nach Seed suchen
    for entry in stats:
        if entry.get("seed") == seed:
            entry.setdefault("infos", []).update(infos)
            break
    else:
        # Seed existiert noch nicht
        stats.append({"seed": seed, "infos": [infos]})

    with open(STATISTICS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)


def get_seed():
    buchstaben = string.ascii_letters
    zahlen = string.digits
    alle_zeichen = buchstaben + zahlen
    laenge = 6
    seed = "".join(random.choice(alle_zeichen) for _ in range(laenge))

    try:
        with open(STATISTICS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
            if not isinstance(stats, list):
                stats = []
    except (FileNotFoundError, json.JSONDecodeError):
        stats = []

    # Nach Seed suchen
    for entry in stats:
        if entry.get("seed") == seed:
            get_seed()
    else:
        return seed


# ------------------------------------------
# Runner ausführen
# ------------------------------------------
def run_match(seed):
    command = [
        "ruby",
        "runner_patched.rb",
        "--seed",
        seed,
        "--write-profile-json",
        RESULT_PATH,
        "--max-tps",
        "10000",
        "--rounds",
        "50",
        "--multi-core",
        "--threads",
        "32",
        r"../haferbot",
        r"../haferbot_kopie",
    ]

    subprocess.run(command, check=True)

    # Kurz warten bis Datei geschrieben ist
    time.sleep(0.2)

    with open(RESULT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Score extrahieren – hier AUFBAU ANPASSEN!
    score = data[0].get("total_score")
    return score


# ------------------------------------------
# Hauptoptimierung
# ------------------------------------------
def optimize_weight(seed):
    print(f"Teste Seed {seed}")
    start_weight = 2.0
    factor = 1.5
    current_weight = start_weight
    dict = {}
    set_bot_weight(start_weight)
    current_score = run_match(seed)
    dict.update({current_score: current_weight})

    for i in range(4):
        set_bot_weight(current_weight + factor)
        score_plus = run_match(seed)
        dict.update({score_plus: current_weight + factor})

        if score_plus > current_score:
            current_score = score_plus
            current_weight = dict[current_score]
            factor = factor / 2
            dict = {}
            dict.update({current_score: current_weight})
            print(f"Done with: {i + 1} of 4")
        else:
            set_bot_weight(current_weight - factor)
            score_minus = run_match(seed)
            dict.update({score_minus: current_weight - factor})

            current_score = max(score_minus, current_score, score_plus)
            current_weight = dict[current_score]
            factor = factor / 2
            dict = {}
            dict.update({current_score: current_weight})
            print(f"Done with: {i + 1} of 4")

    print("\n==============================")
    print(" Optimierung abgeschlossen")
    print("==============================")
    print(f"Best weight: {current_weight}")
    print(f"Best score: {current_score}")
    return current_weight, current_score


def complete_previous():
    print("\nCompleting previous\n")
    try:
        with open(STATISTICS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
            if not isinstance(stats, list):
                stats = []
    except (FileNotFoundError, json.JSONDecodeError):
        stats = []

    for entry in stats:
        seed = entry.get("seed")
        set_seed(seed)
        run_match(seed)


def main():
    rounds = 1
    for i in range(rounds):
        seed = "adfwe"
        set_seed(seed)
        best_weight, best_score = optimize_weight(seed)
        write_statistics(seed, best_weight, best_score)
        print("\n==============================")
        print(f"Finished round {i + 1} of {rounds}")
        print("==============================")

    print("\n==============================")
    print(f"Done with all {i + 1} rounds")
    print("==============================")
    # complete_previous()


if __name__ == "__main__":
    main()
