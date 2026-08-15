# Compresseur JPG/JPEG

> Réduisez le poids de vos photos par lots, sans jamais risquer de perdre un original.

Application de bureau qui compresse et redimensionne des fichiers JPG/JPEG en série. Chaque réglage — qualité, taille, format de sortie — se règle avant l'export, une barre de progression suit le traitement image par image, et le gain obtenu s'affiche en fin de course.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![ttkbootstrap](https://img.shields.io/badge/ttkbootstrap-1.18-FF4B4B)
![Tests](https://img.shields.io/badge/tests-113%20passing-16a34a)
![Couverture](https://img.shields.io/badge/couverture-99%25-16a34a)

---

## Le problème

Alléger un dossier de photos pour un site web ou un archivage se fait le plus souvent image par image, dans un éditeur ouvert puis refermé à chaque fichier. Les outils en ligne qui automatisent la tâche imposent d'envoyer ses photos sur un serveur tiers, et les scripts en ligne de commande demandent de retenir une syntaxe pour chaque réglage.

Cette application traite le lot entier en une fois, en local, avec un retour visuel sur l'avancement et sur les octets réellement gagnés.

## Fonctionnalités

- **Compression par lots avec suivi en temps réel** — la jauge affiche le pourcentage, le compteur et le nom du fichier en cours (`45 % — 9 / 20 — img_08.jpg`). Sur un lot de 20 photos de 3000×2000 (58 Mo), l'interface conserve une latence médiane de 31 ms, sans aucun gel.
- **Annulation à tout moment** — le bouton d'export se change en bouton d'annulation pendant le traitement ; les images déjà compressées sont conservées et le bilan les comptabilise.
- **Réglage fin de la compression** — qualité et redimensionnement se règlent sur deux jauges circulaires, avec sortie en JPG, JPEG ou WEBP.
- **Mode « Stockage optimisé »** — un interrupteur applique un profil agressif d'un seul geste : qualité 50, redimensionnement 75 %, sortie WEBP, encodage optimisé, métadonnées supprimées.
- **Glisser-déposer** — les fichiers se déposent directement sur la fenêtre ; déposer un dossier importe les JPG qu'il contient.
- **Aucun écrasement possible** — si le nom de sortie est déjà pris, sur le disque ou par une autre image du lot, la version compressée est écrite à côté (`photo_1.jpg`). Deux `IMG_001.jpg` venant de dossiers différents cohabitent.
- **Suppression optionnelle des originaux** — une fois cochée, l'option efface chaque source dès que sa version compressée est écrite, sans demande de confirmation. Une image dont la compression a échoué n'est jamais supprimée.
- **Fichiers d'entrée réellement vérifiés** — le format est lu par Pillow, pas déduit de l'extension : un PNG renommé en `.jpg` est écarté et signalé (`12 image(s) sélectionnée(s). 2 fichier(s) ignoré(s) : ne sont pas de vrais JPEG`).
- **Échecs listés, pas masqués** — les fichiers non exportés sont présentés avec leur cause au lieu de rester dans le journal.
- **Export en archive** — l'ensemble du lot peut être regroupé dans un `.zip`, dont la taille sert alors au calcul du gain.
- **Dossier de destination mémorisé** d'une session à l'autre.

## Technologies

| Outil | Rôle |
|---|---|
| [Python 3.12](https://www.python.org/) | Langage |
| [ttkbootstrap](https://ttkbootstrap.readthedocs.io/) | Interface graphique thématisée, jauges `Meter` et `Floodgauge` |
| [Pillow](https://pillow.readthedocs.io/) | Ouverture, redimensionnement et encodage des images |
| [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) | Glisser-déposer de fichiers (dépendance facultative) |
| [unittest](https://docs.python.org/3/library/unittest.html) | Tests (bibliothèque standard) |
| [coverage.py](https://coverage.readthedocs.io/) | Couverture de tests, branches comprises |
| [auto-py-to-exe](https://github.com/brentvollebregt/auto-py-to-exe) | Empaquetage en exécutable autonome |

## Installation

Prérequis : Python 3.12.

```bash
git clone https://github.com/<compte>/jpg-compressor.git
cd jpg-compressor

python3.12 -m venv env
source env/bin/activate          # Windows : env\Scripts\activate
pip install -r requirements.txt
```

Le glisser-déposer repose sur `tkinterdnd2`, qui embarque la bibliothèque native `tkdnd` pour Windows (x86/x64/arm64) et macOS (x64/arm64). Cette dépendance est facultative : si elle est absente ou incompatible avec la plateforme, l'application démarre normalement et seul le glisser-déposer est désactivé.

## Utilisation

```bash
python main.py
```

La fenêtre s'ouvre sur les réglages de compression. Importez des images par le bouton **Importer des images** ou en les faisant glisser sur la fenêtre, choisissez le dossier de destination, puis lancez **Exporter des images**. La jauge remplace alors la ligne d'état jusqu'à la fin du traitement.

Si l'environnement virtuel n'a pas été créé dans le dossier du projet — ou s'il a été créé avant un déplacement du dépôt — `python main.py` échoue à l'import de `ttkbootstrap` : recréez-le avec les commandes d'installation ci-dessus.

## Tests

```bash
python -m unittest discover -v                        # les 113 tests
python -m unittest tests.test_model                   # un module
python -m unittest tests.test_model.ZipExportTests.test_export_zip   # un seul test

coverage run -m unittest discover && coverage report
coverage html                                         # rapport détaillé dans htmlcov/
```

La couverture est de **99 %**, lignes et branches, sans aucune instruction non exécutée. Les tests du Modèle s'exécutent sans affichage ; ceux de la Vue et du Contrôleur construisent de vrais widgets et lancent réellement le thread de compression, la boucle d'événements étant animée par le test lui-même. Sur une machine sans écran, ces cas sont ignorés au lieu d'échouer.

La seule branche non couverte est l'import conditionnel de `tkinterdnd2` dans `mvc/window.py` : elle ne s'évalue qu'au chargement du module, et ne peut donc pas être exercée dans un environnement où la bibliothèque est installée. Le comportement de repli qui en dépend, lui, est testé.

## Structure du projet

```
main.py              Point d'entrée : journalisation, fenêtre, contrôleur, boucle
utils.py             Résolution des chemins, en mode script comme empaqueté
mvc/
  constants.py       Réglages par défaut, formats acceptés, libellés de fenêtre
  model.py           Données et compression (aucune dépendance à Tkinter)
  view.py            Widgets, jauge de progression et boîtes de dialogue
  controller.py      Orchestration, thread de traitement et file de progression
  window.py          Fabrique de fenêtre et glisser-déposer facultatif
tests/
  support.py         Outils communs : isolation, images de test, boucle d'événements
  test_model.py      Importation, compression, export, annulation, persistance
  test_view.py       États de l'interface et boîtes de dialogue
  test_controller.py Parcours complet, traitement en arrière-plan, garde-fous
  test_window.py     Fabrique de fenêtre et filtrage des dépôts
  test_utils.py      Chemins de lecture et d'écriture
  test_main.py       Câblage du démarrage
```

L'architecture sépare strictement le traitement de l'affichage : `model.py` n'importe ni Tkinter ni ttkbootstrap, ce qui rend la compression testable sans écran. La compression s'exécute dans un thread secondaire qui ne touche jamais aux widgets : il publie sa progression dans une `queue.Queue` que le Contrôleur relit depuis le thread principal via `after()`. Toute évolution doit respecter cette règle — Tkinter n'est pas thread-safe.

## Contributeurs

### Développeur

Conception, décisions et validation du produit :

- définition du besoin et des règles métier : compression par lots, profils de réglages, périmètre JPG/JPEG en entrée avec WEBP conservé en sortie ;
- choix d'ergonomie : jauge de progression plutôt qu'un simple pourcentage, bouton d'export se muant en bouton d'annulation, glisser-déposer sur la fenêtre ;
- choix techniques structurants : architecture MVC, migration vers ttkbootstrap, traitement en thread avec file de progression, tests en `unittest` plutôt qu'en `pytest`, empaquetage par `auto-py-to-exe`, compatibilité Windows et macOS exigée ;
- arbitrage des correctifs : résolution des collisions de noms retenue en priorité, correction de l'orientation EXIF reportée, confirmation avant suppression des originaux retirée au profit d'un export sans interruption ;
- recette de l'application et détection des anomalies.

### Agents de code

**Gemini** — refonte initiale de l'architecture en MVC, migration de CustomTkinter vers ttkbootstrap, implémentation des options avancées d'encodage et de la bascule « Stockage optimisé ».

**Claude Opus 5 via Claude Code (CLI)** — réalisation sous la direction du développeur :

- implémentation de la compression en arrière-plan, de la jauge de progression et de l'annulation ;
- ajout du glisser-déposer, avec repli propre lorsque `tkinterdnd2` est indisponible ;
- correction des anomalies de sécurité des données : écrasement silencieux des fichiers homonymes, original détruit lorsque la destination coïncidait avec le dossier source, statistiques faussées par les images en échec ;
- diagnostic de l'anomalie qui empêchait l'application de démarrer : `ttk.LabelFrame` n'existe plus sous ce nom en ttkbootstrap 1.18 ;
- rédaction des 113 tests et de la couverture à 99 % ;
- documentation : docstrings, commentaires et ce README.

Chaque modification a été relue et validée par le développeur avant intégration.

## Licence

GNU GENERAL PUBLIC LICENSE, Version 3, 29 June 2007
