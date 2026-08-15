from mvc.constants import WINDOW_GEOMETRY, WINDOW_TITLE
from mvc.controller import ApplicationController
from mvc.model import configure_logging
from mvc.window import create_main_window


def main() -> None:
    """
    Point d'entrée de l'application : construit la fenêtre, instancie le
    Contrôleur (qui crée le Modèle et la Vue) puis démarre la boucle graphique.
    """
    # Installe le fichier de journalisation (logs/application.log)
    configure_logging()

    # Création de la fenêtre principale (Root Window)
    # Utilise le thème "darkly" de ttkbootstrap pour une apparence moderne, et
    # active le glisser-déposer de fichiers lorsque tkinterdnd2 est disponible.
    app = create_main_window(
        title=WINDOW_TITLE,
        geometry=WINDOW_GEOMETRY,
        themename="darkly",
    )

    # Initialisation du Contrôleur
    # Le Contrôleur crée et lie le Modèle et la Vue
    ApplicationController(app)

    # Lancement de la boucle principale de l'interface graphique
    app.mainloop()


if __name__ == '__main__':
    main()
