from playwright.sync_api import sync_playwright
import json
import re


BASE_URL = "https://prod2.lnr.fr/calendrier-et-resultats/2026-2027"


def nettoyer_lignes(texte):
    lignes = []

    for ligne in texte.splitlines():
        ligne = ligne.strip()

        if ligne:
            lignes.append(ligne)

    return lignes


def est_score(texte):
    return re.match(r"^\d+\s*-\s*\d+$", texte) is not None


def recuperer_matchs(texte, journee):
    lignes = nettoyer_lignes(texte)

    matchs = []

    # On cherche le début de la journée
    debut = -1

    for i, ligne in enumerate(lignes):

        if (
            ligne.upper() == f"JOURNÉE {journee}"
            or ligne.upper() == f"J{journee}"
        ):
            debut = i
            break

    if debut == -1:
        print(f"⚠ Journée J{journee} introuvable dans la page")
        return []

    lignes = lignes[debut:]

    date_actuelle = None
    i = 0

    while i < len(lignes):

        ligne = lignes[i]

        # Arrêt lorsqu'on arrive au bas de la page
        if ligne in [
            "LES AVANTAGES",
            "NOS PARTENAIRES",
            "BONS PLANS, CONTENUS EXCLUSIFS,"
        ]:
            break

        # Une date est généralement en majuscules
        if (
            ligne.startswith("JEUDI")
            or ligne.startswith("VENDREDI")
            or ligne.startswith("SAMEDI")
            or ligne.startswith("DIMANCHE")
            or ligne.startswith("LUNDI")
        ):
            date_actuelle = ligne
            i += 1
            continue

        # Recherche d'un score
        if est_score(ligne):

            score = ligne.split("-")

            score_domicile = int(score[0].strip())
            score_exterieur = int(score[1].strip())

            # Recherche équipe domicile avant le score
            domicile = None

            for j in range(i - 1, max(i - 8, -1), -1):

                candidat = lignes[j]

                if (
                    candidat not in ["e", "Bo", "Bd"]
                    and not candidat.isdigit()
                    and not est_score(candidat)
                ):
                    domicile = candidat
                    break

            # Recherche équipe extérieure après le score
            exterieur = None

            for j in range(i + 1, min(i + 8, len(lignes))):

                candidat = lignes[j]

                if candidat == "Feuille de match":
                    break

                if (
                    candidat not in ["e", "Bo", "Bd"]
                    and not candidat.isdigit()
                    and not est_score(candidat)
                    and not candidat.startswith("Voir le résumé")
                ):
                    exterieur = candidat
                    break

            if domicile and exterieur:

                matchs.append({
                    "journee": f"J{journee}",
                    "date": date_actuelle,
                    "domicile": domicile,
                    "exterieur": exterieur,
                    "scoreDomicile": score_domicile,
                    "scoreExterieur": score_exterieur
                })

        # Match futur : score "-"
        elif ligne == "-":

            domicile = None
            exterieur = None

            for j in range(i - 1, max(i - 8, -1), -1):

                candidat = lignes[j]

                if (
                    candidat not in ["e", "Bo", "Bd"]
                    and not candidat.isdigit()
                ):
                    domicile = candidat
                    break

            for j in range(i + 1, min(i + 8, len(lignes))):

                candidat = lignes[j]

                if candidat == "Feuille de match":
                    break

                if (
                    candidat not in ["e", "Bo", "Bd"]
                    and not candidat.isdigit()
                ):
                    exterieur = candidat
                    break

            if domicile and exterieur:

                matchs.append({
                    "journee": f"J{journee}",
                    "date": date_actuelle,
                    "domicile": domicile,
                    "exterieur": exterieur,
                    "scoreDomicile": None,
                    "scoreExterieur": None
                })

        i += 1

    return matchs


def main():

    print("Ouverture du calendrier PRO D2...")

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
            print(f"Récupération de J{numero}...")

            url = f"{BASE_URL}/j{numero}"

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(3000)

                texte = page.locator("body").inner_text()

                matchs = recuperer_matchs(
                    texte,
                    numero
                )

                calendrier["journees"][f"J{numero}"] = matchs

                print(
                    f"✓ {len(matchs)} match(s) récupéré(s)"
                )

            except Exception as erreur:

                print(
                    f"⚠ Erreur J{numero} : {erreur}"
                )

                calendrier["journees"][f"J{numero}"] = []

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
