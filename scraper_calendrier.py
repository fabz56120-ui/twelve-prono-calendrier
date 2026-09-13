def cliquer_journee(page, journee):

    print(f"Sélection de {journee}...")

    numero = journee.replace("J", "")

    # -------------------------------------------------
    # 1 - Cherche d'abord un vrai élément <select>
    # -------------------------------------------------

    selects = page.locator("select")

    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            options = select.locator("option").all_text_contents()

            options = [
                option.strip()
                for option in options
            ]

            if journee in options:

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

        except Exception:
            pass


    # -------------------------------------------------
    # 2 - Cas d'un menu personnalisé
    # -------------------------------------------------

    try:

        # Cherche tous les éléments contenant "Journée"
        labels = page.get_by_text(
            "Journée",
            exact=True
        )

        for i in range(labels.count()):

            label = labels.nth(i)

            try:

                if label.is_visible():

                    # On clique sur le parent ou le conteneur
                    label.click()

                    page.wait_for_timeout(500)

                    # Maintenant seulement on cherche
                    # la journée dans le menu ouvert
                    options = page.get_by_text(
                        journee,
                        exact=True
                    )

                    for j in range(options.count()):

                        option = options.nth(j)

                        if option.is_visible():

                            option.click()

                            page.wait_for_timeout(2000)

                            texte = page.locator(
                                "body"
                            ).inner_text()

                            if (
                                f"JOURNÉE {numero}"
                                in texte
                            ):

                                print(
                                    f"✓ {journee} sélectionnée"
                                )

                                return True

            except Exception:
                pass

    except Exception:
        pass


    # -------------------------------------------------
    # 3 - Dernière tentative :
    # ouvre tous les boutons potentiels puis cherche J
    # -------------------------------------------------

    try:

        boutons = page.locator(
            "button"
        )

        for i in range(boutons.count()):

            bouton = boutons.nth(i)

            try:

                if not bouton.is_visible():
                    continue

                texte_bouton = bouton.inner_text().strip()

                # Bouton susceptible d'être le sélecteur
                if (
                    "Journée" in texte_bouton
                    or texte_bouton.startswith("J")
                ):

                    bouton.click()

                    page.wait_for_timeout(500)

                    options = page.get_by_text(
                        journee,
                        exact=True
                    )

                    for j in range(options.count()):

                        option = options.nth(j)

                        if option.is_visible():

                            option.click()

                            page.wait_for_timeout(2000)

                            texte = page.locator(
                                "body"
                            ).inner_text()

                            if (
                                f"JOURNÉE {numero}"
                                in texte
                            ):

                                print(
                                    f"✓ {journee} sélectionnée"
                                )

                                return True

            except Exception:
                pass

    except Exception:
        pass


    print(
        f"⚠ Impossible de sélectionner {journee}"
    )

    return False
