from playwright.sync_api import sync_playwright
import json
import re


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
# EXTRACTION D'UNE JOURNEE
# =========================================================

def extraire_matchs(texte, numero_journee):

    lignes = [
        ligne.strip()
        for ligne in texte.splitlines()
        if ligne.strip()
    ]

    # Cherche la vraie section JOURNÉE X
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


    # On garde uniquement le contenu après JOURNÉE X
    lignes = lignes[debut + 1:]


    # On s'arrête avant la publicité
    fin = len(lignes)

    for i, ligne in enumerate(lignes):

        if ligne == "LES AVANTAGES":

            fin = i
            break

    lignes = lignes[:fin]


    # -----------------------------------------------------
    # EXTRACTION DES MATCHS
    # -----------------------------------------------------

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


        # -------------------------
        # DATE
        # -------------------------

        if any(
            ligne.startswith(jour)
            for jour in jours
        ):

            date_actuelle = ligne

            continue


        # -------------------------
        # EQUIPE
        # -------------------------

        if ligne in CLUBS:

            equipes_en_attente.append(ligne)


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


    # -----------------------------------------------------
    # SCORES
    # -----------------------------------------------------

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
# SELECTION D'UNE JOURNEE
# =========================================================

def selectionner_journee(
    page,
    numero
):

    journee = f"J{numero}"

    print(
        f"\nSélection de {journee}..."
    )


    # Tous les éléments qui affichent J1, J2, etc.
    elements = page.get_by_text(
        journee,
        exact=True
    )


    for i in range(elements.count()):

        element = elements.nth(i)

        try:

            if element.is_visible():

                # Clic sur la journée
                element.click()

                # Attend le changement réel du contenu
                page.wait_for_function(
                    """
                    (numero) => {
                        return document.body.innerText.includes(
                            "JOURNÉE " + numero
                        );
                    }
                    """,
                    numero,
                    timeout=10000
                )


                page.wait_for_timeout(1000)


                print(
                    f"✓ JOURNÉE {numero} chargée"
                )

                return True


        except Exception as erreur:

            continue


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


        print(
            "Page chargée."
        )


        # =================================================
        # RECUPERATION J1 → J30
        # =================================================

        for numero in range(1, 31):


            if not selectionner_journee(
                page,
                numero
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
            ][f"J{numero}"] = matchs


            print(
                f"✓ J{numero} : "
                f"{len(matchs)} matchs récupérés"
            )


        # =================================================
        # SAUVEGARDE JSON
        # =================================================

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


        print(
            "\n================================="
        )

        print(
            "✓ calendrier.json créé"
        )

        print(
            "================================="
        )


        # Debug de la dernière page affichée
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
