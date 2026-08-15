"""
Tests des utilitaires de résolution de chemins.

Ces fonctions déterminent où l'application lit ses ressources et où elle écrit
ses réglages, aussi bien en mode script qu'une fois empaquetée par PyInstaller.
"""
import os
import sys
import pathlib
import unittest
from unittest import mock

from tests.support import IsolatedTestCase
from utils import get_resource_path, get_writable_path


class ResourcePathTests(IsolatedTestCase):
    """Chemins de lecture seule (icônes, ressources statiques)."""

    def test_mode_script(self):
        """Hors empaquetage, la ressource est cherchée dans le répertoire courant."""
        resolved = get_resource_path("assets/icone.png")

        self.assertEqual(resolved, os.path.join(os.path.abspath("."), "assets/icone.png"))

    def test_mode_empaquete(self):
        """Une fois empaqueté, PyInstaller expose ses ressources via sys._MEIPASS."""
        with mock.patch.object(sys, "_MEIPASS", "/tmp/_MEI123", create=True):
            resolved = get_resource_path("assets/icone.png")

        self.assertEqual(resolved, os.path.join("/tmp/_MEI123", "assets/icone.png"))


class WritablePathTests(IsolatedTestCase):
    """Chemins d'écriture (réglages, journaux)."""

    def test_mode_script_cree_le_dossier_parent(self):
        """Le répertoire intermédiaire est créé au passage."""
        resolved = get_writable_path("logs/application.log")

        self.assertTrue((self.workdir / "logs").is_dir())
        self.assertEqual(resolved, str(self.workdir / "logs" / "application.log"))

    def test_mode_empaquete_ecrit_a_cote_de_l_executable(self):
        """
        Une fois empaqueté, les fichiers modifiables vont auprès de l'exécutable.

        Les écrire dans le dossier temporaire de PyInstaller les ferait
        disparaître à chaque fermeture de l'application.
        """
        faux_executable = self.workdir / "bin" / "compresseur.exe"
        faux_executable.parent.mkdir(parents=True, exist_ok=True)

        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "executable", str(faux_executable)):
            resolved = get_writable_path("settings/export_folder.json")

        self.assertEqual(
            resolved, str(self.workdir / "bin" / "settings" / "export_folder.json")
        )
        self.assertTrue((self.workdir / "bin" / "settings").is_dir())

    def test_appel_repete_sur_un_dossier_existant(self):
        """Un second appel ne relève aucune erreur sur un dossier déjà créé."""
        first = get_writable_path("settings/export_folder.json")
        second = get_writable_path("settings/export_folder.json")

        self.assertEqual(first, second)
        self.assertTrue(pathlib.Path(first).parent.is_dir())


if __name__ == '__main__':
    unittest.main()
