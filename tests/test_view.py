"""
Tests de la Vue sur de véritables widgets Tkinter.

Les états vérifiés (jauge affichée, réglages verrouillés, libellé du bouton)
sont ceux que l'utilisateur voit réellement à l'écran.
"""
import unittest
from unittest import mock

from tests.support import GuiTestCase, is_packed, requires_gui
from mvc.constants import DEFAULT_OUTPUT_FORMAT, DEFAULT_QUALITY, DEFAULT_RESIZE
from mvc.view import ApplicationView


@requires_gui
class ViewConstructionTests(GuiTestCase):
    """Construction de l'interface et valeurs initiales."""

    def setUp(self) -> None:
        super().setUp()
        self.view = ApplicationView(self.window)

    def test_valeurs_par_defaut(self):
        """Les réglages initiaux correspondent aux constantes du projet."""
        self.assertEqual(self.view.quality_meter.amountusedvar.get(), DEFAULT_QUALITY)
        self.assertEqual(self.view.resize_meter.amountusedvar.get(), DEFAULT_RESIZE)
        self.assertEqual(self.view.output_format_var.get(), DEFAULT_OUTPUT_FORMAT)
        self.assertFalse(self.view.optimized_storage_var.get())
        self.assertFalse(self.view.zip_export_var.get())

    def test_widgets_exposes_au_controleur(self):
        """Le Contrôleur trouve toutes les références dont il a besoin."""
        self.assertEqual(
            set(self.view.widget_references),
            {"import_button", "export_final_button", "reset_button",
             "optimized_storage_checkbutton", "export_path_button"},
        )

    def test_etat_initial_du_statut(self):
        """Le label de statut est visible et la jauge masquée au démarrage."""
        self.window.update_idletasks()

        self.assertTrue(is_packed(self.view.status_label))
        self.assertFalse(is_packed(self.view.progress_gauge))

    def test_update_status_label(self):
        """Le texte et le style du statut sont modifiables."""
        self.view.update_status_label("Un message", "danger")

        self.assertEqual(self.view.status_label.cget("text"), "Un message")

    def test_update_state_buttons(self):
        """Les trois boutons d'action se pilotent indépendamment."""
        self.view.update_state_buttons(import_enabled=False, export_enabled=True, reset_enabled=False)

        self.assertEqual(str(self.view.import_button.cget("state")), "disabled")
        self.assertEqual(str(self.view.export_final_button.cget("state")), "normal")
        self.assertEqual(str(self.view.reset_button.cget("state")), "disabled")

    def test_set_meter_values(self):
        """Les deux jauges de réglage acceptent de nouvelles valeurs."""
        self.view.set_meter_values(quality=42, resize=66)

        self.assertEqual(self.view.quality_meter.amountusedvar.get(), 42)
        self.assertEqual(self.view.resize_meter.amountusedvar.get(), 66)


@requires_gui
class ProcessingStateTests(GuiTestCase):
    """Bascule de l'interface en mode traitement et retour au repos."""

    def setUp(self) -> None:
        super().setUp()
        self.view = ApplicationView(self.window)

    def test_begin_processing(self):
        """La jauge remplace le statut et les réglages sont verrouillés."""
        self.view.begin_processing(total_images=12)
        self.window.update_idletasks()

        self.assertTrue(is_packed(self.view.progress_gauge))
        self.assertFalse(is_packed(self.view.status_label))
        self.assertEqual(self.view.progress_value_var.get(), 0)
        self.assertEqual(self.view.progress_text_var.get(), "0 % — 0 / 12")
        self.assertEqual(self.view.export_final_button.cget("text"), "Annuler")
        self.assertEqual(str(self.view.import_button.cget("state")), "disabled")
        self.assertEqual(str(self.view.reset_button.cget("state")), "disabled")
        self.assertEqual(str(self.view.delete_checkbutton.cget("state")), "disabled")

    def test_update_progress(self):
        """La jauge affiche le pourcentage, le compteur et le fichier courant."""
        self.view.begin_processing(total_images=8)

        self.view.update_progress(done=2, total=8, filename="img_02.jpg")

        self.assertEqual(self.view.progress_value_var.get(), 25)
        self.assertEqual(self.view.progress_text_var.get(), "25 % — 2 / 8 — img_02.jpg")

    def test_update_progress_sans_image(self):
        """Un total nul n'entraîne pas de division par zéro."""
        self.view.update_progress(done=0, total=0, filename="")

        self.assertEqual(self.view.progress_value_var.get(), 0)

    def test_end_processing(self):
        """Le statut reprend sa place et les réglages sont déverrouillés."""
        self.view.begin_processing(total_images=3)

        self.view.end_processing()
        self.window.update_idletasks()

        self.assertFalse(is_packed(self.view.progress_gauge))
        self.assertTrue(is_packed(self.view.status_label))
        self.assertEqual(self.view.export_final_button.cget("text"), "Exporter des images")
        self.assertEqual(str(self.view.delete_checkbutton.cget("state")), "normal")

    def test_set_cancelling(self):
        """La demande d'annulation se voit sur le bouton et dans la jauge."""
        self.view.begin_processing(total_images=3)

        self.view.set_cancelling()

        self.assertEqual(self.view.export_final_button.cget("text"), "Annulation...")
        self.assertEqual(str(self.view.export_final_button.cget("state")), "disabled")
        self.assertEqual(self.view.progress_text_var.get(), "Annulation en cours...")

    def test_widget_detruit_ne_bloque_pas_le_verrouillage(self):
        """Un widget disparu est ignoré au lieu d'interrompre la bascule."""
        self.view._lockable_widgets[0].destroy()

        self.view.begin_processing(total_images=1)
        self.view.end_processing()

        self.assertEqual(self.view.export_final_button.cget("text"), "Exporter des images")


@requires_gui
class DialogTests(GuiTestCase):
    """Sélecteurs de fichiers et rapport d'échecs."""

    def setUp(self) -> None:
        super().setUp()
        self.view = ApplicationView(self.window)

    def test_selection_du_dossier_d_export(self):
        """La Vue relaie le chemin choisi par l'utilisateur."""
        with mock.patch("mvc.view.filedialog.askdirectory", return_value="/tmp/destination"):
            self.assertEqual(self.view.open_directory_dialog(), "/tmp/destination")

    def test_selection_des_fichiers(self):
        """Le filtre de la boîte de dialogue se limite aux extensions JPEG."""
        with mock.patch(
            "mvc.view.filedialog.askopenfilenames", return_value=("/tmp/a.jpg",)
        ) as dialog:
            self.assertEqual(self.view.open_files_dialog(), ("/tmp/a.jpg",))

        self.assertEqual(
            dialog.call_args.kwargs["filetypes"], [("Image Files", "*.jpg *.jpeg")]
        )

    def test_rapport_d_echecs(self):
        """Les fichiers non exportés sont listés avec leur cause."""
        with mock.patch("mvc.view.Messagebox.show_warning") as dialog:
            self.view.show_failure_report([("a.jpg", "disque plein"), ("b.jpg", "refusé")])

        message = dialog.call_args.kwargs["message"]
        self.assertIn("2 fichier(s)", message)
        self.assertIn("a.jpg : disque plein", message)
        self.assertIn("application.log", message)

    def test_rapport_d_echecs_tronque(self):
        """Au-delà de dix entrées, le reste est résumé."""
        failures = [(f"f{i}.jpg", "erreur") for i in range(14)]

        with mock.patch("mvc.view.Messagebox.show_warning") as dialog:
            self.view.show_failure_report(failures)

        message = dialog.call_args.kwargs["message"]
        self.assertIn("et 4 autre(s)", message)

    def test_rapport_vide_n_affiche_rien(self):
        """Aucune boîte n'est ouverte sans échec à signaler."""
        with mock.patch("mvc.view.Messagebox.show_warning") as dialog:
            self.view.show_failure_report([])

        dialog.assert_not_called()


if __name__ == '__main__':
    unittest.main()
