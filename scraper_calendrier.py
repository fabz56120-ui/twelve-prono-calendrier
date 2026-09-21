
from playwright.sync_api import sync_playwright
import json
import re
import unicodedata
from datetime import datetime

BASE_URL = "https://prod2.lnr.fr/calendrier-et-resultats/2026-2027"
RUGBYRAMA_URL = "https://www.rugbyrama.fr/resultats/rugby/pro-d2/calendrier"

EQUIPES = [
    "Biarritz Olympique PB", "Colomiers Rugby", "Soyaux-Angoulême XV",
    "US Montauban", "Provence Rugby", "RC Narbonnais",
    "AS Béziers Hérault", "USON Nevers", "CA Brive", "Nissa Rugby",
    "US Dax", "Valence Romans", "Oyonnax Rugby", "Stade Aurillacois",
    "FC Grenoble Rugby", "SU Agen"
]


def normaliser_texte(texte):
    if not texte:
        return ""

    texte = unicodedata.normalize("NFD", texte)

    texte = "".join(
        c for c in texte
        if unicodedata.category(c) != "Mn"
    )

    texte = texte.upper()

    return re.sub(r"[^A-Z0-9]+", "_", texte).strip("_")


def nettoyer_ligne(ligne):
    if not ligne:
        return ""

    ligne = ligne.replace("**", "")

    ligne = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        ligne
    )

    return ligne.replace("\xa0", " ").strip()


def nettoyer_lignes(texte):
    return [
        nettoyer_ligne(ligne)
        for ligne in texte.splitlines()
        if nettoyer_ligne(ligne)
    ]


def creer_match_id(journee, domicile, exterieur, date):
    return "_".join([
        normaliser_texte(journee),
        normaliser_texte(domicile),
        normaliser_texte(exterieur),
        normaliser_texte(date)
    ])


def extraire_section_journee(texte, numero):
    motifs = [
        f"JOURNÉE {numero}",
        f"JOURNEE {numero}",
        f"Journée {numero}",
        f"Journee {numero}"
    ]

    position = next(
        (
            texte.find(m)
            for m in motifs
            if texte.find(m) != -1
        ),
        -1
    )

    if position == -1:
        return ""

    section = texte[position:]

    positions = [
        p
        for m in [
            "LES AVANTAGES",
            "NOS PARTENAIRES",
            "BON PLAN"
        ]
        if (p := section.find(m)) != -1
    ]

    return (
        section[:min(positions)]
        if positions
        else section
    )


def est_une_date(texte):
    jours = (
        "LUNDI MARDI MERCREDI JEUDI "
        "VENDREDI SAMEDI DIMANCHE"
    ).split()

    texte = nettoyer_ligne(texte).upper()

    return any(
        texte.startswith(j + " ")
        for j in jours
    )


def extraire_heure(texte):
    if not texte:
        return None

    motif = (
        r"(?<!\d)"
        r"([01]?\d|2[0-3])"
        r"\s*(?::|[hH])"
        r"\s*([0-5]\d)"
        r"(?!\d)"
    )

    resultat = re.search(motif, texte)

    if not resultat:
        return None

    return (
        f"{int(resultat.group(1)):02d}:"
        f"{int(resultat.group(2)):02d}"
    )


def est_un_score(texte):
    return re.fullmatch(
        r"\d+\s*-\s*\d+",
        texte.strip()
    ) is not None


def extraire_score(texte):
    a, b = re.split(
        r"\s*-\s*",
        texte.strip()
    )

    return int(a), int(b)


def trouver_equipe(texte):
    n = normaliser_texte(texte)

    for equipe in EQUIPES:
        if normaliser_texte(equipe) == n:
            return equipe

    return None


def extraire_matchs(texte, numero):
    section = extraire_section_journee(
        texte,
        numero
    )

    if not section:
        return []

    matchs = []

    date_actuelle = None
    heure_actuelle = None

    equipes_trouvees = []
    score_en_attente = None

    for ligne in nettoyer_lignes(section):

        if est_une_date(ligne):
            date_actuelle = ligne.upper()
            heure_actuelle = extraire_heure(ligne)

            equipes_trouvees = []
            score_en_attente = None

            continue

        heure = extraire_heure(ligne)

        if heure:
            heure_actuelle = heure
            continue

        if est_un_score(ligne):
            score_en_attente = extraire_score(ligne)
            continue

        equipe = trouver_equipe(ligne)

        if not equipe:
            continue

        equipes_trouvees.append(equipe)

        if len(equipes_trouvees) < 2:
            continue

        domicile, exterieur = equipes_trouvees[:2]

        match = {
            "id": creer_match_id(
                f"J{numero}",
                domicile,
                exterieur,
                date_actuelle or ""
            ),
            "journee": f"J{numero}",
            "date": date_actuelle,
            "heure": heure_actuelle,
            "domicile": domicile,
            "exterieur": exterieur,
            "scoreDomicile": (
                score_en_attente[0]
                if score_en_attente
                else None
            ),
            "scoreExterieur": (
                score_en_attente[1]
                if score_en_attente
                else None
            )
        }

        matchs.append(match)

        equipes_trouvees = []
        score_en_attente = None
        heure_actuelle = None

    uniques = []
    vus = set()

    for match in matchs:
        if match["id"] not in vus:
            vus.add(match["id"])
            uniques.append(match)

    return uniques


def cle_match(domicile, exterieur):
    return frozenset((
        normaliser_texte(domicile),
        normaliser_texte(exterieur)
    ))


def extraire_matchs_rugbyrama(texte):
    """
    Extraction prudente :
    conserve les blocs contenant deux équipes
    connues et une heure.
    """

    lignes = nettoyer_lignes(texte)
    resultats = []

    for i, ligne in enumerate(lignes):

        heure = extraire_heure(ligne)

        if not heure:
            continue

        equipes = []

        debut = max(0, i - 8)
        fin = min(len(lignes), i + 9)

        for candidate in lignes[debut:fin]:

            equipe = trouver_equipe(candidate)

            if equipe and equipe not in equipes:
                equipes.append(equipe)

        if len(equipes) >= 2:

            resultats.append({
                "domicile": equipes[0],
                "exterieur": equipes[1],
                "heure": heure
            })

    uniques = []
    vus = set()

    for match in resultats:

        cle = (
            cle_match(
                match["domicile"],
                match["exterieur"]
            ),
            match["heure"]
        )

        if cle not in vus:
            vus.add(cle)
            uniques.append(match)

    return uniques


def completer_heures(calendrier, horaires_rr):
    index = {}

    for item in horaires_rr:

        cle = cle_match(
            item["domicile"],
            item["exterieur"]
        )

        index.setdefault(cle, []).append(
            item["heure"]
        )

    complets = 0

    for matchs in calendrier["journees"].values():

        for match in matchs:

            if match.get("heure"):
                continue

            heures = index.get(
                cle_match(
                    match["domicile"],
                    match["exterieur"]
                ),
                []
            )

            heures = [
                h
                for h in heures
                if h != "00:00"
            ]

            if len(set(heures)) == 1:

                match["heure"] = heures[0]
                complets += 1

    return complets


def main():

    calendrier = {
        "source": BASE_URL,
        "saison": "2026-2027",
        "journees": {}
    }

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1920,
                "height": 1080
            }
        )

        for numero in range(1, 31):

            print(
                f"\n===== Récupération de J{numero} ====="
            )

            try:

                page.goto(
                    f"{BASE_URL}/j{numero}",
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(8000)

                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )

                page.wait_for_timeout(2000)

                texte = page.locator("body").inner_text()

                with open(
                    f"debug_J{numero}.txt",
                    "w",
                    encoding="utf-8"
                ) as f:

                    f.write(texte)

                matchs = extraire_matchs(
                    texte,
                    numero
                )

                calendrier["journees"][f"J{numero}"] = matchs

                print(
                    f"✓ {len(matchs)} match(s)"
                )

            except Exception as erreur:

                print(
                    f"⚠ Première tentative échouée "
                    f"pour J{numero}: {erreur}"
                )

                try:

                    page.goto(
                        f"{BASE_URL}/j{numero}",
                        wait_until="commit",
                        timeout=60000
                    )

                    page.wait_for_timeout(10000)

                    page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight)"
                    )

                    page.wait_for_timeout(2000)

                    texte = page.locator("body").inner_text()

                    with open(
                        f"debug_J{numero}.txt",
                        "w",
                        encoding="utf-8"
                    ) as f:

                        f.write(texte)

                    matchs = extraire_matchs(
                        texte,
                        numero
                    )

                    calendrier["journees"][f"J{numero}"] = matchs

                    print(
                        f"✓ Deuxième tentative : "
                        f"{len(matchs)} match(s)"
                    )

                except Exception as seconde_erreur:

                    print(
                        f"⚠ Échec définitif J{numero}: "
                        f"{seconde_erreur}"
                    )

                    calendrier["journees"][f"J{numero}"] = []

        print(
            "\n===== Complément des heures "
            "avec Rugbyrama ====="
        )

        horaires_rr = []

        try:

            page.goto(
                RUGBYRAMA_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(7000)

            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_timeout(2000)

            texte_rr = page.locator("body").inner_text()

            with open(
                "debug_rugbyrama.txt",
                "w",
                encoding="utf-8"
            ) as f:

                f.write(texte_rr)

            horaires_rr = extraire_matchs_rugbyrama(
                texte_rr
            )

            print(
                f"✓ {len(horaires_rr)} horaire(s) "
                f"candidat(s) trouvé(s)"
            )

        except Exception as erreur:

            print(
                f"⚠ Rugbyrama ignoré: {erreur}"
            )

        browser.close()

    complets = completer_heures(
        calendrier,
        horaires_rr
    )

    print(
        f"✓ {complets} heure(s) complétée(s) "
        f"depuis Rugbyrama"
    )

    with open(
        "calendrier.json",
        "w",
        encoding="utf-8"
    ) as fichier:

        json.dump(
            calendrier,
            fichier,
            ensure_ascii=False,
            indent=4
        )

    print(
        "✓ calendrier.json créé"
    )


if __name__ == "__main__":
    main()
