from playwright.sync_api import sync_playwright
import json
import re
import time


URL = "https://prod2.lnr.fr/calendrier-et-resultats"

JOURNEES = [f"J{i}" for i in range(1, 31)]


def nettoyer_lignes(texte):

    lignes = []

    for ligne in texte.splitlines():

        ligne = ligne.strip()

        if ligne:
            lignes.append(ligne)

    return lignes


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

    return any(jour in ligne.upper() for jour in jours)


def est_score(ligne):

    return re.match(r"^\d+\s*-\s*\d+$", ligne) is not None


def nettoyer_nom_equipe(ligne):

    a_ignorer = [
        "e",
        "Bo",
        "Bd",
        "Feuille de match",
        "Voir le résumé",
        "Billetterie",
        "Covoiturer"
    ]

    if ligne in a_ignorer:
        return None

    if re.match(r"^\d+$", ligne):
        return None

    if est_score(ligne):
        return None

    return ligne


def extraire_matchs(texte, journee):

    lignes = nettoyer_lignes(texte)

    matchs = []

    numero_journee = journee.replace("J", "")

    debut = None

    for i, ligne in enumerate(lignes):

        if ligne.upper() == f"JOURNÉE {numero_journee}":
            debut = i
            break

    if debut is None:
        print(f"⚠ JOURNÉE {journee} introuvable")
        return matchs

    fin = len(lignes)

    mots_fin = [
        "LES AVANTAGES",
        "NOS PARTENAIRES",
        "BON PLAN"
    ]

    for i in range(debut + 1, len(lignes)):

        if lignes[i] in mots_fin:
            fin = i
            break

    lignes = lignes[debut + 1:fin]

    date_actuelle = None
    index = 0

    while index < len(lignes):

        ligne = lignes[index]

        if est_date(ligne):

            date_actuelle = ligne
            index += 1
            continue

        if est_score(ligne):

            score = ligne

            try:

                score_domicile, score_exterieur = [
                    int(x.strip())
                    for x in score.split("-")
                ]

            except:
                index += 1
                continue

            domicile = None

            # Recherche équipe domicile avant le score
            recherche = index - 1

            while recherche >= 0:

                candidat = nettoyer_nom_equipe(
                    lignes[recherche]
                )

                if candidat:

                    domicile = candidat
                    break

                recherche -= 1

            exterieur = None

            # Recherche équipe extérieure après le score
            recherche = index + 1

            while recherche < len(lignes):

                candidat = nettoyer_nom_equipe(
                    lignes[recherche]
                )

                if candidat:

                    exterieur = candidat
                    break

                recherche += 1

            if domicile and exterieur:

                match = {
                    "journee": journee,
                    "date": date_actuelle,
                    "domicile": domicile,
                    "exterieur": exterieur,
                    "scoreDomicile": score_domicile,
                    "scoreExterieur": score_exterieur
                }

                matchs.append(match)

            index += 1
            continue

        index += 1

    return matchs


def cliquer_journee(page, journee):

    print(f"Sélection de {journee}...")

    numero = journee.replace("J", "")

    selecteurs = [
        f"xpath=//*[normalize-space(text())='{journee}']",
        f"xpath=//*[@role='option' and normalize-space(.)='{journee}']",
        f"xpath=//button[normalize-space(.)='{journee}']",
        f"xpath=//*[normalize-space(.)='{journee}']"
    ]

    for selecteur in selecteurs:

        try:

            elements = page.locator(selecteur)

            total = elements.count()

            for i in range(total):

                element = elements.nth(i)

                try:

                    if element.is_visible():

                        # Scroll jusqu'à l'élément
                        element.scroll_into_view_if_needed()

                        # Clic JavaScript pour les éléments custom
                        element.evaluate(
                            "(el) => el.click()"
                        )

                        # Attente du chargement
                        page.wait_for_timeout(1500)

                        texte = page.locator(
                            "body"
                        ).inner_text()

                        if (
                            f"JOURNÉE {numero}" in texte
                        ):

                            print(
                                f"✓ {journee} sélectionnée"
                            )

                            return True

                except:
                    pass

        except:
            pass

    print(
        f"⚠ Impossible de sélectionner {journee}"
    )

    return False


def main():

    print(
        "Ouverture du calendrier officiel..."
    )

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

        calendrier = {
            "source": URL,
            "saison": "2026-2027",
            "journees": {}
        }

        for journee in JOURNEES:

            print("")
            print(
                "================================="
            )

            selection_ok = cliquer_journee(
                page,
                journee
            )

            if not selection_ok:

                continue

            texte = page.locator(
                "body"
            ).inner_text()

            matchs = extraire_matchs(
                texte,
                journee
            )

            calendrier["journees"][journee] = matchs

            print(
                f"✓ {len(matchs)} match(s) récupéré(s)"
            )

            # Sauvegarde après chaque journée
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

        # Sauvegarde debug finale
        texte_final = page.locator(
            "body"
        ).inner_text()

        with open(
            "debug_calendrier.txt",
            "w",
            encoding="utf-8"
        ) as fichier:

            fichier.write(
                texte_final
            )

        browser.close()

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
