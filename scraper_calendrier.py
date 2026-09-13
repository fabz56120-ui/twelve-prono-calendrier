from playwright.sync_api import sync_playwright
import json
import re
import time


URL = "https://prod2.lnr.fr/calendrier-et-resultats"


# =========================================================
# CLUBS PRO D2
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
# RECUPERATION DES MATCHS DANS LE TEXTE
# =========================================================

def extraire_matchs(texte, numero_journee):

    lignes = [
        ligne.strip()
        for ligne in texte.splitlines()
        if ligne.strip()
    ]

    # On se place uniquement dans la partie de la journée
    debut = -1

    for i, ligne in enumerate(lignes):

        if ligne == f"JOURNÉE {numero_journee}":
            debut = i
            break

    if debut == -1:

        print(
            f"Impossible de trouver JOURNÉE {numero_journee}"
        )

        return []

    lignes = lignes[debut + 1:]

    # On coupe avant les avantages / publicité
    fin = len(lignes)

    for i, ligne in enumerate(lignes):

        if ligne == "LES AVANTAGES":
            fin = i
            break

    lignes = lignes[:fin]

    matchs = []

    date_actuelle = ""
    equipes_trouvees = []

    for ligne in lignes:

        # Dates
        if (
            ligne.startswith("LUNDI")
            or ligne.startswith("MARDI")
            or ligne.startswith("MERCREDI")
            or ligne.startswith("JEUDI")
            or ligne.startswith("VENDREDI")
            or ligne.startswith("SAMEDI")
            or ligne.startswith("DIMANCHE")
        ):

            date_actuelle = ligne

            continue

        # Equipe connue
        if ligne in CLUBS:

            equipes_trouvees.append(ligne)

        # Score
        if re.match(r"^\d+\s*-\s*\d+$", ligne):

            score = ligne

            # On doit avoir les deux équipes autour du score
            if len(equipes_trouvees) >= 1:

                equipe_domicile = equipes_trouvees[-1]

                matchs.append({
                    "journee": f"J{numero_journee}",
                    "date": date_actuelle,
                    "domicile": equipe_domicile,
                    "score": score,
                    "exterieur": ""
                })

    # Maintenant on attribue les équipes extérieures.
    # On reprend la séquence complète des clubs.
    equipes = [
        ligne
        for ligne in lignes
        if ligne in CLUBS
    ]

    index_equipe = 0

    for match in matchs:

        if index_equipe + 1 < len(equipes):

            match["domicile"] = equipes[index_equipe]
            match["exterieur"] = equipes[index_equipe + 1]

            index_equipe += 2

    return matchs


# =========================================================
# SELECTION D'UNE JOURNEE
# =========================================================

def selectionner_journee(page, journee):

    print(f"Sélection de {journee}...")

    # -----------------------------------------------------
    # Cas 1 : le site utilise un <select>
    # -----------------------------------------------------

    selects = page.locator("select")

    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            options = select.locator("option").all_text_contents()

            if journee in options:

                select.select_option(
                    label=journee
                )

                page.wait_for_timeout(3000)

                return True

        except Exception:
            pass

    # -----------------------------------------------------
    # Cas 2 : bouton / élément personnalisé
    # -----------------------------------------------------

    elements = page.get_by_text(
        journee,
        exact=True
    )

    for i in range(elements.count()):

        element = elements.nth(i)

        try:

            if element.is_visible():

                element.click()

                page.wait_for_timeout(3000)

                return True

        except Exception:
            pass

    print(
        f"Impossible de sélectionner {journee}"
    )

    return False


# =========================================================
# PROGRAMME PRINCIPAL
# =========================================================

def main():

    print(
        "Ouverture du calendrier officiel..."
    )

    calendrier_complet = []

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

        page.wait_for_timeout(5000)

        print(
            "Page HTML chargée."
        )

        # -------------------------------------------------
        # RECUPERATION DES JOURNEES J1 A J30
        # -------------------------------------------------

        for numero in range(1, 31):

            journee = f"J{numero}"

            print(
                f"\n========== {journee} =========="
            )

            succes = selectionner_journee(
                page,
                journee
            )

            if not succes:

                continue

            texte = page.locator(
                "body"
            ).inner_text()

            matchs = extraire_matchs(
                texte,
                numero
            )

            print(
                f"{len(matchs)} matchs trouvés."
            )

            calendrier_complet.extend(
                matchs
            )

        # -------------------------------------------------
        # SAUVEGARDE JSON
        # -------------------------------------------------

        resultat = {
            "source": URL,
            "calendrier": calendrier_complet
        }

        with open(
            "calendrier.json",
            "w",
            encoding="utf-8"
        ) as fichier:

            json.dump(
                resultat,
                fichier,
                ensure_ascii=False,
                indent=4
            )

        print(
            "\n================================"
        )

        print(
            f"TOTAL : {len(calendrier_complet)} matchs."
        )

        print(
            "calendrier.json créé."
        )

        # -------------------------------------------------
        # DEBUG
        # -------------------------------------------------

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

        browser.close()


if __name__ == "__main__":
    main()
