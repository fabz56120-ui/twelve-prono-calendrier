from playwright.sync_api import sync_playwright
import json
import re


URL = "https://prod2.lnr.fr/calendrier-et-resultats"

JOURNEES = [f"J{i}" for i in range(1, 31)]


def nettoyer_lignes(texte):

    return [
        ligne.strip()
        for ligne in texte.splitlines()
        if ligne.strip()
    ]


def est_date(ligne):

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
        jour in ligne.upper()
        for jour in jours
    )


def est_score(ligne):

    return re.match(
        r"^\d+\s*-\s*\d+$",
        ligne
    ) is not None


def est_match_futur(ligne):

    return ligne.strip() == "-"


def est_a_ignorer(ligne):

    mots = [
        "e",
        "Bo",
        "Bd",
        "Feuille de match",
        "Voir le résumé",
        "Billetterie",
        "Covoiturer"
    ]

    if ligne in mots:
        return True

    if re.match(r"^\d+$", ligne):
        return True

    if est_score(ligne):
        return True

    if est_match_futur(ligne):
        return True

    return False


def extraire_matchs(texte, journee):

    lignes = nettoyer_lignes(texte)

    matchs = []

    numero = journee.replace("J", "")

    # Recherche de JOURNÉE X
    debut = None

    for i, ligne in enumerate(lignes):

        if ligne.upper() == f"JOURNÉE {numero}":

            debut = i + 1
            break

    if debut is None:

        print(f"⚠ JOURNÉE {numero} introuvable")

        return matchs

    # Fin de la zone de la journée
    fin = len(lignes)

    marqueurs_fin = [
        "LES AVANTAGES",
        "NOS PARTENAIRES",
        "BON PLAN"
    ]

    for i in range(debut, len(lignes)):

        if lignes[i] in marqueurs_fin:

            fin = i
            break

    contenu = lignes[debut:fin]

    date_actuelle = None
    index = 0

    while index < len(contenu):

        ligne = contenu[index]

        # ----------------------------------------
        # DATE
        # ----------------------------------------

        if est_date(ligne):

            date_actuelle = ligne

            index += 1
            continue

        # ----------------------------------------
        # SCORE TERMINÉ
        # Exemple : 38 - 20
        # ----------------------------------------

        if est_score(ligne):

            score_domicile, score_exterieur = [
                int(x.strip())
                for x in ligne.split("-")
            ]

            domicile = None
            exterieur = None

            # Équipe domicile avant le score
            recherche = index - 1

            while recherche >= 0:

                candidat = contenu[recherche]

                if not est_a_ignorer(candidat):

                    domicile = candidat
                    break

                recherche -= 1

            # Équipe extérieure après le score
            recherche = index + 1

            while recherche < len(contenu):

                candidat = contenu[recherche]

                if not est_a_ignorer(candidat):

                    exterieur = candidat
                    break

                recherche += 1

            if domicile and exterieur:

                matchs.append({
                    "journee": journee,
                    "date": date_actuelle,
                    "domicile": domicile,
                    "exterieur": exterieur,
                    "scoreDomicile": score_domicile,
                    "scoreExterieur": score_exterieur
                })

            index += 1
            continue

        # ----------------------------------------
        # MATCH FUTUR
        # Exemple :
        #
        # Equipe domicile
        # 4
        # e
        #
        # -
        #
        # Equipe extérieure
        # ----------------------------------------

        if est_match_futur(ligne):

            domicile = None
            exterieur = None

            # Équipe domicile avant le "-"
            recherche = index - 1

            while recherche >= 0:

                candidat = contenu[recherche]

                if not est_a_ignorer(candidat):

                    domicile = candidat
                    break

                recherche -= 1

            # Équipe extérieure après le "-"
            recherche = index + 1

            while recherche < len(contenu):

                candidat = contenu[recherche]

                if not est_a_ignorer(candidat):

                    exterieur = candidat
                    break

                recherche += 1

            if domicile and exterieur:

                matchs.append({
                    "journee": journee,
                    "date": date_actuelle,
                    "domicile": domicile,
                    "exterieur": exterieur,
                    "scoreDomicile": None,
                    "scoreExterieur": None
                })

            index += 1
            continue

        index += 1

    return matchs


def trouver_select_journee(page):

    selects = page.locator("select")

    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            if not select.is_visible():
                continue

            options = select.locator(
                "option"
            ).all_text_contents()

            options = [
                option.strip()
                for option in options
            ]

            if "J1" in options and "J30" in options:

                return select

        except Exception:
            pass

    return None


def cliquer_journee(page, journee):

    print(f"Sélection de {journee}...")

    numero = journee.replace("J", "")

    # ----------------------------------------
    # Vrai SELECT
    # ----------------------------------------

    select = trouver_select_journee(page)

    if select is not None:

        try:

            select.select_option(
                label=journee
            )

            page.wait_for_timeout(2000)

            texte = page.locator(
                "body"
            ).inner_text()

            if f"JOURNÉE {numero}" in texte:

                print(f"✓ {journee} sélectionnée")

                return True

        except Exception as erreur:

            print(
                f"Erreur select {journee}: {erreur}"
            )

    # ----------------------------------------
    # Menu personnalisé
    # ----------------------------------------

    try:

        labels = page.get_by_text(
            "Journée",
            exact=True
        )

        for i in range(labels.count()):

            label = labels.nth(i)

            if not label.is_visible():
                continue

            label.click()

            page.wait_for_timeout(500)

            options = page.get_by_text(
                journee,
                exact=True
            )

            for j in range(options.count()):

                option = options.nth(j)

                if not option.is_visible():
                    continue

                option.scroll_into_view_if_needed()

                option.click()

                page.wait_for_timeout(2500)

                texte = page.locator(
                    "body"
                ).inner_text()

                if f"JOURNÉE {numero}" in texte:

                    print(
                        f"✓ {journee} sélectionnée"
                    )

                    return True

    except Exception:
        pass

    print(
        f"⚠ Impossible de sélectionner {journee}"
    )

    return False


def main():

    print(
        "Ouverture du calendrier officiel..."
    )

    calendrier = {
        "source": URL,
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

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(5000)

        print("Page chargée.")

        for journee in JOURNEES:

            print("")
            print(
                "================================="
            )

            if not cliquer_journee(
                page,
                journee
            ):

                continue

            texte = page.locator(
                "body"
            ).inner_text()

            matchs = extraire_matchs(
                texte,
                journee
            )

            calendrier["journees"][
                journee
            ] = matchs

            print(
                f"✓ {len(matchs)} match(s) récupéré(s)"
            )

            # Sauvegarde progressive
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

        browser.close()

    # Sauvegarde finale
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

    print("")
    print(
        "================================="
    )

    print(
        "✓ calendrier.json créé"
    )

    print(
        "================================="
    )


if __name__ == "__main__":
    main()
