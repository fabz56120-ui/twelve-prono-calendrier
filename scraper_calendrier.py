
from playwright.sync_api import sync_playwright
import json
import re
import unicodedata
import os

BASE_URL = "https://prod2.lnr.fr/calendrier-et-resultats/2026-2027"
RUGBYRAMA_URL = "https://www.rugbyrama.fr/resultats/rugby/pro-d2/calendrier"
FICHIER_JSON = "calendrier.json"

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
    "PROVENCE_RUGBY": "Provence Rugby",
    "AGEN": "SU Agen",
    "BRIVE": "CA Brive",
    "VALENCE_ROMANS": "Valence Romans",
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
    "SU Agen",
]


# --------------------------------------------------
# NORMALISATION
# --------------------------------------------------

def normaliser_texte(texte):
    if not texte:
        return ""

    texte = unicodedata.normalize("NFD", str(texte))
    texte = "".join(
        c for c in texte
        if unicodedata.category(c) != "Mn"
    )
    texte = texte.upper()

    return re.sub(r"[^A-Z0-9]+", "_", texte).strip("_")


def nettoyer_ligne(ligne):
    if not ligne:
        return ""

    ligne = ligne.replace("**", "")
    ligne = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", ligne)

    return ligne.replace("\xa0", " ").strip()


def nettoyer_lignes(texte):
    return [
        nettoyer_ligne(ligne)
        for ligne in texte.splitlines()
        if nettoyer_ligne(ligne)
    ]


def trouver_equipe(texte):
    n = normaliser_texte(texte)

    for equipe in EQUIPES:
        if normaliser_texte(equipe) == n:
            return equipe

    return EQUIVALENCES_RUGBYRAMA.get(n)


def cle_match(domicile, exterieur):
    return (
        normaliser_texte(domicile),
        normaliser_texte(exterieur)
    )


def creer_match_id(journee, domicile, exterieur, date):
    return "_".join([
        normaliser_texte(journee),
        normaliser_texte(domicile),
        normaliser_texte(exterieur),
        normaliser_texte(date)
    ])


# --------------------------------------------------
# DATES, HEURES ET SCORES
# --------------------------------------------------

def est_une_date(texte):
    jours = (
        "LUNDI MARDI MERCREDI JEUDI "
        "VENDREDI SAMEDI DIMANCHE"
    ).split()

    texte = nettoyer_ligne(texte).upper()

    return any(texte.startswith(j + " ") for j in jours)


def extraire_heure(texte):
    if not texte:
        return None

    m = re.search(
        r"(?<!\d)([01]?\d|2[0-3])\s*(?::|[hH])\s*([0-5]\d)(?!\d)",
        texte
    )

    if not m:
        return None

    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"


def est_un_score(texte):
    return re.fullmatch(
        r"\d+\s*-\s*\d+",
        texte.strip()
    ) is not None


def extraire_score(texte):
    a, b = re.split(r"\s*-\s*", texte.strip())
    return int(a), int(b)


def match_deja_joue(match):
    return (
        match.get("scoreDomicile") is not None
        and match.get("scoreExterieur") is not None
    )


# --------------------------------------------------
# EXTRACTION LNR
# --------------------------------------------------

def extraire_section_journee(texte, numero):
    motifs = [
        f"JOURNÉE {numero}",
        f"JOURNEE {numero}",
        f"Journée {numero}",
        f"Journee {numero}"
    ]

    position = next(
        (texte.find(m) for m in motifs if texte.find(m) != -1),
        -1
    )

    if position == -1:
        return ""

    section = texte[position:]

    positions = [
        p for m in ["LES AVANTAGES", "NOS PARTENAIRES", "BON PLAN"]
        if (p := section.find(m)) != -1
    ]

    return section[:min(positions)] if positions else section


def extraire_matchs(texte, numero):
    section = extraire_section_journee(texte, numero)

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
                exterieur,
                date_actuelle or ""
            ),
            "journee": f"J{numero}",
            "date": date_actuelle,
            "heure": heure_actuelle,
            "domicile": domicile,
            "exterieur": exterieur,
            "scoreDomicile": (
                score_en_attente[0]
                if score_en_attente is not None else None
            ),
            "scoreExterieur": (
                score_en_attente[1]
                if score_en_attente is not None else None
            )
        }

        matchs.append(match)

        equipes_trouvees = []
        score_en_attente = None
        heure_actuelle = None

    uniques = []
    vus = set()

    for match in matchs:
        cle = cle_match(
            match["domicile"],
            match["exterieur"]
        )

        if cle not in vus:
            vus.add(cle)
            uniques.append(match)

    return uniques


# --------------------------------------------------
# EXTRACTION DES HEURES RUGBYRAMA
# --------------------------------------------------

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


def completer_heures(calendrier, horaires_rr):
    index = {}

    for item in horaires_rr:
        cle = cle_match(
            item["domicile"],
            item["exterieur"]
        )

        index.setdefault(cle, []).append(item["heure"])

    complets = 0

    for matchs in calendrier["journees"].values():

        for match in matchs:

            if match_deja_joue(match):
                continue

            heures = index.get(
                cle_match(
                    match["domicile"],
                    match["exterieur"]
                ),
                []
            )

            heures = list(set(h for h in heures if h != "00:00"))

            if len(heures) == 1 and match.get("heure") != heures[0]:
                match["heure"] = heures[0]
                complets += 1

    return complets


# --------------------------------------------------
# CHARGEMENT DE L'ANCIEN CALENDRIER
# --------------------------------------------------

def charger_ancien_calendrier():
    if not os.path.exists(FICHIER_JSON):
        print("Aucun ancien calendrier trouvé.")
        return {"journees": {}}

    try:
        with open(FICHIER_JSON, "r", encoding="utf-8") as fichier:
            ancien = json.load(fichier)

        if not isinstance(ancien.get("journees"), dict):
            ancien["journees"] = {}

        print("✓ Ancien calendrier chargé.")
        return ancien

    except Exception as erreur:
        print(f"⚠ Impossible de lire l'ancien calendrier : {erreur}")
        raise


# --------------------------------------------------
# FUSION ET PROTECTION DES MATCHS
# --------------------------------------------------

def fusionner_journee(anciens, nouveaux, numero):
    resultat = []

    anciens_par_cle = {}

    for ancien in anciens:
        cle = cle_match(
            ancien["domicile"],
            ancien["exterieur"]
        )
        anciens_par_cle[cle] = ancien

    nouveaux_vus = set()

    for nouveau in nouveaux:

        cle = cle_match(
            nouveau["domicile"],
            nouveau["exterieur"]
        )

        nouveaux_vus.add(cle)
        ancien = anciens_par_cle.get(cle)

        # Nouveau match : on l'ajoute.
        if ancien is None:
            resultat.append(nouveau)
            print(
                f"  + Nouveau match : "
                f"{nouveau['domicile']} - {nouveau['exterieur']}"
            )
            continue

        # Match déjà joué : aucune modification.
        if match_deja_joue(ancien):
            resultat.append(ancien)
            print(
                f"  = Match joué protégé : "
                f"{ancien['domicile']} - {ancien['exterieur']}"
            )
            continue

        # Match non joué : actualisation.
        fusion = ancien.copy()

        # On conserve impérativement l'ancien identifiant.
        fusion["id"] = ancien.get(
            "id",
            nouveau["id"]
        )

        fusion["journee"] = ancien.get(
            "journee",
            nouveau["journee"]
        )

        # Les équipes restent celles du match existant.
        fusion["domicile"] = ancien["domicile"]
        fusion["exterieur"] = ancien["exterieur"]

        # Actualiser uniquement avec les données disponibles.
        if nouveau.get("date"):
            fusion["date"] = nouveau["date"]

        if nouveau.get("heure"):
            fusion["heure"] = nouveau["heure"]

        # Si un score vient d'être publié, on l'enregistre.
        if (
            nouveau.get("scoreDomicile") is not None
            and nouveau.get("scoreExterieur") is not None
        ):
            fusion["scoreDomicile"] = nouveau["scoreDomicile"]
            fusion["scoreExterieur"] = nouveau["scoreExterieur"]

        resultat.append(fusion)

        print(
            f"  ↻ Match actualisé : "
            f"{fusion['domicile']} - {fusion['exterieur']}"
        )

    # Si un ancien match n'a pas été retrouvé pendant le scraping,
    # on le conserve pour éviter toute perte de données.
    for ancien in anciens:

        cle = cle_match(
            ancien["domicile"],
            ancien["exterieur"]
        )

        if cle not in nouveaux_vus:
            resultat.append(ancien)

            print(
                f"  = Match conservé : "
                f"{ancien['domicile']} - {ancien['exterieur']}"
            )

    return resultat


def fusionner_calendrier(ancien, nouveau):
    calendrier_final = {
        "source": BASE_URL,
        "saison": "2026-2027",
        "journees": {}
    }

    anciennes_journees = ancien.get("journees", {})
    nouvelles_journees = nouveau.get("journees", {})

    for numero in range(1, 31):

        nom = f"J{numero}"

        anciens = anciennes_journees.get(nom, [])
        nouveaux = nouvelles_journees.get(nom, [])

        print(f"\n===== Fusion de {nom} =====")

        # Si la récupération a échoué ou n'a rien retourné,
        # on garde intégralement l'ancienne journée.
        if not nouveaux:
            calendrier_final["journees"][nom] = anciens
            print("  Journée non récupérée : ancienne version conservée.")
            continue

        calendrier_final["journees"][nom] = fusionner_journee(
            anciens,
            nouveaux,
            numero
        )

    return calendrier_final


# --------------------------------------------------
# PROGRAMME PRINCIPAL
# --------------------------------------------------

def main():

    ancien_calendrier = charger_ancien_calendrier()

    nouveau_calendrier = {
        "source": BASE_URL,
        "saison": "2026-2027",
        "journees": {}
    }

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1920, "height": 1080}
        )

        for numero in range(1, 31):

            nom = f"J{numero}"

            print(f"\n===== Récupération de {nom} =====")

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

                texte = page.locator("body").inner_text()

                with open(
                    f"debug_{nom}.txt",
                    "w",
                    encoding="utf-8"
                ) as fichier:
                    fichier.write(texte)

                matchs = extraire_matchs(texte, numero)

                nouveau_calendrier["journees"][nom] = matchs

                print(f"✓ {len(matchs)} match(s) récupéré(s)")

            except Exception as erreur:

                print(
                    f"⚠ Première tentative échouée pour {nom} : {erreur}"
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

                    texte = page.locator("body").inner_text()

                    with open(
                        f"debug_{nom}.txt",
                        "w",
                        encoding="utf-8"
                    ) as fichier:
                        fichier.write(texte)

                    matchs = extraire_matchs(texte, numero)

                    nouveau_calendrier["journees"][nom] = matchs

                    print(
                        f"✓ Deuxième tentative : {len(matchs)} match(s)"
                    )

                except Exception as seconde_erreur:

                    print(
                        f"⚠ Échec définitif {nom} : {seconde_erreur}"
                    )

                    nouveau_calendrier["journees"][nom] = []

        print("\n===== Récupération Rugbyrama =====")

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

            texte_rr = page.locator("body").inner_text()

            with open(
                "debug_rugbyrama.txt",
                "w",
                encoding="utf-8"
            ) as fichier:
                fichier.write(texte_rr)

            horaires_rr = extraire_matchs_rugbyrama(texte_rr)

            print(
                f"✓ {len(horaires_rr)} horaire(s) candidat(s) trouvé(s)"
            )

        except Exception as erreur:
            print(f"⚠ Rugbyrama ignoré : {erreur}")

        browser.close()

    # Fusion avec l'ancien calendrier.
    calendrier_final = fusionner_calendrier(
        ancien_calendrier,
        nouveau_calendrier
    )

    # Compléter les heures manquantes avec Rugbyrama.
    complets = completer_heures(
        calendrier_final,
        horaires_rr
    )

    print(
        f"\n✓ {complets} heure(s) complétée(s) depuis Rugbyrama"
    )

    # Sauvegarde du calendrier final.
    with open(
        FICHIER_JSON,
        "w",
        encoding="utf-8"
    ) as fichier:
        json.dump(
            calendrier_final,
            fichier,
            ensure_ascii=False,
            indent=4
        )

    print("\n===================================")
    print("✓ calendrier.json créé")
    print("✓ Matchs déjà joués protégés")
    print("✓ Identifiants existants conservés")
    print("✓ Journées non récupérées conservées")
    print("===================================")


if __name__ == "__main__":
    main()
    
