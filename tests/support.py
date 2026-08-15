"""
Outils communs à la suite de tests : isolation du répertoire de travail,
fabrication d'images réelles et accès à un environnement graphique partagé.
"""
import os
import sys
import time
import shutil
import pathlib
import tempfile
import unittest
from typing import Callable, List, Optional

from PIL import Image

# Rend les modules du projet (utils, mvc) importables quel que soit le
# répertoire depuis lequel la suite est lancée.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fabrication d'images
# ---------------------------------------------------------------------------

def make_jpeg(
    directory: pathlib.Path,
    name: str = "photo.jpg",
    size: tuple = (200, 150),
) -> pathlib.Path:
    """
    Écrit un vrai fichier JPEG sur le disque.

    Le contenu est un dégradé plutôt qu'un aplat uni : une image unie se
    compresserait en quelques centaines d'octets et rendrait les mesures de
    gain de taille peu représentatives.

    Args:
        directory: Le répertoire d'accueil, créé si nécessaire.
        name: Le nom du fichier à écrire.
        size: Les dimensions (largeur, hauteur) de l'image.

    Returns:
        Le chemin du fichier créé.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name

    image = Image.new("RGB", size)
    pixels = image.load()
    for x in range(size[0]):
        for y in range(size[1]):
            pixels[x, y] = ((x * 3) % 256, (y * 5) % 256, ((x + y) * 7) % 256)
    image.save(path, format="JPEG", quality=95)

    return path


def make_png(directory: pathlib.Path, name: str = "piege.jpg") -> pathlib.Path:
    """
    Écrit un PNG sous une extension JPEG.

    Sert à vérifier que la validation du Modèle repose sur le contenu réel du
    fichier et non sur son extension.

    Args:
        directory: Le répertoire d'accueil.
        name: Le nom du fichier, volontairement trompeur.

    Returns:
        Le chemin du fichier créé.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    Image.new("RGB", (40, 40), (10, 20, 30)).save(path, format="PNG")
    return path


def default_options(**overrides) -> dict:
    """
    Construit un jeu d'options d'exportation neutre.

    Args:
        **overrides: Les options à surcharger pour le test courant.

    Returns:
        Le dictionnaire d'options attendu par `process_and_export`.
    """
    options = {
        'quality': 80,
        'resize_factor': 1.0,
        'output_format': 'JPG',
        'add_suffixe': False,
        'use_zip': False,
        'delete_originals': False,
        'optimized_encoding': False,
        'progressive_loading': False,
        'strip_metadata': False,
    }
    options.update(overrides)
    return options


# ---------------------------------------------------------------------------
# Cas de test de base
# ---------------------------------------------------------------------------

class IsolatedTestCase(unittest.TestCase):
    """
    Cas de test exécuté dans un répertoire temporaire.

    `get_writable_path` résout ses chemins depuis le répertoire courant : sans
    cette isolation, les tests écriraient dans les dossiers `settings/` et
    `logs/` du dépôt.
    """

    def setUp(self) -> None:
        self._previous_cwd = os.getcwd()
        self.workdir = pathlib.Path(tempfile.mkdtemp(prefix="jpgtest-")).resolve()
        os.chdir(self.workdir)

        # Répertoires de travail standards : sources d'un côté, export de l'autre
        self.source_dir = self.workdir / "sources"
        self.export_dir = self.workdir / "export"
        self.source_dir.mkdir()
        self.export_dir.mkdir()

    def tearDown(self) -> None:
        os.chdir(self._previous_cwd)
        shutil.rmtree(self.workdir, ignore_errors=True)

    def make_jpeg(self, name: str = "photo.jpg", size: tuple = (200, 150),
                  directory: Optional[pathlib.Path] = None) -> pathlib.Path:
        """Raccourci créant un JPEG dans le répertoire des sources du test."""
        return make_jpeg(directory if directory is not None else self.source_dir, name, size)


# ---------------------------------------------------------------------------
# Environnement graphique
# ---------------------------------------------------------------------------

def is_packed(widget) -> bool:
    """
    Indique si un widget occupe actuellement sa place dans la fenêtre.

    `winfo_ismapped()` ne convient pas ici : il renvoie faux dès que la fenêtre
    parente est masquée, ce qui est le cas des fenêtres de test. Interroger le
    gestionnaire de placement traduit exactement l'effet de `pack`/`pack_forget`.

    Args:
        widget: Le widget à examiner.

    Returns:
        True si le widget est placé par `pack`.
    """
    return widget.winfo_manager() == "pack"


_shared_root = None
_gui_error: Optional[str] = None


def get_shared_root():
    """
    Retourne la fenêtre racine partagée par les tests d'interface.

    Une seule racine est créée pour toute la suite : chaque test travaille
    ensuite dans une `Toplevel` qu'il détruit, ce qui évite de multiplier les
    interpréteurs Tcl.

    Returns:
        La fenêtre racine, ou None si aucun affichage n'est disponible.
    """
    global _shared_root, _gui_error

    if _shared_root is not None or _gui_error is not None:
        return _shared_root

    try:
        import ttkbootstrap as ttk
        _shared_root = ttk.Window(themename="darkly")
        _shared_root.withdraw()
    except Exception as e:  # pragma: no cover - dépend de la machine de test
        _gui_error = str(e)
        _shared_root = None

    return _shared_root


def gui_available() -> bool:
    """Indique si un affichage graphique est utilisable sur cette machine."""
    return get_shared_root() is not None


#: Décorateur appliqué aux cas de test nécessitant un affichage.
requires_gui = unittest.skipUnless(
    gui_available(), "Aucun affichage graphique disponible (exécution sans écran)"
)


class GuiTestCase(IsolatedTestCase):
    """
    Cas de test disposant d'une fenêtre Tkinter réelle.

    La Vue et le Contrôleur sont exercés sur de véritables widgets : les états
    vérifiés (jauge affichée, bouton verrouillé) sont ceux que l'utilisateur
    verrait effectivement.
    """

    def setUp(self) -> None:
        super().setUp()
        import ttkbootstrap as ttk

        self.root = get_shared_root()
        # Chaque test dispose de sa propre fenêtre, détruite juste après
        self.window = ttk.Toplevel(self.root)
        self.window.withdraw()

    def tearDown(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass
        super().tearDown()

    def pump(self, duration_ms: int = 50) -> None:
        """
        Fait tourner la boucle d'événements pendant une durée donnée.

        Args:
            duration_ms: La durée d'animation de la boucle, en millisecondes.
        """
        deadline = time.perf_counter() + (duration_ms / 1000.0)
        while time.perf_counter() < deadline:
            self.root.update()
            time.sleep(0.005)

    def pump_until(self, predicate: Callable[[], bool], timeout: float = 20.0) -> bool:
        """
        Fait tourner la boucle d'événements jusqu'à ce qu'une condition soit vraie.

        C'est l'équivalent, pour un test, de l'attente d'un utilisateur devant
        l'écran : les rappels `after()` du Contrôleur sont réellement exécutés.

        Args:
            predicate: La condition d'arrêt.
            timeout: Le délai maximal d'attente, en secondes.

        Returns:
            True si la condition a été satisfaite avant l'échéance.
        """
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self.root.update()
            if predicate():
                return True
            time.sleep(0.005)
        return False


class ProgressRecorder:
    """Rappel de progression enregistrant chacun de ses appels."""

    def __init__(self) -> None:
        self.calls: List[tuple] = []

    def __call__(self, done: int, total: int, filename: str) -> None:
        self.calls.append((done, total, filename))
