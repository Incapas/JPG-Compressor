import tkinter as tk
from tkinter import filedialog
from typing import Dict, Any, List, Tuple

import ttkbootstrap as ttk
from ttkbootstrap import Meter, Label, Checkbutton, Button, Entry, Floodgauge
from ttkbootstrap.dialogs import Messagebox

from .constants import (
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_QUALITY,
    DEFAULT_RESIZE,
    OUTPUT_FORMATS,
    WINDOW_GEOMETRY,
    WINDOW_TITLE,
)


class ApplicationView:
    """
    Construit l'intégralité de l'interface graphique utilisateur (GUI) en utilisant
    Tkinter et la librairie ttkbootstrap.

    Cette classe contient toutes les références de widgets, les variables de contrôle
    (tk.Var) pour gérer l'état de l'interface, et les méthodes pour interagir
    avec le système de fichiers (dialogues).
    """

    def __init__(self, master: tk.Tk) -> None:
        """
        Initialise la Vue, configure la fenêtre principale et les variables de contrôle.

        Args:
            master: La fenêtre principale (root) de l'application.
        """
        # Stocke la référence à la fenêtre principale
        self.master: tk.Tk = master

        # Configure les propriétés de base de la fenêtre
        master.title(WINDOW_TITLE)
        master.geometry(WINDOW_GEOMETRY)
        master.resizable(False, False)

        # Variable pour l'activation du mode "Stockage optimisé"
        self.optimized_storage_var: tk.BooleanVar = tk.BooleanVar(value=False)

        # Variables pour les options de compression
        self.optimized_encoding_var: tk.BooleanVar = tk.BooleanVar(value=False)
        self.strip_metadata_var: tk.BooleanVar = tk.BooleanVar(value=False)
        self.progressive_loading_var: tk.BooleanVar = tk.BooleanVar(value=False)

        # Variables pour les options d'exportation
        self.zip_export_var: tk.BooleanVar = tk.BooleanVar(value=False)
        self.delete_originals_var: tk.BooleanVar = tk.BooleanVar(value=False)
        self.add_suffixe_var: tk.BooleanVar = tk.BooleanVar(value=False)

        # Variable pour le format de sortie (Radiobuttons)
        self.output_format_var: tk.StringVar = tk.StringVar(value=DEFAULT_OUTPUT_FORMAT)

        # Variable pour le chemin d'exportation (Entry)
        self.export_path_var: tk.StringVar = tk.StringVar(value="")

        # Variables pilotant la jauge de progression (valeur 0-100 et texte affiché)
        self.progress_value_var: tk.IntVar = tk.IntVar(value=0)
        self.progress_text_var: tk.StringVar = tk.StringVar(value="")

        # --- Références aux widgets principaux (initialisés à None avant _create_widgets) ---
        self.quality_meter: Meter | None = None
        self.resize_meter: Meter | None = None
        self.status_label: Label | None = None
        self.progress_gauge: Floodgauge | None = None
        self.import_button: Button | None = None
        self.export_final_button: Button | None = None
        self.reset_button: Button | None = None
        self.delete_checkbutton: Checkbutton | None = None
        self.widget_references: Dict[str, Any] = {} # Pour stocker les widgets nécessaires au Contrôleur

        # Widgets verrouillés pendant une compression, pour empêcher toute
        # modification des réglages alors que le traitement est déjà lancé.
        self._lockable_widgets: List[Any] = []

        # Lance la construction de l'interface
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Construit et place tous les widgets de l'application dans la fenêtre."""

        # --- BOUTON "STOCKAGE OPTIMISÉ" (TOUT EN HAUT) ---
        # Création du Checkbutton de bascule de mode optimisé
        optimized_storage_checkbutton: Checkbutton = ttk.Checkbutton(
            self.master,
            text="Stockage optimisé",
            bootstyle="warning-round-toggle",
            padding=10,
            variable=self.optimized_storage_var,
        )
        # Positionnement : rempli horizontalement, avec marges
        optimized_storage_checkbutton.pack(fill="x", padx=20, pady=(15, 0))
        self._lockable_widgets.append(optimized_storage_checkbutton)


        # --------------------------------------------------------------------------------------
        # --- CADRE PRINCIPAL (OPTIONS DE COMPRESSION) ---
        # --------------------------------------------------------------------------------------

        # Création du LabelFrame principal pour les réglages de compression
        settings_frame: ttk.Labelframe = ttk.Labelframe(
            self.master,
            text="Compression",
            padding=15,
            bootstyle="primary"
        )
        settings_frame.pack(fill="x", padx=20, pady=(15, 0))

        # Cadre conteneur horizontal pour aligner les trois blocs (Meters, Format, Optimisation)
        horizontal_master_frame: ttk.Frame = ttk.Frame(settings_frame)
        horizontal_master_frame.pack(padx=10, pady=10, anchor="center")

        # BLOC 1 : METER DANS UN LABELFRAME (Contrôles Principaux)
        meter_group_frame: ttk.Labelframe = ttk.Labelframe(horizontal_master_frame, text="Contrôles Principaux", padding=10, bootstyle="info")
        meter_group_frame.pack(side="left", padx=15)

        # --- Qualité de compression (Meter) ---
        quality_container: ttk.Frame = ttk.Frame(meter_group_frame)
        quality_container.pack(side="left", padx=10)
        # Création du widget Meter pour la qualité
        self.quality_meter = ttk.Meter(
            quality_container,
            interactive=True, # Permet à l'utilisateur d'interagir avec la jauge
            bootstyle="info",
            subtext="de qualité",
            textright="%",
            amountused=DEFAULT_QUALITY,
        )
        self.quality_meter.pack()

        # --- Redimensionnement (Meter) ---
        resize_container: ttk.Frame = ttk.Frame(meter_group_frame)
        resize_container.pack(side="left", padx=15)
        # Création du widget Meter pour le redimensionnement
        self.resize_meter = ttk.Meter(
            resize_container,
            interactive=True, # Permet à l'utilisateur d'interagir avec la jauge
            bootstyle="info",
            subtext="de la taille originale",
            textright="%",
            amountused=DEFAULT_RESIZE,
        )
        self.resize_meter.pack()

        # BLOC 2 : FORMAT (RADIOBUTTONS)
        format_block_frame: ttk.Labelframe = ttk.Labelframe(horizontal_master_frame, text="Format de sortie", padding=20, bootstyle="info")
        format_block_frame.pack(side="left", padx=15, fill="y", ipadx=30)

        # Création des Radiobuttons pour le choix du format (JPG, JPEG, WEBP)
        for fmt in OUTPUT_FORMATS:
            format_radiobutton = ttk.Radiobutton(
                format_block_frame,
                text=fmt,
                value=fmt,
                bootstyle="info",
                variable=self.output_format_var # Lié à la variable de format
            )
            format_radiobutton.pack(pady=5, padx=5, anchor="w")
            self._lockable_widgets.append(format_radiobutton)

        # BLOC 3 : OPTIMISATION (CHECKBUTTONS)
        fine_opt_block_frame: ttk.Labelframe = ttk.Labelframe(horizontal_master_frame, text="Optimisation", padding=20, bootstyle="info")
        fine_opt_block_frame.pack(side="left", padx=15, fill="y")

        # Checkbutton pour l'encodage optimisé
        optimized_encoding_checkbutton = ttk.Checkbutton(
            fine_opt_block_frame,
            text="Encodage optimisé",
            bootstyle="info-round-toggle",
            variable=self.optimized_encoding_var
        )
        optimized_encoding_checkbutton.pack(pady=5, anchor="w")

        # Checkbutton pour la suppression des métadonnées
        strip_metadata_checkbutton = ttk.Checkbutton(
            fine_opt_block_frame,
            text="Suppression des métadonnées",
            bootstyle="info-round-toggle",
            variable=self.strip_metadata_var
        )
        strip_metadata_checkbutton.pack(pady=5, anchor="w")

        # Checkbutton pour l'affichage progressif
        progressive_loading_checkbutton = ttk.Checkbutton(
            fine_opt_block_frame,
            text="Affichage progressif (JPEG)",
            bootstyle="info-round-toggle",
            variable=self.progressive_loading_var
        )
        progressive_loading_checkbutton.pack(pady=5, anchor="w")

        self._lockable_widgets.extend([
            optimized_encoding_checkbutton,
            strip_metadata_checkbutton,
            progressive_loading_checkbutton,
        ])


        # --------------------------------------------------------------------------------------
        # --- CADRE 2 : CONFIGURATION DE L'EXPORTATION (Destination + Options) ---
        # --------------------------------------------------------------------------------------

        # Création du LabelFrame pour les réglages d'exportation
        export_config_frame: ttk.Labelframe = ttk.Labelframe(
            self.master,
            text="Exportation",
            padding=15,
            bootstyle="primary"
        )
        export_config_frame.pack(fill="x", padx=20, pady=(35, 0))

        # 1. Chemin de sauvegarde (sur une ligne)
        path_container: ttk.Frame = ttk.Frame(export_config_frame)
        path_container.pack(fill="x", pady=(0, 15))

        # Label d'information
        ttk.Label(path_container, text="Chemin de la sauvegarde :").pack(side="left", padx=(0, 10))

        # Champ de texte (Entry) affichant le chemin d'exportation (lecture seule)
        export_path_entry: Entry = ttk.Entry(
            path_container,
            textvariable=self.export_path_var, # Lié à la variable de chemin
            bootstyle="info",
            state="readonly" # Empêche l'édition directe par l'utilisateur
        )
        export_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Bouton pour ouvrir la boîte de dialogue de sélection de dossier
        export_path_button: Button = ttk.Button(
            path_container,
            text="...",
            bootstyle="info-outline",
            # La commande sera définie par le contrôleur
        )
        export_path_button.pack(side="left")
        self._lockable_widgets.append(export_path_button)

        # 2. Options d'Exportation (ZIP / Suppression / Suffixe)
        options_container: ttk.Frame = ttk.Frame(export_config_frame)
        options_container.pack(fill="x")

        # Checkbutton pour l'export en ZIP
        zip_checkbutton = ttk.Checkbutton(
            options_container,
            text="Exporter dans un fichier .ZIP",
            bootstyle="info-round-toggle",
            variable=self.zip_export_var
        )
        zip_checkbutton.pack(padx=(0, 30), side="left")

        # Checkbutton pour la suppression des originaux
        self.delete_checkbutton = ttk.Checkbutton(
            options_container,
            text="Supprimer les originaux après l'export",
            bootstyle="info-round-toggle",
            variable=self.delete_originals_var
        )
        self.delete_checkbutton.pack(padx=(0, 30), side="left")

        # Checkbutton pour l'ajout du suffixe
        suffixe_checkbutton = ttk.Checkbutton(
            options_container,
            text="Ajouter le suffixe '_compressée'",
            bootstyle="info-round-toggle",
            variable=self.add_suffixe_var
        )
        suffixe_checkbutton.pack(side="left")

        self._lockable_widgets.extend([zip_checkbutton, self.delete_checkbutton, suffixe_checkbutton])


        # --------------------------------------------------------------------------------------
        # --- LIGNE D'ACTIONS (Trois boutons) ---
        # --------------------------------------------------------------------------------------

        action_buttons_frame: ttk.Frame = ttk.Frame(self.master, padding=20)
        action_buttons_frame.pack(fill="x", pady=(30, 10))

        # 1. Bouton: Importer des images
        self.import_button = ttk.Button(
            action_buttons_frame,
            text="Importer des images",
            bootstyle="info-outline",
            width=25,
            # La commande sera définie par le contrôleur
        )
        self.import_button.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # 2. Bouton: Exporter images (devient "Annuler" pendant un traitement)
        self.export_final_button = ttk.Button(
            action_buttons_frame,
            text="Exporter des images",
            bootstyle="success-outline",
            width=25,
            state="disabled", # Désactivé par défaut
            # La commande sera définie par le contrôleur
        )
        self.export_final_button.pack(side="left", fill="x", expand=True, padx=10)

        # 3. Bouton: Réinitialiser
        self.reset_button = ttk.Button(
            action_buttons_frame,
            text="Réinitialiser",
            bootstyle="danger-outline",
            width=25,
            state="disabled", # Désactivé par défaut
            # La commande sera définie par le contrôleur
        )
        self.reset_button.pack(side="left", fill="x", expand=True, padx=(10, 0))


        # --------------------------------------------------------------------------------------
        # --- ÉTAT ET RÉSULTAT (Sous les boutons) ---
        # --------------------------------------------------------------------------------------

        # Conteneur commun au label de statut et à la jauge de progression :
        # les deux occupent tour à tour le même emplacement, ce qui évite toute
        # variation de hauteur dans une fenêtre non redimensionnable.
        self.status_container: ttk.Frame = ttk.Frame(self.master)
        self.status_container.pack(fill="x", padx=5)

        # Label d'état affichant les messages d'information/erreur/succès
        self.status_label = ttk.Label(
            self.status_container,
            text="Aucune image n'a été sélectionnée",
            padding=15,
            bootstyle="info"
        )
        self.status_label.pack(fill="x")

        # Jauge de progression, masquée tant qu'aucune compression n'est en cours
        self.progress_gauge = ttk.Floodgauge(
            self.status_container,
            bootstyle="success",
            maximum=100,
            thickness=46,
            font=("Helvetica", 11, "bold"),
            variable=self.progress_value_var,
            textvariable=self.progress_text_var,
        )

        # Stockage des références des widgets pour le Contrôleur
        self.widget_references = {
            'import_button': self.import_button,
            'export_final_button': self.export_final_button,
            'reset_button': self.reset_button,
            'optimized_storage_checkbutton': optimized_storage_checkbutton, # Le Checkbutton de bascule en haut
            'export_path_button': export_path_button, # Le bouton pour choisir le chemin (les points de suspension)
        }

    # --- Méthodes publiques de mise à jour de la Vue (appelées par le Contrôleur) ---

    def update_status_label(self, message: str, bootstyle: str = "info") -> None:
        """
        Met à jour le texte et le style (couleur) du Label de statut en bas de l'application.

        Args:
            message: Le nouveau texte à afficher.
            bootstyle: Le style ttkbootstrap à appliquer (e.g., 'info', 'success', 'danger', 'warning').
        """
        # Configure le texte et le style visuel
        self.status_label.configure(text=message, bootstyle=bootstyle)

    def update_state_buttons(self, import_enabled: bool, export_enabled: bool, reset_enabled: bool) -> None:
        """
        Met à jour l'état (actif/désactivé) des trois boutons d'action principaux.

        Args:
            import_enabled: True pour activer le bouton d'importation, False pour le désactiver.
            export_enabled: True pour activer le bouton d'exportation, False pour le désactiver.
            reset_enabled: True pour activer le bouton de réinitialisation, False pour le désactiver.
        """
        # Configure l'état du bouton d'importation
        self.import_button.configure(state="normal" if import_enabled else "disabled")
        # Configure l'état du bouton d'exportation
        self.export_final_button.configure(state="normal" if export_enabled else "disabled")
        # Configure l'état du bouton de réinitialisation
        self.reset_button.configure(state="normal" if reset_enabled else "disabled")

    def set_meter_values(self, quality: int, resize: int) -> None:
        """
        Définit les valeurs affichées et utilisées par les widgets Meter de qualité et de redimensionnement.

        Args:
            quality: La nouvelle valeur (entre 0 et 100) pour le Meter de qualité.
            resize: La nouvelle valeur (entre 0 et 100) pour le Meter de redimensionnement.
        """
        # Utilise amountusedvar pour changer la valeur interactive du Meter
        self.quality_meter.amountusedvar.set(quality)
        self.resize_meter.amountusedvar.set(resize)

    # --- Gestion de l'état "traitement en cours" ---

    def begin_processing(self, total_images: int) -> None:
        """
        Bascule l'interface en mode traitement : la jauge remplace le label de
        statut, les réglages sont verrouillés et le bouton d'export devient
        un bouton d'annulation.

        Args:
            total_images: Le nombre d'images à traiter, affiché dans la jauge.
        """
        # Verrouille tous les réglages pour éviter une modification en cours de route
        self._set_options_enabled(False)
        self.import_button.configure(state="disabled")
        self.reset_button.configure(state="disabled")

        # Le bouton d'export se mue en bouton d'annulation
        self.export_final_button.configure(
            text="Annuler", bootstyle="danger", state="normal"
        )

        # Initialise puis affiche la jauge à la place du label de statut
        self.progress_value_var.set(0)
        self.progress_text_var.set(f"0 % — 0 / {total_images}")
        self.status_label.pack_forget()
        self.progress_gauge.pack(fill="x")

    def update_progress(self, done: int, total: int, filename: str) -> None:
        """
        Met à jour la jauge de progression.

        Args:
            done: Le nombre d'images déjà traitées.
            total: Le nombre total d'images à traiter.
            filename: Le nom du fichier qui vient d'être traité.
        """
        percent: int = int((done / total) * 100) if total > 0 else 0
        self.progress_value_var.set(percent)
        self.progress_text_var.set(f"{percent} % — {done} / {total} — {filename}")

    def end_processing(self) -> None:
        """
        Quitte le mode traitement : la jauge s'efface, le label de statut
        reprend sa place et les réglages sont déverrouillés.
        """
        self.progress_gauge.pack_forget()
        self.status_label.pack(fill="x")

        # Rétablit le bouton d'export dans son apparence normale
        self.export_final_button.configure(
            text="Exporter des images", bootstyle="success-outline"
        )

        self._set_options_enabled(True)

    def set_cancelling(self) -> None:
        """Signale visuellement qu'une annulation est demandée et en attente."""
        self.export_final_button.configure(state="disabled", text="Annulation...")
        self.progress_text_var.set("Annulation en cours...")

    def _set_options_enabled(self, enabled: bool) -> None:
        """
        Active ou désactive tous les widgets de réglage.

        Args:
            enabled: True pour rendre les réglages modifiables, False pour les verrouiller.
        """
        state: str = "normal" if enabled else "disabled"
        for widget in self._lockable_widgets:
            try:
                widget.configure(state=state)
            except tk.TclError:
                # Un widget détruit ou ne gérant pas l'option 'state' est ignoré
                continue

    # --- Boîtes de dialogue ---

    def open_directory_dialog(self) -> str:
        """
        Ouvre la boîte de dialogue native pour sélectionner un répertoire de destination.

        Returns:
            Le chemin du répertoire sélectionné ou une chaîne vide si annulé.
        """
        # Retourne directement le résultat de la fonction Tkinter
        return filedialog.askdirectory(
            title="Sélectionner le dossier d'export"
        )

    def open_files_dialog(self) -> Tuple[str, ...]:
        """
        Ouvre la boîte de dialogue native pour sélectionner un ou plusieurs fichiers images.

        Returns:
            Un tuple contenant les chemins d'accès absolus des fichiers sélectionnés,
            ou un tuple vide si annulé.
        """
        # Retourne le tuple des chemins des fichiers sélectionnés
        return filedialog.askopenfilenames(
            title="Sélectionner les images à compresser",
            # Filtre les types de fichiers acceptés
            filetypes=[("Image Files", "*.jpg *.jpeg")]
        )

    def show_failure_report(self, failures: List[Tuple[str, str]]) -> None:
        """
        Affiche le détail des fichiers qui n'ont pas pu être traités.

        Args:
            failures: La liste des couples (nom de fichier, raison de l'échec).
        """
        if not failures:
            return

        # Au-delà de quelques lignes, la boîte de dialogue devient illisible :
        # le détail complet reste disponible dans logs/application.log.
        shown = failures[:10]
        lines: List[str] = [f"• {name} : {reason}" for name, reason in shown]

        if len(failures) > len(shown):
            lines.append(f"... et {len(failures) - len(shown)} autre(s).")

        Messagebox.show_warning(
            message=(
                f"{len(failures)} fichier(s) n'ont pas pu être exportés :\n\n"
                + "\n".join(lines)
                + "\n\nLe détail complet figure dans logs/application.log."
            ),
            title="Fichiers non exportés",
            parent=self.master,
        )
