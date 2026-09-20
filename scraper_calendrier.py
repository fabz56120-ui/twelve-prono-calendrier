
from playwright.sync_api import sync_playwright
import json
import re
import unicodedata


BASE_URL = "https://prod2.lnr.fr/calendrier-et-resultats/2026-2027"


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


def nettoyer_lignes(texte):

    lignes = []

    for ligne in texte.splitlines():

        ligne = ligne.strip()

        if ligne:
            lignes.append(ligne)

    return lignes


def normaliser_texte(texte):

    if not texte:
        return ""

    texte = unicodedata.normalize(
        "NFD",
        texte
    )

    texte = "".join(
        caractere
        for caractere in texte
        if unicodedata.category(caractere) != "Mn"
    )

    texte = texte.upper()

    texte = re.sub(
        r"[^A-Z0-9]+",
        "_",
        texte
    )

    return texte.strip("_")


def creer_match_id(
    journee,
    domicile,
    exterieur,
    date
):

    return "_".join([
        normaliser_texte(journee),
        normaliser_texte(domicile),
        normaliser_texte(exterieur),
        normaliser_texte(date)
    ])


def extraire_section_journee(texte, numero):

    titre = f"JOURNÉE {numero}"

    position = texte.rfind(titre)

    if position == -1:
        return ""

    section = texte[position:]

    marqueurs_fin = [
        "LES AVANTAGES",
        "NOS PARTENAIRES",
        "BON PLAN"
    ]

    for marqueur in marqueurs_fin:

        position_fin = section.find(marqueur)

        if position_fin != -1:
            section = section[:position_fin]

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

    return any(
        texte.startswith(jour)
        for jour in jours
    )


def est_un_score(texte):

    return re.match(
        r"^\d+\s*-\s*\d+$",
        texte
    ) is not None


def extraire_matchs(texte, numero):

    section = extraire_section_journee(
        texte,
        numero
    )

    if not section:
        return []

    lignes = nettoyer_lignes(section)

    matchs = []

    date_actuelle = None
    equipes_trouvees = []
    score_en_attente = None

    for ligne in lignes:

        if est_une_date(ligne):

            date_actuelle = ligne
            continue

        if est_un_score(ligne):

            morceaux = re.split(
                r"\s*-\s*",
                ligne
            )

            score_en_attente = (
                int(morceaux[0]),
                int(morceaux[1])
            )

            continue

        if ligne == "-":

            score_en_attente = None
            continue

        if ligne in EQUIPES:

            equipes_trouvees.append(ligne)

            if len(equipes_trouvees) == 2:

                domicile = equipes_trouvees[0]
                exterieur = equipes_trouvees[1]

                match_id = creer_match_id(
                    f"J{numero}",
                    domicile,
                    exterieur,
                    date_actuelle
                )

                match = {
                    "id": match_id,
                    "journee": f"J{numero}",
                    "date": date_actuelle,
                    "domicile": domicile,
                    "exterieur": exterieur,
                    "scoreDomicile": None,
                    "scoreExterieur": None
                }

                if score_en_attente is not None:

                    match["scoreDomicile"] = (
                        score_en_attente[0]
                    )

                    match["scoreExterieur"] = (
                        score_en_attente[1]
                    )

                matchs.append(match)

                equipes_trouvees = []
                score_en_attente = None

    matchs_uniques = []
    deja_vus = set()

    for match in matchs:

        cle = match["id"]

        if cle not in deja_vus:

            deja_vus.add(cle)
            matchs_uniques.append(match)

    return matchs_uniques


def main():

    print("Ouverture du calendrier officiel...")

    calendrier = {
        "source": "https://prod2.lnr.fr/calendrier-et-resultats",
        "saison": "2026-2027",
        "journees": {}
    }

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        for numero in range(1, 31):

            print()
            print("=================================")
            print()
            print(
                f"Récupération de J{numero}..."
            )

            url = f"{BASE_URL}/j{numero}"

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(3000)

                texte = page.locator(
                    "body"
                ).inner_text()

                matchs = extraire_matchs(
                    texte,
                    numero
                )

                calendrier["journees"][
                    f"J{numero}"
                ] = matchs

                print(
                    f"✓ {len(matchs)} match(s) récupéré(s)"
                )

            except Exception as erreur:

                print(
                    f"⚠ Erreur sur J{numero} : {erreur}"
                )

                calendrier["journees"][
                    f"J{numero}"
                ] = []

        browser.close()

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

    print()
    print("=================================")
    print()
    print("✓ calendrier.json créé")
    print()
    print("=================================")


if __name__ == "__main__":
    main()
