
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

    texte = unicodedata.normalize("NFD", texte)

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

    titres = [
        f"JOURNÉE {numero}",
        f"JOURNEE {numero}"
    ]

    position = -1

    for titre in titres:

        trouve = texte.rfind(titre)

        if trouve > position:
            position = trouve

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

    texte = texte.upper().strip()

    return any(
        texte.startswith(jour)
        for jour in jours
    )


def extraire_heure(texte):

    if not texte:
        return None

    motifs = [
        r"(?<!\d)([01]?\d|2[0-3])\s*:\s*([0-5]\d)(?!\d)",
        r"(?<!\d)([01]?\d|2[0-3])\s*[hH]\s*([0-5]\d)(?!\d)"
    ]

    for motif in motifs:

        resultat = re.search(
            motif,
            texte
        )

        if resultat:

            heure = int(resultat.group(1))
            minutes = resultat.group(2)

            return f"{heure:02d}:{minutes}"

    return None


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

        heure_ligne = extraire_heure(ligne)

        if est_une_date(ligne):

            date_actuelle = ligne
            heure_actuelle = heure_ligne

            equipes_trouvees = []
            score_en_attente = None

            continue

        if heure_ligne is not None:

            heure_actuelle = heure_ligne
            continue

        if est_un_score(ligne):

            score_en_attente = extraire_score(ligne)
            continue

        if ligne == "-":

            continue

        if ligne in EQUIPES:

            equipes_trouvees.append(ligne)

            if len(equipes_trouvees) == 2:

                domicile = equipes_trouvees[0]
                exterieur = equipes_trouvees[1]

                match = {
                    "id": creer_match_id(
                        f"J{numero}",
                        domicile,
                        exterieur,
                        date_actuelle
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

                    match["scoreDomicile"] = (
                        score_en_attente[0]
                    )

                    match["scoreExterieur"] = (
                        score_en_attente[1]
                    )

                matchs.append(match)

                equipes_trouvees = []
                score_en_attente = None

                # On ne supprime pas l'heure ici :
                # elle peut être réutilisée si le site
                # affiche l'heure avant le score.

    matchs_uniques = []
    deja_vus = set()

    for match in matchs:

        if match["id"] not in deja_vus:

            deja_vus.add(match["id"])
            matchs_uniques.append(match)

    return matchs_uniques


def main():

    print("Ouverture du calendrier officiel...")

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
                    wait_until="networkidle",
                    timeout=60000
                )

                page.wait_for_timeout(5000)

                # Défilement pour déclencher le chargement
                page.evaluate("""
                    window.scrollTo(
                        0,
                        document.body.scrollHeight
                    );
                """)

                page.wait_for_timeout(2000)

                texte = page.locator(
                    "body"
                ).inner_text()

                # Sauvegarde du texte pour diagnostic
                with open(
                    f"debug_J{numero}.txt",
                    "w",
                    encoding="utf-8"
                ) as debug:

                    debug.write(texte)

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
                        f"  {match['date']} | "
                        f"{match['heure']} | "
                        f"{match['domicile']} - "
                        f"{match['exterieur']} | "
                        f"{match['scoreDomicile']} - "
                        f"{match['scoreExterieur']}"
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
