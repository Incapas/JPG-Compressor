"""
Création de la fenêtre principale, avec prise en charge optionnelle du
glisser-déposer de fichiers.

Le glisser-déposer repose sur `tkinterdnd2`, qui embarque la bibliothèque
native `tkdnd` pour Windows (x86/x64/arm64) et macOS (x64/arm64). La
dépendance est volontairement traitée comme facultative : si elle est absente
ou si son chargement échoue, l'application démarre normalement, seul le
glisser-déposer étant indisponible.
"""
import logging
import pathlib
from typing import Callable, List, Optional

import ttkbootstrap as ttk

from .constants import INPUT_EXTENSIONS

logger = logging.getLogger(__name__)

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE: bool = True
except Exception as import_error:  # pragma: no cover - dépend de l'installation locale
    TkinterDnD = None
    DND_FILES = None
    DND_AVAILABLE = False
    logger.info(f"Glisser-déposer indisponible (tkinterdnd2 non chargé): {import_error}")


if DND_AVAILABLE:

    class _DnDWindow(ttk.Window, TkinterDnD.DnDWrapper):
        """
        Fenêtre ttkbootstrap enrichie des méthodes de glisser-déposer de tkdnd.

        L'héritage multiple est la méthode recommandée pour combiner un thème
        ttkbootstrap avec tkinterdnd2 : `ttk.Window` fournit le style, le
        `DnDWrapper` fournit `drop_target_register` et `dnd_bind`.
        """

        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            # Charge la bibliothèque native tkdnd dans cet interpréteur Tcl
            self.TkdndVersion = TkinterDnD._require(self)


def create_main_window(title: str, geometry: str, themename: str = "darkly") -> ttk.Window:
    """
    Construit la fenêtre principale de l'application.

    Tente d'abord une fenêtre compatible glisser-déposer et retombe sur une
    fenêtre ttkbootstrap classique en cas d'échec (bibliothèque absente ou
    binaire natif incompatible avec la plateforme).

    Args:
        title: Le titre de la fenêtre.
        geometry: La géométrie initiale, au format "LARGEURxHAUTEUR".
        themename: Le nom du thème ttkbootstrap.

    Returns:
        La fenêtre principale. Son attribut `dnd_enabled` indique si le
        glisser-déposer est utilisable.
    """
    window: Optional[ttk.Window] = None

    if DND_AVAILABLE:
        try:
            window = _DnDWindow(title=title, themename=themename)
            window.dnd_enabled = True
        except Exception as e:
            # Le chargement du binaire natif peut échouer sur une plateforme
            # non prévue : on repart alors sur une fenêtre standard.
            logger.warning(f"Initialisation du glisser-déposer impossible: {e}")
            window = None

    if window is None:
        window = ttk.Window(title=title, themename=themename)
        window.dnd_enabled = False

    window.geometry(geometry)
    # Empêche le redimensionnement pour maintenir une disposition stable
    window.resizable(False, False)

    return window


def enable_file_drop(widget, callback: Callable[[List[str]], None]) -> bool:
    """
    Déclare un widget comme cible de dépôt de fichiers.

    Args:
        widget: Le widget cible (typiquement la fenêtre principale).
        callback: Fonction appelée avec la liste des chemins déposés, déjà
            filtrée sur les extensions JPG/JPEG. Elle n'est pas appelée si le
            dépôt ne contient aucun fichier exploitable.

    Returns:
        True si la cible a pu être enregistrée, False sinon.
    """
    if not getattr(widget, "dnd_enabled", False) or DND_FILES is None:
        return False

    def _on_drop(event) -> None:
        # tkdnd renvoie une chaîne Tcl : les chemins contenant des espaces sont
        # entourés d'accolades. splitlist effectue le découpage correctement.
        try:
            raw_paths = widget.tk.splitlist(event.data)
        except Exception as e:
            logger.error(f"Dépôt illisible: {e}")
            return

        callback(_collect_image_paths(raw_paths))

    try:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind('<<Drop>>', _on_drop)
        return True
    except Exception as e:  # pragma: no cover - dépend de la plateforme
        logger.warning(f"Enregistrement de la cible de dépôt impossible: {e}")
        return False


def _collect_image_paths(raw_paths) -> List[str]:
    """
    Filtre les chemins déposés pour ne conserver que les fichiers JPG/JPEG.

    Un dossier déposé est parcouru (sans récursion) afin d'en extraire les
    images qu'il contient directement : c'est le geste attendu quand on fait
    glisser un dossier de photos sur la fenêtre.

    Args:
        raw_paths: Les chemins bruts issus de l'événement de dépôt.

    Returns:
        La liste des chemins de fichiers retenus.
    """
    collected: List[str] = []

    for raw_path in raw_paths:
        path = pathlib.Path(str(raw_path))

        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_file() and child.suffix.lower() in INPUT_EXTENSIONS:
                    collected.append(str(child))
        elif path.is_file() and path.suffix.lower() in INPUT_EXTENSIONS:
            collected.append(str(path))

    return collected
