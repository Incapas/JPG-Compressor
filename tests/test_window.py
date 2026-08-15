"""
Tests de la fabrique de fenêtre et du glisser-déposer.

Le glisser-déposer étant une dépendance facultative, ces tests vérifient
autant le chemin nominal que le repli lorsque `tkinterdnd2` est absent.
"""
import unittest
from unittest import mock

from tests.support import IsolatedTestCase, requires_gui, make_jpeg, make_png
from mvc import window as window_module
from mvc.window import _collect_image_paths, create_main_window, enable_file_drop


class CollectImagePathsTests(IsolatedTestCase):
    """Filtrage des chemins issus d'un dépôt."""

    def test_conserve_les_extensions_jpeg(self):
        """Seuls les fichiers .jpg et .jpeg sont retenus."""
        jpg = make_jpeg(self.source_dir, "a.jpg")
        jpeg = make_jpeg(self.source_dir, "b.jpeg")
        texte = self.source_dir / "notes.txt"
        texte.write_text("pas une image")

        collected = _collect_image_paths([str(jpg), str(jpeg), str(texte)])

        self.assertEqual(sorted(collected), sorted([str(jpg), str(jpeg)]))

    def test_extension_insensible_a_la_casse(self):
        """Une extension en majuscules est acceptée."""
        majuscule = make_jpeg(self.source_dir, "PHOTO.JPG")

        collected = _collect_image_paths([str(majuscule)])

        self.assertEqual(collected, [str(majuscule)])

    def test_dossier_depose_est_parcouru(self):
        """Déposer un dossier importe les images qu'il contient directement."""
        make_jpeg(self.source_dir, "a.jpg")
        make_jpeg(self.source_dir, "b.jpg")
        (self.source_dir / "notes.txt").write_text("ignoré")
        # Un sous-dossier n'est volontairement pas exploré
        make_jpeg(self.source_dir / "sous_dossier", "c.jpg")

        collected = _collect_image_paths([str(self.source_dir)])

        self.assertEqual([path.rsplit("/", 1)[-1] for path in collected], ["a.jpg", "b.jpg"])

    def test_chemin_inexistant_est_ignore(self):
        """Un chemin invalide ne provoque pas d'erreur."""
        collected = _collect_image_paths([str(self.workdir / "fantome.jpg")])

        self.assertEqual(collected, [])

    def test_le_filtre_ne_valide_pas_le_contenu(self):
        """
        Le filtre porte sur l'extension seule.

        La vérification du format réel appartient au Modèle : c'est lui qui
        écartera ce PNG déguisé et le signalera à l'utilisateur.
        """
        piege = make_png(self.source_dir, "piege.jpg")

        collected = _collect_image_paths([str(piege)])

        self.assertEqual(collected, [str(piege)])


@requires_gui
class CreateMainWindowTests(IsolatedTestCase):
    """Construction de la fenêtre principale."""

    def test_fenetre_configuree(self):
        """Titre, géométrie et interdiction de redimensionnement sont appliqués."""
        window = create_main_window("Titre de test", "640x480")
        self.addCleanup(window.destroy)

        # La géométrie n'est relevable qu'une fois la fenêtre réalisée par le
        # gestionnaire de fenêtres, et avant tout masquage : une fenêtre retirée
        # de l'écran rapporte 1x1, quelle que soit la taille demandée.
        window.update()
        geometry = window.geometry()
        window.withdraw()

        self.assertEqual(window.title(), "Titre de test")
        self.assertEqual(window.resizable(), (False, False))
        self.assertTrue(geometry.startswith("640x480"), geometry)

    def test_repli_sans_tkinterdnd2(self):
        """Sans la bibliothèque, la fenêtre est créée sans glisser-déposer."""
        with mock.patch.object(window_module, "DND_AVAILABLE", False):
            window = create_main_window("Sans DnD", "320x240")
        self.addCleanup(window.destroy)
        window.withdraw()

        self.assertFalse(window.dnd_enabled)
        self.assertFalse(enable_file_drop(window, lambda paths: None))

    @unittest.skipUnless(window_module.DND_AVAILABLE, "tkinterdnd2 n'est pas installé")
    def test_repli_si_l_initialisation_echoue(self):
        """Un binaire natif incompatible fait retomber sur une fenêtre standard."""
        with mock.patch.object(
            window_module, "_DnDWindow", side_effect=RuntimeError("tkdnd introuvable")
        ):
            window = create_main_window("Repli", "320x240")
        self.addCleanup(window.destroy)
        window.withdraw()

        self.assertFalse(window.dnd_enabled)


@requires_gui
@unittest.skipUnless(window_module.DND_AVAILABLE, "tkinterdnd2 n'est pas installé")
class DragAndDropTests(IsolatedTestCase):
    """Enregistrement de la cible de dépôt et traitement de l'événement."""

    def setUp(self) -> None:
        super().setUp()
        self.window = create_main_window("DnD", "320x240")
        self.window.withdraw()
        self.addCleanup(self.window.destroy)

    def _register(self, callback):
        """
        Enregistre la cible de dépôt et retourne le gestionnaire installé.

        `enable_file_drop` confie une fermeture locale à `dnd_bind` : on
        l'intercepte ici pour pouvoir la déclencher comme le ferait tkdnd.

        Args:
            callback: Le rappel applicatif recevant la liste des chemins.

        Returns:
            Un couple (résultat de l'enregistrement, gestionnaire d'événement).
        """
        captured = {}
        original_bind = self.window.dnd_bind

        def capture(sequence, func):
            captured["handler"] = func
            return original_bind(sequence, func)

        with mock.patch.object(self.window, "dnd_bind", capture):
            registered = enable_file_drop(self.window, callback)

        return registered, captured.get("handler")

    def test_enregistrement_de_la_cible(self):
        """La fenêtre accepte les dépôts lorsque la bibliothèque est disponible."""
        self.assertTrue(self.window.dnd_enabled)
        registered, handler = self._register(lambda paths: None)

        self.assertTrue(registered)
        self.assertIsNotNone(handler)

    def test_depot_transmet_les_images(self):
        """Un dépôt appelle le rappel avec les seuls fichiers JPEG."""
        recus = []
        _, handler = self._register(recus.append)
        jpg = make_jpeg(self.source_dir, "a.jpg")
        texte = self.source_dir / "notes.txt"
        texte.write_text("ignoré")

        event = mock.Mock()
        # Reproduit la chaîne Tcl produite par tkdnd
        event.data = f"{{{jpg}}} {{{texte}}}"
        handler(event)

        self.assertEqual(recus, [[str(jpg)]])

    def test_depot_de_chemins_contenant_des_espaces(self):
        """Les accolades Tcl entourant les chemins à espaces sont correctement décodées."""
        recus = []
        _, handler = self._register(recus.append)
        dossier = self.workdir / "mes photos de vacances"
        image = make_jpeg(dossier, "photo de plage.jpg")

        event = mock.Mock()
        event.data = f"{{{image}}}"
        handler(event)

        self.assertEqual(recus, [[str(image)]])

    def test_depot_illisible_est_ignore(self):
        """Une charge utile incompréhensible n'appelle pas le rappel."""
        recus = []
        _, handler = self._register(recus.append)

        event = mock.Mock()
        # Accolade jamais refermée : Tcl refuse de découper cette liste
        event.data = "{chemin sans fin"

        handler(event)

        self.assertEqual(recus, [])

    def test_depot_sans_image_appelle_le_rappel_avec_une_liste_vide(self):
        """Le Contrôleur reste responsable du message affiché à l'utilisateur."""
        recus = []
        _, handler = self._register(recus.append)
        texte = self.source_dir / "notes.txt"
        texte.write_text("ignoré")

        event = mock.Mock()
        event.data = f"{{{texte}}}"
        handler(event)

        self.assertEqual(recus, [[]])

    def test_echec_d_enregistrement(self):
        """Une cible impossible à enregistrer est signalée sans interrompre l'appli."""
        with mock.patch.object(
            self.window, "drop_target_register", side_effect=RuntimeError("refusé")
        ):
            self.assertFalse(enable_file_drop(self.window, lambda paths: None))


if __name__ == '__main__':
    unittest.main()
