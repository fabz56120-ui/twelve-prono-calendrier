from playwright.sync_api import sync_playwright
import json
import re


URL = "https://prod2.lnr.fr/calendrier-et-resultats"


# =========================================================
# LISTE DES CLUBS
# =========================================================

CLUBS = [
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


# =========================================================
# EXTRACTION D'UNE JOURNEE
# =========================================================

def extraire_matchs(texte, numero_journee):

    lignes = []

    for ligne in texte.splitlines():

        ligne = ligne.strip()

        if ligne:
            lignes.append(ligne)

    # Recherche de la vraie section JOURNÉE X
    debut = None

    for i, ligne in enumerate(lignes):

        if ligne == f"JOURNÉE {numero_journee}":

            debut = i
            break

    if debut is None:

        print(
            f"⚠ JOURNÉE {numero_journee} introuvable"
        )

        return []

    # On garde uniquement la journée
    lignes = lignes[debut + 1:]

    fin = len(lignes)

    for i, ligne in enumerate(lignes):

        if ligne == "LES AVANTAGES":

            fin = i
            break

    lignes = lignes[:fin]


    # -----------------------------------------------
    # RECUPERATION DES DATES ET CLUBS
    # -----------------------------------------------

    matchs = []

    date_actuelle = None

    equipes_en_attente = []

    jours = [
        "LUNDI",
        "MARDI",
        "MERCREDI",
        "JEUDI",
        "VENDREDI",
        "SAMEDI",
        "DIMANCHE"
    ]

    for ligne in lignes:

        # Date
        if any(
            ligne.startswith(jour)
            for jour in jours
        ):

            date_actuelle = ligne

            continue


        # Equipe
        if ligne in CLUBS:

            equipes_en_attente.append(
                ligne
            )

            # Dès qu'on a 2 équipes = 1 match
            if len(equipes_en_attente) == 2:

                matchs.append({

                    "journee":
                        f"J{numero_journee}",

                    "date":
                        date_actuelle,

                    "domicile":
                        equipes_en_attente[0],

                    "exterieur":
                        equipes_en_attente[1],

                    "scoreDomicile":
                        None,

                    "scoreExterieur":
                        None
                })

                equipes_en_attente = []


    # -----------------------------------------------
    # RECUPERATION DES SCORES
    # -----------------------------------------------

    scores = []

    for ligne in lignes:

        resultat = re.match(
            r"^(\d+)\s*-\s*(\d+)$",
            ligne
        )

        if resultat:

            scores.append(

                (
                    int(resultat.group(1)),
                    int(resultat.group(2))
                )
            )


    # Attribution des scores dans l'ordre
    for i, score in enumerate(scores):

        if i >= len(matchs):
            break

        matchs[i]["scoreDomicile"] = score[0]
        matchs[i]["scoreExterieur"] = score[1]


    return matchs


# =========================================================
# SELECTION JOURNEE
# =========================================================

def selectionner_journee(page, journee):

    print(
        f"Sélection de {journee}"
    )

    # Recherche des éléments exacts J1, J2, etc.
    elements = page.get_by_text(
        journee,
        exact=True
    )

    for i in range(elements.count()):

        element = elements.nth(i)

        try:

            if element.is_visible():

                element.click()

                page.wait_for_timeout(1500)

                return True

        except Exception:

            pass


    print(
        f"⚠ Impossible de sélectionner {journee}"
    )

    return False


# =========================================================
# PROGRAMME PRINCIPAL
# =========================================================

def main():

    print(
        "Ouverture du calendrier officiel..."
    )

    calendrier_complet = {

        "source": URL,

        "saison": "2026-2027",

        "journees": {}
    }


    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        page.goto(

            URL,

            wait_until="domcontentloaded",

            timeout=60000
        )

        page.wait_for_timeout(
            5000
        )


        # -----------------------------------------------
        # J1 A J30
        # -----------------------------------------------

        for numero in range(1, 31):

            journee = f"J{numero}"

            print(
                f"\n===================="
            )

            print(
                f"RECUPERATION {journee}"
            )

            print(
                f"===================="
            )


            if not selectionner_journee(
                page,
                journee
            ):

                continue


            texte = page.locator(
                "body"
            ).inner_text()


            matchs = extraire_matchs(
                texte,
                numero
            )


            calendrier_complet[
                "journees"
            ][journee] = matchs


            print(
                f"✓ {len(matchs)} matchs"
            )


        # -----------------------------------------------
        # SAUVEGARDE
        # -----------------------------------------------

        with open(

            "calendrier.json",

            "w",

            encoding="utf-8"

        ) as fichier:

            json.dump(

                calendrier_complet,

                fichier,

                ensure_ascii=False,

                indent=4

            )


        # Debug de la dernière journée
        with open(

            "debug_calendrier.txt",

            "w",

            encoding="utf-8"

        ) as fichier:

            fichier.write(

                page.locator(
                    "body"
                ).inner_text()
            )


        print(
            "\n================================"
        )

        print(
            "✓ calendrier.json créé"
        )

        print(
            "================================"
        )


        browser.close()


if __name__ == "__main__":
    main()
