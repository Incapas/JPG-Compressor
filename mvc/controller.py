import queue
import logging
import threading
import tkinter as tk
from typing import Dict, Any, List, Optional, Tuple

from .model import ApplicationModel
from .view import ApplicationView
from .window import enable_file_drop
from .constants import (
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_QUALITY,
    DEFAULT_RESIZE,
    OPTIMIZED_OUTPUT_FORMAT,
    OPTIMIZED_QUALITY,
    OPTIMIZED_RESIZE,
    PROGRESS_POLL_MS,
)

logger = logging.getLogger(__name__)


class ApplicationController:
    """
    Gère le flux de l'application, les interactions utilisateur,
    et coordonne le Modèle et la Vue.

    La compression est exécutée dans un thread secondaire. Celui-ci ne touche
    jamais aux widgets : il publie sa progression dans une file, que le thread
    principal vient relire périodiquement via `after()`. C'est la seule façon
    correcte de faire progresser une interface Tkinter, qui n'est pas
    thread-safe.
    """
    def __init__(self, master: tk.Tk) -> None:
        """
        Initialise le contrôleur, le modèle et la vue.

        Args:
            master: La fenêtre principale Tkinter.
        """
        self.master: tk.Tk = master
        # Initialisation du Modèle (logique et données)
        self.model: ApplicationModel = ApplicationModel()
        # Initialisation de la Vue (interface graphique)
        self.view: ApplicationView = ApplicationView(master)

        # --- État du traitement en arrière-plan ---
        self._worker_thread: Optional[threading.Thread] = None
        self._progress_queue: queue.Queue = queue.Queue()
        self._cancel_event: Optional[threading.Event] = None

        # Synchronisation initiale : Initialise le chemin d'exportation de la Vue avec la valeur du Modèle
        self.view.export_path_var.set(self.model.export_path)

        # Lie les méthodes du contrôleur aux événements des widgets de la vue
        self._attach_commands()

        # Active le glisser-déposer de fichiers sur la fenêtre, si disponible
        self._setup_drag_and_drop()

        # Initialise l'état des boutons au lancement de l'application
        self.view.update_state_buttons(import_enabled=True, export_enabled=False, reset_enabled=False)

    def _attach_commands(self) -> None:
        """Lie les méthodes du contrôleur (handlers) aux commandes des widgets interactifs de la vue."""

        # Récupère les références des widgets nécessaires
        widgets: Dict[str, Any] = self.view.widget_references

        # Liaison des commandes des boutons d'action principaux
        widgets['import_button'].configure(command=self.handle_import_images)
        # Ce bouton assure deux rôles selon l'état de l'application (exporter / annuler)
        widgets['export_final_button'].configure(command=self.handle_export_button)
        widgets['reset_button'].configure(command=self.handle_reset)

        # Liaison du bouton de sélection du chemin d'exportation
        widgets['export_path_button'].configure(command=self.handle_select_export_path)

        # Liaison du Checkbutton de bascule du mode optimisé
        widgets['optimized_storage_checkbutton'].configure(command=self.handle_optimized_storage_toggle)

    def _setup_drag_and_drop(self) -> None:
        """Déclare la fenêtre comme cible de dépôt et adapte le message d'accueil."""
        if enable_file_drop(self.master, self.handle_dropped_files):
            self.view.update_status_label(
                "Aucune image n'a été sélectionnée — glissez vos fichiers JPG ici", "info"
            )

    # --- Gestionnaires d'événements (Handlers) ---

    def handle_select_export_path(self) -> None:
        """Gère l'ouverture du dialogue de sélection de répertoire et la persistance du chemin."""
        # Ouvre la boîte de dialogue de sélection de répertoire
        chosen_path: str = self.view.open_directory_dialog()

        if chosen_path:
            # 1. Met à jour le Modèle et le rend persistant via la fonction de sauvegarde
            self.model.write_config(chosen_path)

            # 2. Met à jour l'affichage de la Vue
            self.view.export_path_var.set(chosen_path)
            self.view.update_status_label(
                f"Dossier de destination sélectionné et sauvegardé : {chosen_path}", "success"
            )

    def handle_import_images(self) -> None:
        """Gère l'importation des images, le chargement dans le Modèle et la mise à jour de la Vue."""
        # Ouvre la boîte de dialogue de sélection des fichiers images
        files: Tuple[str, ...] = self.view.open_files_dialog()

        # Si la sélection est annulée (tuple vide)
        if not files:
            self.view.update_status_label("Importation annulée. Aucune image sélectionnée.", "info")
            return

        self._load_into_model(list(files))

    def handle_dropped_files(self, paths: List[str]) -> None:
        """
        Gère le dépôt de fichiers par glisser-déposer sur la fenêtre.

        Args:
            paths: Les chemins JPG/JPEG extraits du dépôt (fichiers et contenu
                direct des dossiers déposés).
        """
        # Un dépôt pendant un traitement est ignoré : les données du Modèle sont
        # en cours de lecture par le thread de compression.
        if self._is_processing():
            return

        if not paths:
            self.view.update_status_label(
                "Aucun fichier JPG/JPEG dans ce dépôt.", "warning"
            )
            return

        self._load_into_model(paths)

    def _load_into_model(self, paths: List[str]) -> None:
        """
        Charge une liste de chemins dans le Modèle et reflète le résultat dans la Vue.

        Args:
            paths: Les chemins des fichiers à charger.
        """
        # 1. Chargement des images dans le Modèle
        num_files: int
        rejected: List[str]
        num_files, rejected = self.model.load_images(paths)

        # 2. Mise à jour de l'interface utilisateur
        if num_files > 0:
            message: str = f"{num_files} image(s) sélectionnée(s) : Prêt pour l'export."
            if rejected:
                # Les fichiers écartés sont signalés plutôt que passés sous silence
                message += (
                    f" {len(rejected)} fichier(s) ignoré(s) : ne sont pas de vrais JPEG."
                )
            self.view.update_status_label(message, "warning" if rejected else "success")
            self.view.update_state_buttons(import_enabled=True, export_enabled=True, reset_enabled=True)
        else:
            # Affichage de l'échec
            reason: str = (
                f"Aucun des {len(rejected)} fichier(s) n'est un véritable JPEG."
                if rejected else "Aucune image valide n'a été chargée."
            )
            self.view.update_status_label(f"Échec de l'importation. {reason}", "danger")
            self.view.update_state_buttons(import_enabled=True, export_enabled=False, reset_enabled=False)

    def handle_optimized_storage_toggle(self) -> None:
        """Applique ou désactive les réglages pour le mode 'stockage optimisé' (réglages agressifs)."""

        # Vérifie l'état actuel de la variable de contrôle
        if self.view.optimized_storage_var.get():
            # --- Activation du mode optimisé ---
            self.view.set_meter_values(quality=OPTIMIZED_QUALITY, resize=OPTIMIZED_RESIZE)
            self.view.output_format_var.set(OPTIMIZED_OUTPUT_FORMAT)  # Meilleure compression
            self.view.optimized_encoding_var.set(True)            # Encodage optimisé activé
            self.view.strip_metadata_var.set(True)                # Suppression des métadonnées
            self.view.progressive_loading_var.set(True)           # Affichage progressif (si compatible)

            self.view.update_status_label(
                "Mode Stockage Optimisé activé. Les réglages ont été ajustés.", "warning"
            )
        else:
            # --- Retour aux réglages par défaut ---
            self.view.set_meter_values(quality=DEFAULT_QUALITY, resize=DEFAULT_RESIZE)
            self.view.output_format_var.set(DEFAULT_OUTPUT_FORMAT)
            self.view.optimized_encoding_var.set(False)
            self.view.strip_metadata_var.set(False)
            self.view.progressive_loading_var.set(False)

            # Réinitialise le message seulement si aucune image n'est chargée
            if not self.model.data:
                 self.view.update_status_label("Aucune image n'a été sélectionnée", "info")

    # --- Exportation (thread de traitement) ---

    def _is_processing(self) -> bool:
        """Indique si une compression est actuellement en cours."""
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def handle_export_button(self) -> None:
        """
        Point d'entrée unique du bouton central, qui change de rôle selon l'état :
        il lance l'exportation au repos, il l'annule pendant un traitement.
        """
        if self._is_processing():
            self.handle_cancel_export()
        else:
            self.handle_export_images()

    def handle_cancel_export(self) -> None:
        """Demande l'arrêt du traitement en cours à la prochaine image."""
        if self._cancel_event is not None:
            self._cancel_event.set()
            self.view.set_cancelling()

    def handle_export_images(self) -> None:
        """Collecte les options de la Vue et lance la compression en arrière-plan."""

        # Vérification préliminaire : y a-t-il des données à traiter ?
        if not self.model.data:
            self.view.update_status_label("Aucune image à exporter. Veuillez importer des fichiers.", "danger")
            return

        # 1. Collecte des options de la Vue
        options: Optional[Dict[str, Any]] = self._collect_options()
        if options is None:
            return

        # 2. Préparation du canal de communication avec le thread de traitement
        self._cancel_event = threading.Event()
        self._progress_queue = queue.Queue()

        # 3. Bascule de l'interface en mode traitement
        self.view.begin_processing(len(self.model.data))

        # 4. Lancement du thread. Il est 'daemon' pour ne pas retenir la fermeture
        # de l'application si l'utilisateur ferme la fenêtre en cours de route.
        self._worker_thread = threading.Thread(
            target=self._run_export, args=(options,), daemon=True
        )
        self._worker_thread.start()

        # 5. Démarrage de la relecture périodique de la file de progression
        self.master.after(PROGRESS_POLL_MS, self._poll_progress)

    def _collect_options(self) -> Optional[Dict[str, Any]]:
        """
        Lit les réglages courants de la Vue et les valide.

        Returns:
            Le dictionnaire d'options, ou None si la lecture ou la validation a échoué
            (le message d'erreur est alors déjà affiché).
        """
        try:
            options: Dict[str, Any] = {
                # Récupère la valeur du Meter de qualité
                'quality': self.view.quality_meter.amountusedvar.get(),
                # Récupère la valeur du Meter de redimensionnement et la convertit en facteur (e.g., 75% -> 0.75)
                'resize_factor': self.view.resize_meter.amountusedvar.get() / 100.0,
                # Récupère les valeurs des variables de contrôle
                'output_format': self.view.output_format_var.get(),
                'add_suffixe': self.view.add_suffixe_var.get(),
                'use_zip': self.view.zip_export_var.get(),
                'delete_originals': self.view.delete_originals_var.get(),
                'optimized_encoding': self.view.optimized_encoding_var.get(),
                'progressive_loading': self.view.progressive_loading_var.get(),
                'strip_metadata': self.view.strip_metadata_var.get(),
            }
        except Exception as e:
            # Gestion d'une erreur de lecture des widgets
            self.view.update_status_label(f"Échec de la lecture des paramètres: {e}", "danger")
            return None

        # Validation simple des paramètres (la validation complète est faite dans le Modèle)
        if not (1 <= options['quality'] <= 100):
            self.view.update_status_label("Erreur: La qualité de compression doit être entre 1 et 100.", "danger")
            return None

        return options

    def _run_export(self, options: Dict[str, Any]) -> None:
        """
        Exécute la compression. **Cette méthode tourne dans le thread secondaire**
        et ne doit donc jamais appeler la Vue directement : tout passe par la file.

        Args:
            options: Les options de compression collectées depuis la Vue.
        """
        def report(done: int, total: int, filename: str) -> None:
            """Rappel de progression : dépose simplement l'information dans la file."""
            self._progress_queue.put(("progress", done, total, filename))

        try:
            result = self.model.process_and_export(
                options,
                progress_callback=report,
                cancel_event=self._cancel_event,
            )
            self._progress_queue.put(("done", result))
        except Exception as e:
            # Filet de sécurité : une erreur imprévue ne doit pas laisser
            # l'interface bloquée en mode traitement.
            logger.exception("Erreur inattendue pendant l'exportation")
            self._progress_queue.put(("error", str(e)))

    def _poll_progress(self) -> None:
        """
        Vide la file de progression et met à jour la Vue.
        Exécutée dans le thread principal, elle se replanifie tant que le
        traitement n'a pas rendu son résultat final.
        """
        finished: bool = False

        try:
            while True:
                message = self._progress_queue.get_nowait()
                kind: str = message[0]

                if kind == "progress":
                    _, done, total, filename = message
                    self.view.update_progress(done, total, filename)
                elif kind == "done":
                    success_count, stats = message[1]
                    self._finish_export(success_count, stats)
                    finished = True
                elif kind == "error":
                    self._fail_export(message[1])
                    finished = True
        except queue.Empty:
            pass

        if not finished:
            # Replanifie la prochaine relecture de la file
            self.master.after(PROGRESS_POLL_MS, self._poll_progress)

    def _finish_export(self, success_count: int, stats: Dict[str, Any]) -> None:
        """
        Restaure l'interface et présente le bilan du traitement.

        Args:
            success_count: Le nombre d'images exportées avec succès.
            stats: Le dictionnaire de statistiques renvoyé par le Modèle.
        """
        self.view.end_processing()

        failures: List[Tuple[str, str]] = stats.get("failures", [])
        cancelled: bool = stats.get("cancelled", False)

        if success_count == 0:
            # Gestion de l'échec de traitement (récupère un message d'erreur si disponible)
            error_msg: str = stats.get("error_msg", "Aucune image n'a été traitée avec succès.")
            if cancelled:
                error_msg = "Traitement annulé avant le premier enregistrement."
            self.view.update_status_label(f"Échec de l'exportation. {error_msg}", "danger")
            self.view.update_state_buttons(import_enabled=True, export_enabled=True, reset_enabled=True)
        else:
            # Construction du message de bilan détaillé avec les statistiques
            prefix: str = "Exportation annulée" if cancelled else "Exportation terminée"
            message: str = (
                f"{prefix} : {success_count} image(s) compressée(s) avec succès. "
                f"| {stats['total_old_mo']:.2f} Mo -> {stats['total_new_mo']:.2f} Mo | "
                f"Différence: {stats['difference_mo']:.2f} Mo ({stats['gain_percent']:.1f}%)"
            )
            if failures:
                message += f" | {len(failures)} échec(s)"

            bootstyle: str = "warning" if (failures or cancelled) else "success"
            self.view.update_status_label(message, bootstyle)

            # Réactive le bouton d'importation et maintient le bouton de réinitialisation actif
            self.view.update_state_buttons(
                import_enabled=True, export_enabled=cancelled, reset_enabled=True
            )

        # Le détail des fichiers non exportés est présenté explicitement,
        # au lieu de rester enfoui dans le journal.
        if failures:
            self.view.show_failure_report(failures)

    def _fail_export(self, error_message: str) -> None:
        """
        Restaure l'interface après une erreur imprévue du thread de traitement.

        Args:
            error_message: Le message décrivant l'erreur rencontrée.
        """
        self.view.end_processing()
        self.view.update_status_label(f"Erreur inattendue : {error_message}", "danger")
        self.view.update_state_buttons(import_enabled=True, export_enabled=True, reset_enabled=True)

    def handle_reset(self) -> None:
        """Gère la réinitialisation complète de l'application (données et interface)."""

        # Une réinitialisation pendant un traitement corromprait les données lues
        # par le thread : l'action est simplement ignorée.
        if self._is_processing():
            return

        # 1. Réinitialisation du Modèle (ferme les objets PIL, vide les données)
        self.model.reset_data()
        # Recharge le chemin d'exportation persistant
        self.model.setup_export_path()

        # 2. Réinitialisation des variables de la Vue aux valeurs par défaut
        self.view.set_meter_values(quality=DEFAULT_QUALITY, resize=DEFAULT_RESIZE)
        self.view.optimized_storage_var.set(False)
        self.view.optimized_encoding_var.set(False)
        self.view.strip_metadata_var.set(False)
        self.view.progressive_loading_var.set(False)
        self.view.zip_export_var.set(False)
        self.view.delete_originals_var.set(False)
        self.view.add_suffixe_var.set(False)
        self.view.output_format_var.set(DEFAULT_OUTPUT_FORMAT)

        # Met à jour le chemin d'exportation dans la vue avec la valeur réinitialisée du modèle
        self.view.export_path_var.set(self.model.export_path)

        # Mise à jour de l'état final de la vue
        self.view.update_status_label("Aucune image n'a été sélectionnée", "info")
        self.view.update_state_buttons(import_enabled=True, export_enabled=False, reset_enabled=False)
