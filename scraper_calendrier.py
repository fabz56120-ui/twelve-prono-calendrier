from playwright.sync_api import sync_playwright


URL = "https://prod2.lnr.fr/calendrier-et-resultats"


def main():

    print("Ouverture du calendrier officiel...")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=60000
        )

        print("Page HTML chargée.")

        # Sauvegarde le HTML complet
        html = page.content()

        with open(
            "debug_calendrier.html",
            "w",
            encoding="utf-8"
        ) as fichier:

            fichier.write(html)

        print(
            "Fichier debug_calendrier.html créé."
        )


        # Garde également le texte pour comparaison
        texte = page.locator("body").inner_text()

        with open(
            "debug_calendrier.txt",
            "w",
            encoding="utf-8"
        ) as fichier:

            fichier.write(texte)

        print(
            "Fichier debug_calendrier.txt créé."
        )

        browser.close()


if __name__ == "__main__":
    main()
