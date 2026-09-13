from playwright.sync_api import sync_playwright
import json


URL = "https://prod2.lnr.fr/calendrier-resultats"


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

        texte = page.locator("body").inner_text()

        # Sauvegarde du debug
        with open(
            "debug_calendrier.txt",
            "w",
            encoding="utf-8"
        ) as fichier:

            fichier.write(texte)

        # Pour l'instant, création du fichier JSON
        donnees = {
            "source": URL,
            "calendrier": []
        }

        with open(
            "calendrier.json",
            "w",
            encoding="utf-8"
        ) as fichier:

            json.dump(
                donnees,
                fichier,
                ensure_ascii=False,
                indent=4
            )

        print("debug_calendrier.txt créé.")
        print("calendrier.json créé.")

        browser.close()


if __name__ == "__main__":
    main()
