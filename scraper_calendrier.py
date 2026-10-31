from playwright.sync_api import sync_playwright
import json
import re
import unicodedata

BASE_URL = "https://prod2.lnr.fr/calendrier-et-resultats/2026-2027"
RUGBYRAMA_URL = "https://www.rugbyrama.fr/resultats/rugby/pro-d2/calendrier"

EQUIVALENCES_RUGBYRAMA = {
    "BIARRITZ": "Biarritz Olympique PB",
    "NICE": "Nissa Rugby",
    "ANGOULEME": "Soyaux-Angoulême XV",
    "COLOMIERS": "Colomiers Rugby",
    "BEZIERS": "AS Béziers Hérault",
    "OYONNAX": "Oyonnax Rugby",
    "GRENOBLE": "FC Grenoble Rugby",
    "AURILLAC": "Stade Aurillacois",
    "NEVERS": "USON Nevers",
    "MONTAUBAN": "US Montauban",
    "DAX": "US Dax",
    "NARBONNE": "RC Narbonnais",
    "PROVENCE RUGBY": "Provence Rugby",
    "AGEN": "SU Agen",
    "BRIVE": "CA Brive",
    "VALENCE ROMANS": "Valence Romans",
}

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
        c for c in texte
        if unicodedata.category(c) != "Mn"
    )
    texte = texte.upper()

    return re.sub(
        r"[^A-Z0-9]+", "_", texte
    ).strip("_")


def nettoyer_ligne(ligne):
    if not ligne:
        return ""

    ligne = ligne.replace("**", "")
    ligne = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        ligne
    )

    return ligne.replace("\xa0", " ").strip()


def nettoyer_lignes(texte):
    return [
        nettoyer_ligne(l)
        for l in texte.splitlines()
        if nettoyer_ligne(l)
    ]


# NOUVEL ID : SANS DATE
def creer_match_id(journee, domicile, exterieur, date=None):
    return "_".join([
        normaliser_texte(journee),
        normaliser_texte(domicile),
        normaliser_texte(exterieur)
    ])


def extraire_section_journee(texte, numero):
    motifs = [
        f"JOURNÉE {numero}",
        f"JOURNEE {numero}",
        f"Journée {numero}",
        f"Journee {numero}"
    ]

    position = next(
        (
            texte.find(m)
            for m in motifs
            if texte.find(m) != -1
        ),
        -1
    )

    if position == -1:
        return ""

    section = texte[position:]

    positions = [
        p
        for m in [
            "LES AVANTAGES",
            "NOS PARTENAIRES",
            "BON PLAN"
        ]
        if (p := section.find(m)) != -1
    ]

    return section[:min(positions)] if positions else section


def est_une_date(texte):
    jours = (
        "LUNDI MARDI MERCREDI JEUDI "
        "VENDREDI SAMEDI DIMANCHE"
    ).split()

    texte = nettoyer_ligne(texte).upper()

    return any(
        texte.startswith(j + " ")
        for j in jours
    )


def extraire_heure(texte):
    if not texte:
        return None

    m = re.search(
        r"(?<!\d)([01]?\d|2[0-3])\s*(?::|[hH])\s*([0-5]\d)(?!\d)",
        texte
    )

    return (
        f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        if m else None
    )


def est_un_score(texte):
    return re.fullmatch(
        r"\d+\s*-\s*\d+",
        texte.strip()
    ) is not None


def extraire_score(texte):
    a, b = re.split(
        r"\s*-\s*",
        texte.strip()
    )

    return int(a), int(b)


def trouver_equipe(texte):
    n = normaliser_texte(texte)

    for equipe in EQUIPES:
        if normaliser_texte(equipe) == n:
            return equipe

    return EQUIVALENCES_RUGBYRAMA.get(n)


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

    for ligne in nettoyer_lignes(section):

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

        equipe = trouver_equipe(ligne)

        if not equipe:
            continue

        equipes_trouvees.append(equipe)

        if len(equipes_trouvees) < 2:
            continue

        domicile, exterieur = equipes_trouvees[:2]

        match = {
            "id": creer_match_id(
                f"J{numero}",
                domicile,
                exterieur
            ),
            "journee": f"J{numero}",
            "date": date_actuelle,
            "heure": heure_actuelle,
            "domicile": domicile,
            "exterieur": exterieur,
            "scoreDomicile": (
                score_en_attente[0]
                if score_en_attente else None
            ),
            "scoreExterieur": (
                score_en_attente[1]
                if score_en_attente else None
            )
        }

        matchs.append(match)

        equipes_trouvees = []
        score_en_attente = None
        heure_actuelle = None

    uniques = []
    vus = set()

    for match in matchs:
        if match["id"] not in vus:
            vus.add(match["id"])
            uniques.append(match)

    return uniques


def cle_match(domicile, exterieur):
    return frozenset((
        normaliser_texte(domicile),
        normaliser_texte(exterieur)
    ))


def cle_match_ordonnee(match):
    return (
        normaliser_texte(match.get("journee", "")),
        normaliser_texte(match.get("domicile", "")),
        normaliser_texte(match.get("exterieur", ""))
    )


def extraire_matchs_rugbyrama(texte):
    lignes = nettoyer_lignes(texte)
    resultats = []

    for i, ligne in enumerate(lignes):
        heure = extraire_heure(ligne)

        if not heure or heure == "00:00":
            continue

        equipes = []
        j = i + 1

        while j < len(lignes):
            candidate = lignes[j]

            if j > i + 20:
                break

            if j > i + 1 and extraire_heure(candidate):
                break

            equipe = trouver_equipe(candidate)

            if equipe and equipe not in equipes:
                equipes.append(equipe)

                if len(equipes) == 2:
                    resultats.append({
                        "domicile": equipes[0],
                        "exterieur": equipes[1],
                        "heure": heure
                    })
                    break

            j += 1

    uniques = []
    vus = set()

    for match in resultats:
        cle = (
            cle_match(
                match["domicile"],
                match["exterieur"]
            ),
            match["heure"]
        )

        if cle not in vus:
            vus.add(cle)
            uniques.append(match)

    return uniques


def numero_journee(nom):
    correspondance = re.fullmatch(
        r"J(\d+)",
        nom
    )

    return (
        int(correspondance.group(1))
        if correspondance else 9999
    )


def fusionner_calendrier(ancien, nouveau):

    resultat = {
        "source": nouveau.get(
            "source",
            ancien.get("source", BASE_URL)
        ),
        "saison": nouveau.get(
            "saison",
            ancien.get("saison", "2026-2027")
        ),
        "journees": {}
    }

    toutes_journees = (
        set(ancien.get("journees", {}))
        | set(nouveau.get("journees", {}))
    )

    for journee in sorted(
        toutes_journees,
        key=numero_journee
    ):

        anciens_matchs = (
            ancien.get("journees", {}).get(journee, [])
            or []
        )

        nouveaux_matchs = (
            nouveau.get("journees", {}).get(journee, [])
            or []
        )

        anciens_index = {
            cle_match_ordonnee(match): match
            for match in anciens_matchs
        }

        fusionnes = []
        cles_vues = set()

        for nouveau_match in nouveaux_matchs:

            cle = cle_match_ordonnee(nouveau_match)

            ancien_match = anciens_index.get(
                cle,
                {}
            )

            match = dict(ancien_match)
            match.update(nouveau_match)

            # CONSERVATION DE L'ANCIEN ID
            if ancien_match.get("id"):
                match["id"] = ancien_match["id"]

            # Conservation des anciennes données
            # si la récupération ne fournit rien.
            for champ in (
                "date",
                "heure",
                "scoreDomicile",
                "scoreExterieur"
            ):

                if (
                    nouveau_match.get(champ) in (None, "")
                    and ancien_match.get(champ) not in (None, "")
                ):
                    match[champ] = ancien_match[champ]

            fusionnes.append(match)
            cles_vues.add(cle)

        # Conservation des anciens matchs non récupérés.
        for ancien_match in anciens_matchs:

            cle = cle_match_ordonnee(
                ancien_match
            )

            if cle not in cles_vues:
                fusionnes.append(ancien_match)

        resultat["journees"][journee] = fusionnes

    return resultat


def completer_heures(calendrier, horaires_rr):

    index = {}

    for item in horaires_rr:
        index.setdefault(
            cle_match(
                item["domicile"],
                item["exterieur"]
            ),
            []
        ).append(item["heure"])

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
                h for h in heures
                if h != "00:00"
            ]

            if len(set(heures)) == 1:
                match["heure"] = heures[0]
                complets += 1

    return complets


def main():

    ancien_calendrier = {
        "source": BASE_URL,
        "saison": "2026-2027",
        "journees": {}
    }

    try:
        with open(
            "calendrier.json",
            "r",
            encoding="utf-8"
        ) as fichier:

            ancien_calendrier = json.load(fichier)

        print(
            "✓ Ancien calendrier chargé "
            "pour préserver les IDs et les données"
        )

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        print(
            "⚠ Aucun calendrier précédent exploitable"
        )

    calendrier_brut = {
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
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(8000)

                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )

                page.wait_for_timeout(2000)

                texte = page.locator(
                    "body"
                ).inner_text()

                with open(
                    f"debug_J{numero}.txt",
                    "w",
                    encoding="utf-8"
                ) as f:

                    f.write(texte)

                matchs = extraire_matchs(
                    texte,
                    numero
                )

                calendrier_brut["journees"][
                    f"J{numero}"
                ] = matchs

                print(
                    f"✓ {len(matchs)} match(s)"
                )

            except Exception as erreur:

                print(
                    f"⚠ Première tentative échouée "
                    f"pour J{numero}: {erreur}"
                )

                try:

                    page.goto(
                        f"{BASE_URL}/j{numero}",
                        wait_until="commit",
                        timeout=60000
                    )

                    page.wait_for_timeout(10000)

                    page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight)"
                    )

                    page.wait_for_timeout(2000)

                    texte = page.locator(
                        "body"
                    ).inner_text()

                    with open(
                        f"debug_J{numero}.txt",
                        "w",
                        encoding="utf-8"
                    ) as f:

                        f.write(texte)

                    matchs = extraire_matchs(
                        texte,
                        numero
                    )

                    calendrier_brut["journees"][
                        f"J{numero}"
                    ] = matchs

                    print(
                        f"✓ Deuxième tentative : "
                        f"{len(matchs)} match(s)"
                    )

                except Exception as seconde_erreur:

                    print(
                        f"⚠ Échec définitif J{numero}: "
                        f"{seconde_erreur}"
                    )

                    calendrier_brut["journees"][
                        f"J{numero}"
                    ] = []

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

            texte_rr = page.locator(
                "body"
            ).inner_text()

            with open(
                "debug_rugbyrama.txt",
                "w",
                encoding="utf-8"
            ) as f:

                f.write(texte_rr)

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

    # Fusion avec les données précédentes.
    calendrier = fusionner_calendrier(
        ancien_calendrier,
        calendrier_brut
    )

    complets = completer_heures(
        calendrier,
        horaires_rr
    )

    print(
        f"✓ {complets} heure(s) complétée(s) depuis Rugbyrama"
    )

    # Vérification de la présence des 30 journées.
    for numero in range(1, 31):

        journee = f"J{numero}"

        if journee not in calendrier["journees"]:
            calendrier["journees"][journee] = []

    # Tri final garanti.
    calendrier["journees"] = {
        journee: calendrier["journees"][journee]
        for journee in sorted(
            calendrier["journees"],
            key=numero_journee
        )
    }

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

    print(
        "✓ Journées rangées de J1 à J30"
    )


if __name__ == "__main__":
    main()
