"""
Test du point d'entrée : câblage de la journalisation, de la fenêtre, du
Contrôleur et de la boucle graphique.
"""
import unittest
from unittest import mock

from tests.support import IsolatedTestCase
import main as main_module
from mvc.constants import WINDOW_GEOMETRY, WINDOW_TITLE


class MainTests(IsolatedTestCase):
    """Enchaînement du démarrage."""

    def test_demarrage(self):
        """La fenêtre, le Contrôleur et la boucle sont initialisés dans l'ordre."""
        fake_window = mock.Mock()

        with mock.patch.object(main_module, "configure_logging") as logging_setup, \
             mock.patch.object(main_module, "create_main_window", return_value=fake_window) as factory, \
             mock.patch.object(main_module, "ApplicationController") as controller:
            main_module.main()

        logging_setup.assert_called_once()
        factory.assert_called_once_with(
            title=WINDOW_TITLE, geometry=WINDOW_GEOMETRY, themename="darkly"
        )
        controller.assert_called_once_with(fake_window)
        fake_window.mainloop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
