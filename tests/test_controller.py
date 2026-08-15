"""
Tests du Contrôleur : enchaînement importation → exportation, traitement en
arrière-plan, progression, annulation et garde-fous.

Le thread de compression est réellement lancé et la boucle d'événements
réellement animée : ces tests exercent le même chemin que l'application.
"""
import pathlib
import time
import unittest
from unittest import mock

from tests.support import GuiTestCase, is_packed, requires_gui
from mvc.constants import (
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_QUALITY,
    DEFAULT_RESIZE,
    OPTIMIZED_OUTPUT_FORMAT,
    OPTIMIZED_QUALITY,
    OPTIMIZED_RESIZE,
)
from mvc.controller import ApplicationController


@requires_gui
class ControllerTestCase(GuiTestCase):
    """Cas de base instanciant un Contrôleur relié aux dossiers du test."""

    def setUp(self) -> None:
        super().setUp()
        self.controller = ApplicationController(self.window)
        self.view = self.controller.view
        self.model = self.controller.model
        self.model.write_config(str(self.export_dir))
        self.view.export_path_var.set(str(self.export_dir))
        # Relâche les descripteurs de fichiers encore ouverts en fin de test
        self.addCleanup(self.model.reset_data)

    def import_images(self, count: int = 3) -> list:
        """Crée puis importe un lot d'images dans le Contrôleur."""
        paths = [str(self.make_jpeg(f"img_{i:02d}.jpg")) for i in range(count)]
        self.controller._load_into_model(paths)
        return paths

    def run_export(self, timeout: float = 30.0) -> bool:
        """
        Lance l'exportation et anime la boucle jusqu'à son terme.

        Args:
            timeout: Le délai maximal d'attente, en secondes.

        Returns:
            True si le traitement s'est achevé dans le délai imparti.
        """
        self.controller.handle_export_button()
        return self.pump_until(lambda: not self.controller._is_processing()) and \
            self.pump_until(lambda: is_packed(self.view.status_label), timeout)


class ImportTests(ControllerTestCase):
    """Importation par la boîte de dialogue et par glisser-déposer."""

    def test_import_reussi(self):
        """Les images valides activent l'export et la réinitialisation."""
        paths = [str(self.make_jpeg("a.jpg")), str(self.make_jpeg("b.jpg"))]

        with mock.patch.object(self.view, "open_files_dialog", return_value=tuple(paths)):
            self.controller.handle_import_images()

        self.assertIn("2 image(s) sélectionnée(s)", self.view.status_label.cget("text"))
        self.assertEqual(str(self.view.export_final_button.cget("state")), "normal")
        self.assertEqual(str(self.view.reset_button.cget("state")), "normal")

    def test_import_annule(self):
        """Refermer la boîte de dialogue laisse l'application en l'état."""
        with mock.patch.object(self.view, "open_files_dialog", return_value=()):
            self.controller.handle_import_images()

        self.assertIn("Importation annulée", self.view.status_label.cget("text"))
        self.assertEqual(len(self.model.data), 0)

    def test_import_partiellement_rejete(self):
        """Les fichiers écartés sont signalés sans bloquer les autres."""
        from tests.support import make_png

        valide = str(self.make_jpeg("a.jpg"))
        piege = str(make_png(self.source_dir, "piege.jpg"))

        self.controller._load_into_model([valide, piege])

        message = self.view.status_label.cget("text")
        self.assertIn("1 image(s) sélectionnée(s)", message)
        self.assertIn("1 fichier(s) ignoré(s)", message)

    def test_import_entierement_rejete(self):
        """Un lot sans aucun JPEG valide désactive l'export."""
        from tests.support import make_png

        piege = str(make_png(self.source_dir, "piege.jpg"))

        self.controller._load_into_model([piege])

        self.assertIn("Échec de l'importation", self.view.status_label.cget("text"))
        self.assertEqual(str(self.view.export_final_button.cget("state")), "disabled")

    def test_depot_de_fichiers(self):
        """Un dépôt valide charge les images comme une importation classique."""
        paths = [str(self.make_jpeg("a.jpg"))]

        self.controller.handle_dropped_files(paths)

        self.assertIn("1 image(s) sélectionnée(s)", self.view.status_label.cget("text"))

    def test_depot_sans_image(self):
        """Un dépôt sans JPEG affiche un avertissement explicite."""
        self.controller.handle_dropped_files([])

        self.assertIn("Aucun fichier JPG/JPEG", self.view.status_label.cget("text"))

    def test_depot_ignore_pendant_un_traitement(self):
        """Déposer des fichiers en pleine compression ne perturbe pas le thread."""
        self.import_images(2)

        with mock.patch.object(self.controller, "_is_processing", return_value=True):
            self.controller.handle_dropped_files([str(self.make_jpeg("tardif.jpg"))])

        self.assertNotIn("tardif", self.view.status_label.cget("text"))

    def test_message_d_accueil_mentionne_le_depot(self):
        """Quand le glisser-déposer est actif, l'accueil invite à s'en servir."""
        with mock.patch("mvc.controller.enable_file_drop", return_value=True):
            controller = ApplicationController(self.window)

        self.assertIn("glissez vos fichiers", controller.view.status_label.cget("text"))


class ExportPathTests(ControllerTestCase):
    """Choix et persistance du dossier de destination."""

    def test_selection_enregistree(self):
        """Le dossier choisi est écrit en configuration et affiché."""
        destination = str(self.workdir / "ailleurs")
        (self.workdir / "ailleurs").mkdir()

        with mock.patch.object(self.view, "open_directory_dialog", return_value=destination):
            self.controller.handle_select_export_path()

        self.assertEqual(self.model.export_path, destination)
        self.assertEqual(self.view.export_path_var.get(), destination)
        self.assertIn("sauvegardé", self.view.status_label.cget("text"))

    def test_selection_annulee(self):
        """Refermer le sélecteur ne modifie pas le chemin courant."""
        with mock.patch.object(self.view, "open_directory_dialog", return_value=""):
            self.controller.handle_select_export_path()

        self.assertEqual(self.model.export_path, str(self.export_dir))


class OptimizedStorageTests(ControllerTestCase):
    """Bascule du mode « Stockage optimisé »."""

    def test_activation(self):
        """Le mode applique un profil de compression agressif."""
        self.view.optimized_storage_var.set(True)

        self.controller.handle_optimized_storage_toggle()

        self.assertEqual(self.view.quality_meter.amountusedvar.get(), OPTIMIZED_QUALITY)
        self.assertEqual(self.view.resize_meter.amountusedvar.get(), OPTIMIZED_RESIZE)
        self.assertEqual(self.view.output_format_var.get(), OPTIMIZED_OUTPUT_FORMAT)
        self.assertTrue(self.view.strip_metadata_var.get())
        self.assertTrue(self.view.optimized_encoding_var.get())
        self.assertTrue(self.view.progressive_loading_var.get())

    def test_desactivation(self):
        """Le retour au mode normal rétablit les valeurs par défaut."""
        self.view.optimized_storage_var.set(True)
        self.controller.handle_optimized_storage_toggle()

        self.view.optimized_storage_var.set(False)
        self.controller.handle_optimized_storage_toggle()

        self.assertEqual(self.view.quality_meter.amountusedvar.get(), DEFAULT_QUALITY)
        self.assertEqual(self.view.resize_meter.amountusedvar.get(), DEFAULT_RESIZE)
        self.assertEqual(self.view.output_format_var.get(), DEFAULT_OUTPUT_FORMAT)
        self.assertIn("Aucune image", self.view.status_label.cget("text"))

    def test_desactivation_avec_images_chargees(self):
        """Le message d'état des images importées n'est pas écrasé."""
        self.import_images(1)
        self.view.optimized_storage_var.set(False)

        self.controller.handle_optimized_storage_toggle()

        self.assertIn("image(s) sélectionnée(s)", self.view.status_label.cget("text"))


class ExportTests(ControllerTestCase):
    """Exportation en arrière-plan et bilan affiché."""

    def test_export_complet(self):
        """Le traitement aboutit et l'interface revient au repos."""
        self.import_images(4)

        self.assertTrue(self.run_export())

        self.assertIn("Exportation terminée", self.view.status_label.cget("text"))
        self.assertEqual(len(list(self.export_dir.glob("*.jpg"))), 4)
        self.assertEqual(self.view.export_final_button.cget("text"), "Exporter des images")
        self.assertEqual(str(self.view.import_button.cget("state")), "normal")
        self.assertFalse(is_packed(self.view.progress_gauge))

    def test_progression_affichee(self):
        """La jauge est alimentée pendant le traitement."""
        self.import_images(6)
        releves = []
        original = self.view.update_progress

        def espion(done, total, filename):
            original(done, total, filename)
            releves.append((done, total, self.view.progress_value_var.get()))

        with mock.patch.object(self.view, "update_progress", espion):
            self.assertTrue(self.run_export())

        self.assertGreater(len(releves), 0)
        self.assertEqual(releves[-1][:2], (6, 6))
        # Les valeurs remontées à la jauge sont croissantes
        self.assertEqual([v for _, _, v in releves], sorted(v for _, _, v in releves))

    def test_export_sans_image(self):
        """Exporter sans sélection affiche une erreur sans lancer de thread."""
        self.controller.handle_export_button()

        self.assertIn("Aucune image à exporter", self.view.status_label.cget("text"))
        self.assertFalse(self.controller._is_processing())

    def test_qualite_invalide_refusee(self):
        """Une qualité hors bornes est rejetée avant tout traitement."""
        self.import_images(1)
        self.view.quality_meter.amountusedvar.set(0)

        self.controller.handle_export_button()

        self.assertIn("entre 1 et 100", self.view.status_label.cget("text"))
        self.assertFalse(self.controller._is_processing())

    def test_lecture_des_parametres_en_echec(self):
        """Une lecture de widget impossible est signalée proprement."""
        self.import_images(1)

        with mock.patch.object(
            self.view.quality_meter.amountusedvar, "get", side_effect=RuntimeError("widget perdu")
        ):
            self.controller.handle_export_button()

        self.assertIn("Échec de la lecture des paramètres", self.view.status_label.cget("text"))

    def test_bilan_avec_echecs(self):
        """Les échecs sont comptés dans le bilan et détaillés dans une boîte."""
        self.import_images(3)
        from PIL import Image

        original_save = Image.Image.save

        def save_qui_echoue(image_self, fp, *args, **kwargs):
            if "img_01" in str(fp):
                raise OSError("échec simulé")
            return original_save(image_self, fp, *args, **kwargs)

        with mock.patch.object(Image.Image, "save", save_qui_echoue), \
             mock.patch.object(self.view, "show_failure_report") as rapport:
            self.assertTrue(self.run_export())

        self.assertIn("1 échec(s)", self.view.status_label.cget("text"))
        rapport.assert_called_once()

    def test_echec_total(self):
        """Un échec sur toutes les images laisse l'export réactivable."""
        self.import_images(2)
        from PIL import Image

        with mock.patch.object(Image.Image, "save", side_effect=OSError("échec")), \
             mock.patch.object(self.view, "show_failure_report"):
            self.assertTrue(self.run_export())

        self.assertIn("Échec de l'exportation", self.view.status_label.cget("text"))
        self.assertEqual(str(self.view.export_final_button.cget("state")), "normal")

    def test_message_de_type_inconnu_est_ignore(self):
        """
        Un message imprévu dans la file n'interrompt pas la relecture.

        La boucle de dépouillement doit rester tolérante : un type inconnu est
        simplement sauté, et les messages suivants restent traités.
        """
        self.import_images(1)
        stats = {
            "total_old_mo": 1.0, "total_new_mo": 0.5, "difference_mo": 0.5,
            "gain_percent": 50.0, "export_dir": str(self.export_dir),
            "total_images": 1, "failures": [], "cancelled": False, "zip_path": None,
        }
        self.view.begin_processing(1)
        self.controller._progress_queue.put(("type_inconnu", "charge utile"))
        self.controller._progress_queue.put(("done", (1, stats)))

        self.controller._poll_progress()

        self.assertIn("Exportation terminée", self.view.status_label.cget("text"))

    def test_erreur_inattendue_restaure_l_interface(self):
        """Une exception imprévue du thread ne laisse pas l'interface bloquée."""
        self.import_images(2)

        with mock.patch.object(
            self.model, "process_and_export", side_effect=RuntimeError("panne")
        ):
            self.assertTrue(self.run_export())

        self.assertIn("Erreur inattendue", self.view.status_label.cget("text"))
        self.assertFalse(is_packed(self.view.progress_gauge))
        self.assertEqual(str(self.view.import_button.cget("state")), "normal")


class CancelTests(ControllerTestCase):
    """Interruption d'un traitement en cours."""

    def test_annulation_pendant_le_traitement(self):
        """Le second clic interrompt la compression et restaure l'interface."""
        self.import_images(30)

        # Les images de test se compressent en quelques millisecondes : sans ce
        # ralentissement, le lot serait terminé avant le premier rafraîchissement
        # de la jauge et l'annulation n'aurait rien à interrompre.
        from PIL import Image

        original_save = Image.Image.save

        def save_ralenti(image_self, fp, *args, **kwargs):
            time.sleep(0.02)
            return original_save(image_self, fp, *args, **kwargs)

        with mock.patch.object(Image.Image, "save", save_ralenti):
            self.controller.handle_export_button()

            # Annule dès que la jauge a bougé, donc en plein traitement
            self.assertTrue(
                self.pump_until(lambda: self.view.progress_value_var.get() > 0, timeout=20)
            )
            self.controller.handle_export_button()

            self.assertTrue(
                self.pump_until(lambda: not self.controller._is_processing(), timeout=20)
            )
            self.assertTrue(
                self.pump_until(lambda: is_packed(self.view.status_label), timeout=20)
            )

        self.assertIn("Exportation annulée", self.view.status_label.cget("text"))
        self.assertLess(len(list(self.export_dir.glob("*.jpg"))), 30)
        # L'export reste proposé pour reprendre le lot
        self.assertEqual(str(self.view.export_final_button.cget("state")), "normal")

    def test_annulation_avant_le_premier_enregistrement(self):
        """Une annulation immédiate est distinguée d'un véritable échec."""
        self.import_images(2)
        stats = {
            "total_old_mo": 0.0, "total_new_mo": 0.0, "difference_mo": 0.0,
            "gain_percent": 0.0, "export_dir": str(self.export_dir),
            "total_images": 2, "failures": [], "cancelled": True, "zip_path": None,
        }

        with mock.patch.object(self.model, "process_and_export", return_value=(0, stats)):
            self.assertTrue(self.run_export())

        self.assertIn(
            "Traitement annulé avant le premier enregistrement",
            self.view.status_label.cget("text"),
        )

    def test_annulation_sans_traitement(self):
        """Demander l'annulation hors traitement est sans effet."""
        self.controller._cancel_event = None

        self.controller.handle_cancel_export()

        self.assertFalse(self.controller._is_processing())


class DeleteOriginalsTests(ControllerTestCase):
    """Suppression des originaux depuis l'interface."""

    def test_suppression_immediate(self):
        """
        L'option supprime les originaux sans demander de confirmation.

        L'export ne s'interrompt à aucun moment pour interroger l'utilisateur :
        le lot est traité d'une traite.
        """
        paths = self.import_images(2)
        self.view.delete_originals_var.set(True)

        self.assertTrue(self.run_export())

        for path in paths:
            self.assertFalse(pathlib.Path(path).exists())
        self.assertEqual(len(list(self.export_dir.glob("*.jpg"))), 2)
        self.assertIn("Exportation terminée", self.view.status_label.cget("text"))

    def test_originaux_conserves_sans_l_option(self):
        """Sans l'option, les sources restent en place."""
        paths = self.import_images(2)

        self.assertTrue(self.run_export())

        for path in paths:
            self.assertTrue(pathlib.Path(path).exists())

    def test_suppression_dans_le_dossier_source(self):
        """
        Exporter dans le dossier source ne détruit pas les images.

        La version compressée reçoit un nom libre avant que l'original ne soit
        effacé : c'est ce qui reste comme protection maintenant que la
        confirmation a été retirée.
        """
        paths = self.import_images(1)
        self.model.write_config(str(self.source_dir))
        self.view.delete_originals_var.set(True)

        self.assertTrue(self.run_export())

        self.assertFalse(pathlib.Path(paths[0]).exists())
        self.assertTrue((self.source_dir / "img_00_1.jpg").exists())


class ResetTests(ControllerTestCase):
    """Remise à zéro de l'application."""

    def test_reset_complet(self):
        """Données et réglages retrouvent leur état initial."""
        self.import_images(2)
        self.view.set_meter_values(quality=10, resize=20)
        self.view.zip_export_var.set(True)
        self.view.add_suffixe_var.set(True)

        self.controller.handle_reset()

        self.assertEqual(len(self.model.data), 0)
        self.assertEqual(self.view.quality_meter.amountusedvar.get(), DEFAULT_QUALITY)
        self.assertEqual(self.view.resize_meter.amountusedvar.get(), DEFAULT_RESIZE)
        self.assertFalse(self.view.zip_export_var.get())
        self.assertFalse(self.view.add_suffixe_var.get())
        self.assertEqual(self.view.output_format_var.get(), DEFAULT_OUTPUT_FORMAT)
        self.assertIn("Aucune image", self.view.status_label.cget("text"))
        self.assertEqual(str(self.view.export_final_button.cget("state")), "disabled")

    def test_reset_ignore_pendant_un_traitement(self):
        """Réinitialiser en pleine compression corromprait les données lues."""
        self.import_images(2)

        with mock.patch.object(self.controller, "_is_processing", return_value=True):
            self.controller.handle_reset()

        self.assertEqual(len(self.model.data), 2)


if __name__ == '__main__':
    unittest.main()
