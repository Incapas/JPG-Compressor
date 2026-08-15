"""
Constantes partagées par le Modèle, la Vue et le Contrôleur.

Centraliser ces valeurs évite qu'un réglage par défaut diverge entre la
construction de l'interface (Vue) et sa réinitialisation (Contrôleur).
"""

# --- Réglages par défaut de l'application ---
DEFAULT_QUALITY: int = 80          # Qualité de compression au démarrage (%)
DEFAULT_RESIZE: int = 100          # Redimensionnement au démarrage (% de la taille d'origine)
DEFAULT_OUTPUT_FORMAT: str = "JPG" # Format de sortie au démarrage

# --- Réglages appliqués par le mode "Stockage optimisé" ---
OPTIMIZED_QUALITY: int = 50
OPTIMIZED_RESIZE: int = 75
OPTIMIZED_OUTPUT_FORMAT: str = "WEBP"

# --- Formats ---
# Formats Pillow réellement acceptés à l'importation. 'MPO' est le conteneur
# multi-images utilisé par de nombreux appareils photo : c'est un JPEG valide.
VALID_INPUT_FORMATS: frozenset = frozenset({"JPEG", "MPO"})

# Extensions proposées dans la boîte de dialogue et acceptées au glisser-déposer.
INPUT_EXTENSIONS: tuple = (".jpg", ".jpeg")

# Formats proposés en sortie (le doublon JPG/JPEG ne change que l'extension).
OUTPUT_FORMATS: tuple = ("JPG", "JPEG", "WEBP")

# --- Interface ---
WINDOW_TITLE: str = "Compresseur de fichiers JPG/JPEG"
WINDOW_GEOMETRY: str = "1000x650"

# Intervalle (ms) de relecture de la file de progression par le Contrôleur.
PROGRESS_POLL_MS: int = 100
