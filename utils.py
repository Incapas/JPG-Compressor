import sys
import os


def get_resource_path(relative_path: str) -> str:
    """
    Obtient le chemin absolu vers une ressource EN LECTURE SEULE, compatible
    avec PyInstaller lorsque l'application est packagée.
    
    À utiliser pour les icônes, les images d'interface, ou les fichiers de 
    configuration statiques non modifiables.
    """
    try:
        # Chemin lorsque l'application est packagée (dans le répertoire temp MEIPASS)
        # Note: Cela ne fonctionne pas pour les fichiers en écriture.
        base_path = sys._MEIPASS
    except Exception:
        # Chemin lorsque l'application est exécutée comme un script Python
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_writable_path(relative_path: str) -> str:
    """
    Obtient un chemin d'accès en ÉCRITURE/MODIFICATION, idéal pour les logs, 
    ou les fichiers de réglages utilisateurs.
    
    Il utilise le répertoire de l'exécutable (si packagé) ou le répertoire
    courant (si en mode script) comme base.
    """
    if getattr(sys, 'frozen', False):
        # Si packagé, utilise le répertoire où se trouve l'exécutable
        base_path = os.path.dirname(sys.executable)
    else:
        # Si script, utilise le répertoire de travail
        base_path = os.path.abspath(".")
        
    # Construit le chemin complet et crée les répertoires intermédiaires (ex: 'logs/')
    full_path = os.path.join(base_path, relative_path)
    # Crée le dossier parent si nécessaire (ex: crée 'logs/' si le fichier est 'logs/application.log')
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    return full_path
