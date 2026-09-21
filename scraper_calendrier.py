
from playwright.sync_api import sync_playwright
import json
import re
import unicodedata


BASE_URL = "https://prod2.lnr.fr/calendrier-et-resultats/2026-2027"
RUGBYRAMA_URL = "https://www.rugbyrama.fr/resultats/rugby/pro-d2/calendrier"


EQUIPES = [
    "Biarritz Olympique PB",
    "Colomiers Rugby",
    "Soyaux-Angoulême XV",
    "US Montauban",
    "Provence Rugby",
    "RC Narbonnais",
    "AS Béziers Hérault",
    "USON Nevers",
    "CA Brive",
    "Nissa Rugby",
    "US Dax",
    "Valence Romans",
    "Oyonnax Rugby",
    "Stade Aurillacois",
    "FC Grenoble Rugby",
    "SU Agen"
]


def normaliser_texte(texte):

    if not texte:
        return ""

    texte = unicodedata.normalize("NFD", texte)

    texte = "".join(
        caractere
        for caractere in texte
        if unicodedata.category(caractere) != "Mn"
    )

    texte = texte.upper()

    texte = re.sub(r"[^A-Z0-9]+", "_", texte)

    return texte.strip("_")


def nettoyer_ligne(ligne):

    if not ligne:
        return ""

    ligne = ligne.replace("**", "")

    ligne = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        ligne
    )

    ligne = ligne.replace("\xa0", " ")

    return ligne.strip()


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

    position = -1

    for motif in motifs:

        trouve = texte.find(motif)

        if trouve != -1:

            position = trouve

            break

    if position == -1:

        return ""

    section = texte[position:]

    marqueurs_fin = [
        "LES AVANTAGES",
        "NOS PARTENAIRES",
        "BON PLAN"
    ]

    positions = []

    for marqueur in marqueurs_fin:

        trouve = section.find(marqueur)

        if trouve != -1:

            positions.append(trouve)

    if positions:

        section = section[:min(positions)]

    return section


def est_une_date(texte):

    jours = [
        "LUNDI",
        "MARDI",
        "MERCREDI",
        "JEUDI",
        "VENDREDI",
        "SAMEDI",
        "DIMANCHE"
    ]

    texte = nettoyer_ligne(texte).upper()

    return any(
        texte.startswith(jour + " ")
        for jour in jours
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

    heure = int(resultat.group(1))

    minutes = int(resultat.group(2))

    return f"{heure:02d}:{minutes:02d}"


def est_un_score(texte):

    return re.fullmatch(
        r"\d+\s*-\s*\d+",
        texte.strip()
    ) is not None


def extraire_score(texte):

    morceaux = re.split(
        r"\s*-\s*",
        texte.strip()
    )

    return (
        int(morceaux[0]),
        int(morceaux[1])
    )


def trouver_equipe(texte):

    texte_normalise = normaliser_texte(texte)

    for equipe in EQUIPES:

        if normaliser_texte(equipe) == texte_normalise:

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

    lignes = nettoyer_lignes(section)

    for ligne in lignes:

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

        if ligne == "-":

            continue

        equipe = trouver_equipe(ligne)

        if not equipe:

            continue

        equipes_trouvees.append(equipe)

        if len(equipes_trouvees) < 2:

            continue

        domicile = equipes_trouvees[0]

        exterieur = equipes_trouvees[1]

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
            "scoreDomicile": None,
            "scoreExterieur": None
        }

        if score_en_attente is not None:

            match["scoreDomicile"] = score_en_attente[0]

            match["scoreExterieur"] = score_en_attente[1]

        matchs.append(match)

        equipes_trouvees = []

        score_en_attente = None

        heure_actuelle = None

    matchs_uniques = []

    deja_vus = set()

    for match in matchs:

        if match["id"] in deja_vus:

            continue

        deja_vus.add(match["id"])

        matchs_uniques.append(match)

    return matchs_uniques


def cle_match(domicile, exterieur):

    return frozenset([
        normaliser_texte(domicile),
        normaliser_texte(exterieur)
    ])


def extraire_matchs_rugbyrama(texte):

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

    resultats_uniques = []

    deja_vus = set()

    for match in resultats:

        cle = (
            cle_match(
                match["domicile"],
                match["exterieur"]
            ),
            match["heure"]
        )

        if cle in deja_vus:

            continue

        deja_vus.add(cle)

        resultats_uniques.append(match)

    return resultats_uniques


def completer_heures(calendrier, horaires_rr):

    index = {}

    for item in horaires_rr:

        cle = cle_match(
            item["domicile"],
            item["exterieur"]
        )

        if cle not in index:

            index[cle] = []

        index[cle].append(item["heure"])

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
                heure
                for heure in heures
                if heure != "00:00"
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
                    wait_until="networkidle",
                    timeout=60000
                )

                page.wait_for_timeout(5000)

                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )

                page.wait_for_timeout(2000)

                texte = page.locator("body").inner_text()

                with open(
                    f"debug_J{numero}.txt",
                    "w",
                    encoding="utf-8"
                ) as fichier:

                    fichier.write(texte)

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
                    f"⚠ Erreur J{numero}: {erreur}"
                )

                calendrier["journees"][f"J{numero}"] = []

        print(
            "\n===== Complément des heures avec Rugbyrama ====="
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
            ) as fichier:

                fichier.write(texte_rr)

            horaires_rr = extraire_matchs_rugbyrama(
                texte_rr
            )

            print(
                f"✓ {len(horaires_rr)} horaire(s) candidat(s) trouvé(s)"
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
        f"✓ {complets} heure(s) complétée(s) depuis Rugbyrama"
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
