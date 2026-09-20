
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

    titres_possibles = [
        f"JOURNÉE {numero}",
        f"JOURNEE {numero}"
    ]

    position = -1

    for titre in titres_possibles:

        position_titre = texte.rfind(titre)

        if position_titre > position:
            position = position_titre

    if position == -1:
        return ""

    section = texte[position:]

    marqueurs_fin = [
        "LES AVANTAGES",
        "NOS PARTENAIRES",
        "BON PLAN"
    ]

    positions_fin = []

    for marqueur in marqueurs_fin:

        position_fin = section.find(marqueur)

        if position_fin != -1:
            positions_fin.append(position_fin)

    if positions_fin:
        section = section[:min(positions_fin)]

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

    texte_majuscule = texte.upper()

    return any(
        texte_majuscule.startswith(jour)
        for jour in jours
    )


def extraire_heure(texte):

    if not texte:
        return None

    correspondance = re.search(
        r"(?<!\d)([01]?\d|2[0-3])\s*(?::|h|H)\s*([0-5]\d)(?!\d)",
        texte
    )

    if not correspondance:
        return None

    heure = int(correspondance.group(1))
    minutes = correspondance.group(2)

    return f"{heure:02d}:{minutes}"


def est_une_heure(texte):

    return extraire_heure(texte) is not None


def est_un_score(texte):

    return re.match(
        r"^\d+\s*-\s*\d+$",
        texte
    ) is not None


def convertir_score(texte):

    morceaux = re.split(
        r"\s*-\s*",
        texte
    )

    return (
        int(morceaux[0]),
        int(morceaux[1])
    )


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
    heure_actuelle = None
    equipes_trouvees = []
    score_en_attente = None

    for ligne in lignes:

        # Nouvelle date
        if est_une_date(ligne):

            date_actuelle = ligne
            heure_actuelle = extraire_heure(ligne)

            equipes_trouvees = []
            score_en_attente = None

            continue

        # Heure présente sur une ligne séparée
        heure_detectee = extraire_heure(ligne)

        if heure_detectee is not None:

            heure_actuelle = heure_detectee
            continue

        # Score du match
        if est_un_score(ligne):

            score_en_attente = convertir_score(ligne)

            continue

        # Séparateur présent sur la page
        if ligne == "-":

            continue

        # Équipe détectée
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
                    "heure": heure_actuelle,
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

                # Réinitialisation après chaque match
                equipes_trouvees = []
                score_en_attente = None
                heure_actuelle = None

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

                for match in matchs:

                    print(
                        f"  {match['domicile']} - "
                        f"{match['exterieur']} | "
                        f"Heure : {match['heure']}"
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
