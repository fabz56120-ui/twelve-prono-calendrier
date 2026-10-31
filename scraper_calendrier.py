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
            cle_match(match["domicile"], match["exterieur"]),
            match["heure"]
        )

        if cle not in vus:
            vus.add(cle)
            uniques.append(match)

    return uniques


def completer_heures(calendrier, horaires_rr):
    index = {}
    for item in horaires_rr:
        index.setdefault(cle_match(item["domicile"], item["exterieur"]), []).append(item["heure"])
    complets = 0
    for matchs in calendrier["journees"].values():
        for match in matchs:
            if match.get("heure"):
                continue
            heures = index.get(cle_match(match["domicile"], match["exterieur"]), [])
            heures = [h for h in heures if h != "00:00"]
            if len(set(heures)) == 1:
                match["heure"] = heures[0]
                complets += 1
    return complets


def main():
    calendrier = {"source": BASE_URL, "saison": "2026-2027", "journees": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        for numero in range(1, 31):
            print(f"\n===== Récupération de J{numero} =====")
            try:
                page.goto(f"{BASE_URL}/j{numero}", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(8000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                texte = page.locator("body").inner_text()
                with open(f"debug_J{numero}.txt", "w", encoding="utf-8") as f:
                    f.write(texte)
                matchs = extraire_matchs(texte, numero)
                calendrier["journees"][f"J{numero}"] = matchs
                print(f"✓ {len(matchs)} match(s)")
            except Exception as erreur:
                print(f"⚠ Première tentative échouée pour J{numero}: {erreur}")

                # Deuxième tentative : ne pas perdre la journée à cause
                # d'un timeout réseau du site LNR.
                try:
                    page.goto(
                        f"{BASE_URL}/j{numero}",
                        wait_until="commit",
                        timeout=60000
                    )
                    page.wait_for_timeout(10000)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)

                    texte = page.locator("body").inner_text()

                    with open(
                        f"debug_J{numero}.txt",
                        "w",
                        encoding="utf-8"
                    ) as f:
                        f.write(texte)

                    matchs = extraire_matchs(texte, numero)
                    calendrier["journees"][f"J{numero}"] = matchs

                    print(
                        f"✓ Deuxième tentative : {len(matchs)} match(s)"
                    )

                except Exception as seconde_erreur:
                    print(
                        f"⚠ Échec définitif J{numero}: {seconde_erreur}"
                    )
                    calendrier["journees"][f"J{numero}"] = []

        print("\n===== Complément des heures avec Rugbyrama =====")
        horaires_rr = []
        try:
            page.goto(RUGBYRAMA_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(7000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            texte_rr = page.locator("body").inner_text()
            with open("debug_rugbyrama.txt", "w", encoding="utf-8") as f:
                f.write(texte_rr)
            horaires_rr = extraire_matchs_rugbyrama(texte_rr)
            print(f"✓ {len(horaires_rr)} horaire(s) candidat(s) trouvé(s)")
        except Exception as erreur:
            print(f"⚠ Rugbyrama ignoré: {erreur}")

        browser.close()

    complets = completer_heures(calendrier, horaires_rr)
    print(f"✓ {complets} heure(s) complétée(s) depuis Rugbyrama")
    with open("calendrier.json", "w", encoding="utf-8") as fichier:
        json.dump(calendrier, fichier, ensure_ascii=False, indent=4)
    print("✓ calendrier.json créé")


if __name__ == "__main__":
    main()
