"""
Tests du Modèle : importation, validation des formats, compression,
exportation, progression, annulation et persistance des réglages.

Le Modèle n'importe ni Tkinter ni ttkbootstrap : ces tests s'exécutent sans
affichage graphique.
"""
import os
import json
import pathlib
import threading
import unittest
from unittest import mock
from zipfile import ZipFile

from PIL import Image

from tests.support import IsolatedTestCase, ProgressRecorder, default_options, make_png
from mvc.model import ApplicationModel, configure_logging


class ModelTestCase(IsolatedTestCase):
    """Cas de base fournissant un Modèle configuré sur les dossiers du test."""

    def setUp(self) -> None:
        super().setUp()
        self.model = ApplicationModel()
        self.model.write_config(str(self.export_dir))
        # Relâche les descripteurs de fichiers encore ouverts en fin de test
        self.addCleanup(self.model.reset_data)

    def load(self, *paths) -> tuple:
        """Charge des chemins dans le Modèle et retourne le résultat brut."""
        return self.model.load_images([str(p) for p in paths])


# ---------------------------------------------------------------------------
# Importation et validation des fichiers
# ---------------------------------------------------------------------------

class LoadImagesTests(ModelTestCase):
    """Chargement des fichiers et rejet de ce qui n'est pas un JPEG."""

    def test_accepte_les_jpeg(self):
        """Des JPEG valides sont chargés et leurs métadonnées renseignées."""
        first = self.make_jpeg("a.jpg")
        second = self.make_jpeg("b.jpeg")

        loaded, rejected = self.load(first, second)

        self.assertEqual(loaded, 2)
        self.assertEqual(rejected, [])
        self.assertEqual(len(self.model.data), 2)
        self.assertEqual(self.model.data[1]["old_name"], "a")
        self.assertEqual(self.model.data[1]["old_suffix"], ".jpg")
        self.assertEqual(self.model.data[1]["old_size"], os.path.getsize(first))

    def test_rejette_un_png_renomme(self):
        """
        Un PNG portant l'extension .jpg est écarté.

        C'est le cas que le filtre de la boîte de dialogue laisse passer : seule
        la lecture de l'en-tête par Pillow permet de le détecter.
        """
        piege = make_png(self.source_dir, "piege.jpg")
        valide = self.make_jpeg("vraie.jpg")

        loaded, rejected = self.load(piege, valide)

        self.assertEqual(loaded, 1)
        self.assertEqual(rejected, ["piege.jpg"])
        self.assertEqual(self.model.data[1]["old_name"], "vraie")

    def test_rejette_un_fichier_illisible(self):
        """Un fichier inexistant est rapporté comme rejeté, sans exception."""
        loaded, rejected = self.load(self.source_dir / "fantome.jpg")

        self.assertEqual(loaded, 0)
        self.assertEqual(rejected, ["fantome.jpg"])

    def test_liste_vide(self):
        """Une sélection vide ne charge rien et ne rejette rien."""
        loaded, rejected = self.model.load_images([])

        self.assertEqual(loaded, 0)
        self.assertEqual(rejected, [])

    def test_remplace_la_selection_precedente(self):
        """Une nouvelle importation remplace la précédente au lieu de s'y ajouter."""
        self.load(self.make_jpeg("a.jpg"))
        loaded, _ = self.load(self.make_jpeg("b.jpg"))

        self.assertEqual(loaded, 1)
        self.assertEqual(len(self.model.data), 1)
        self.assertEqual(self.model.data[1]["old_name"], "b")

    def test_reset_data_ferme_les_images(self):
        """La réinitialisation vide les données et relâche les descripteurs."""
        self.load(self.make_jpeg("a.jpg"))
        image_obj = self.model.data[1]["image_obj"]

        self.model.reset_data()

        self.assertEqual(self.model.data, {})
        self.assertIsNone(getattr(image_obj, "fp", None))

    def test_reset_data_tolere_une_fermeture_en_erreur(self):
        """Un objet image récalcitrant n'empêche pas la réinitialisation."""
        self.load(self.make_jpeg("a.jpg"))
        recalcitrant = mock.Mock()
        recalcitrant.close.side_effect = OSError("descripteur invalide")
        self.model.data[1]["image_obj"] = recalcitrant

        self.model.reset_data()

        self.assertEqual(self.model.data, {})
        recalcitrant.close.assert_called_once()


# ---------------------------------------------------------------------------
# Exportation nominale
# ---------------------------------------------------------------------------

class ExportTests(ModelTestCase):
    """Production des fichiers compressés et statistiques associées."""

    def test_cree_les_fichiers_et_les_statistiques(self):
        """L'export produit les fichiers attendus et des statistiques cohérentes."""
        self.load(self.make_jpeg("a.jpg"), self.make_jpeg("b.jpg"))

        success, stats = self.model.process_and_export(default_options(quality=30))

        self.assertEqual(success, 2)
        self.assertTrue((self.export_dir / "a.jpg").exists())
        self.assertTrue((self.export_dir / "b.jpg").exists())
        self.assertEqual(stats["total_images"], 2)
        self.assertEqual(stats["failures"], [])
        self.assertFalse(stats["cancelled"])
        self.assertEqual(stats["export_dir"], str(self.export_dir))
        # Une qualité de 30 doit réduire le poids d'images enregistrées en qualité 95
        self.assertLess(stats["total_new_mo"], stats["total_old_mo"])
        self.assertGreater(stats["gain_percent"], 0)

    def test_applique_le_suffixe(self):
        """L'option de suffixe se reflète dans le nom du fichier produit."""
        self.load(self.make_jpeg("a.jpg"))

        self.model.process_and_export(default_options(add_suffixe=True))

        self.assertTrue((self.export_dir / "a_compressée.jpg").exists())

    def test_redimensionne(self):
        """Le facteur de redimensionnement est appliqué aux dimensions de sortie."""
        self.load(self.make_jpeg("a.jpg", size=(200, 100)))

        self.model.process_and_export(default_options(resize_factor=0.5))

        with Image.open(self.export_dir / "a.jpg") as exported:
            self.assertEqual(exported.size, (100, 50))

    def test_facteur_de_redimensionnement_nul_conserve_la_taille(self):
        """Un facteur à zéro est ignoré plutôt que de produire une image vide."""
        self.load(self.make_jpeg("a.jpg", size=(120, 90)))

        success, _ = self.model.process_and_export(default_options(resize_factor=0.0))

        self.assertEqual(success, 1)
        with Image.open(self.export_dir / "a.jpg") as exported:
            self.assertEqual(exported.size, (120, 90))

    def test_redimensionnement_trop_petit_est_ignore(self):
        """Un facteur qui annulerait une dimension laisse l'image intacte."""
        self.load(self.make_jpeg("a.jpg", size=(10, 10)))

        success, _ = self.model.process_and_export(default_options(resize_factor=0.01))

        self.assertEqual(success, 1)
        with Image.open(self.export_dir / "a.jpg") as exported:
            self.assertEqual(exported.size, (10, 10))

    def test_export_en_webp(self):
        """Le format WEBP produit bien un fichier WEBP."""
        self.load(self.make_jpeg("a.jpg"))

        success, _ = self.model.process_and_export(default_options(output_format='WEBP'))

        self.assertEqual(success, 1)
        with Image.open(self.export_dir / "a.webp") as exported:
            self.assertEqual(exported.format, "WEBP")

    def test_options_d_encodage_avancees(self):
        """Encodage optimisé, progressif et purge des métadonnées s'appliquent ensemble."""
        self.load(self.make_jpeg("a.jpg"))

        success, _ = self.model.process_and_export(default_options(
            optimized_encoding=True, progressive_loading=True, strip_metadata=True,
        ))

        self.assertEqual(success, 1)
        with Image.open(self.export_dir / "a.jpg") as exported:
            self.assertTrue(exported.info.get("progressive"))

    def test_conversion_des_images_avec_transparence(self):
        """
        Une image RGBA est convertie en RGB, seul mode accepté par le JPEG.

        Le cas se présente lorsque le format de sortie est JPEG alors que
        l'image en mémoire porte une couche alpha ; sans conversion, Pillow
        refuserait l'enregistrement.
        """
        source = self.source_dir / "transparent.png"
        Image.new("RGBA", (60, 60), (10, 20, 30, 128)).save(source, format="PNG")

        # L'entrée est alimentée directement : la validation d'importation
        # écarterait ce PNG, alors que le test porte sur la conversion de mode.
        self.model.data[1] = {
            "old_path": str(source),
            "old_name": "transparent",
            "old_suffix": ".png",
            "old_size": source.stat().st_size,
            "new_size": 0,
            "image_obj": Image.open(source),
        }

        success, _ = self.model.process_and_export(default_options())

        self.assertEqual(success, 1)
        with Image.open(self.export_dir / "transparent.jpg") as exported:
            self.assertEqual(exported.mode, "RGB")

    def test_reouvre_une_image_fermee(self):
        """Une image dont le descripteur a été refermé est rouverte à la volée."""
        self.load(self.make_jpeg("a.jpg"))
        self.model.data[1]["image_obj"].close()

        success, _ = self.model.process_and_export(default_options())

        self.assertEqual(success, 1)
        self.assertTrue((self.export_dir / "a.jpg").exists())

    def test_format_de_sortie_non_supporte(self):
        """Un format inconnu est refusé avant tout traitement."""
        self.load(self.make_jpeg("a.jpg"))

        success, stats = self.model.process_and_export(default_options(output_format='GIF'))

        self.assertEqual(success, 0)
        self.assertIn("non supporté", stats["error_msg"])

    def test_export_sans_donnees(self):
        """Exporter sans image chargée renvoie une erreur explicite."""
        success, stats = self.model.process_and_export(default_options())

        self.assertEqual(success, 0)
        self.assertIn("error_msg", stats)

    def test_export_vers_un_dossier_inexistant(self):
        """Un chemin d'export invalide est détecté avant d'ouvrir la moindre image."""
        self.load(self.make_jpeg("a.jpg"))
        self.model.export_path = str(self.workdir / "dossier_absent")

        success, stats = self.model.process_and_export(default_options())

        self.assertEqual(success, 0)
        self.assertIn("error_msg", stats)

    def test_options_par_defaut_si_absentes(self):
        """Un dictionnaire d'options vide retombe sur les valeurs par défaut."""
        self.load(self.make_jpeg("a.jpg"))

        success, _ = self.model.process_and_export({})

        self.assertEqual(success, 1)
        self.assertTrue((self.export_dir / "a.jpg").exists())


# ---------------------------------------------------------------------------
# Collisions de noms
# ---------------------------------------------------------------------------

class NameCollisionTests(ModelTestCase):
    """Aucun fichier ne doit jamais être écrasé silencieusement."""

    def test_collision_entre_deux_sources(self):
        """Deux fichiers homonymes venant de dossiers différents cohabitent."""
        premier = self.make_jpeg("photo.jpg", directory=self.workdir / "dossier_a")
        second = self.make_jpeg("photo.jpg", size=(80, 80), directory=self.workdir / "dossier_b")
        self.load(premier, second)

        success, _ = self.model.process_and_export(default_options())

        self.assertEqual(success, 2)
        self.assertTrue((self.export_dir / "photo.jpg").exists())
        self.assertTrue((self.export_dir / "photo_1.jpg").exists())

    def test_n_ecrase_jamais_un_fichier_existant(self):
        """Un fichier déjà présent dans la destination est préservé."""
        existant = self.export_dir / "a.jpg"
        existant.write_bytes(b"contenu original a preserver")
        self.load(self.make_jpeg("a.jpg"))

        success, _ = self.model.process_and_export(default_options())

        self.assertEqual(success, 1)
        self.assertEqual(existant.read_bytes(), b"contenu original a preserver")
        self.assertTrue((self.export_dir / "a_1.jpg").exists())

    def test_collisions_multiples_sont_numerotees(self):
        """Trois sources homonymes produisent photo.jpg, photo_1.jpg, photo_2.jpg."""
        sources = [
            self.make_jpeg("photo.jpg", directory=self.workdir / f"dossier_{index}")
            for index in range(3)
        ]
        self.load(*sources)

        success, _ = self.model.process_and_export(default_options())

        self.assertEqual(success, 3)
        self.assertEqual(
            {p.name for p in self.export_dir.glob("*.jpg")},
            {"photo.jpg", "photo_1.jpg", "photo_2.jpg"},
        )

    def test_allocation_insensible_a_la_casse(self):
        """
        'Photo.jpg' et 'photo.jpg' sont considérés comme un seul nom.

        Windows et macOS étant par défaut insensibles à la casse, les traiter
        séparément conduirait à un écrasement.
        """
        reserved = set()
        premier = ApplicationModel._allocate_export_name(self.export_dir, "Photo", ".jpg", reserved)
        second = ApplicationModel._allocate_export_name(self.export_dir, "photo", ".jpg", reserved)

        self.assertEqual(premier, "Photo.jpg")
        self.assertEqual(second, "photo_1.jpg")


# ---------------------------------------------------------------------------
# Progression et annulation
# ---------------------------------------------------------------------------

class ProgressAndCancelTests(ModelTestCase):
    """Rappel de progression et interruption du traitement."""

    def test_progression_signalee_pour_chaque_image(self):
        """Le rappel est invoqué une fois par image, dans l'ordre."""
        self.load(self.make_jpeg("a.jpg"), self.make_jpeg("b.jpg"), self.make_jpeg("c.jpg"))
        recorder = ProgressRecorder()

        self.model.process_and_export(default_options(), progress_callback=recorder)

        self.assertEqual([done for done, _, _ in recorder.calls], [1, 2, 3])
        self.assertTrue(all(total == 3 for _, total, _ in recorder.calls))
        self.assertEqual([name for _, _, name in recorder.calls], ["a.jpg", "b.jpg", "c.jpg"])

    def test_progression_signalee_meme_en_cas_d_echec(self):
        """Une image en échec fait tout de même avancer la progression."""
        self.load(self.make_jpeg("a.jpg"), self.make_jpeg("b.jpg"))
        recorder = ProgressRecorder()

        with self._save_failing_on("a."):
            success, stats = self.model.process_and_export(
                default_options(), progress_callback=recorder
            )

        self.assertEqual(success, 1)
        self.assertEqual(len(recorder.calls), 2)
        self.assertEqual(len(stats["failures"]), 1)
        self.assertEqual(stats["failures"][0][0], "a.jpg")

    def test_annulation_interrompt_le_traitement(self):
        """L'événement d'annulation stoppe la boucle à l'image suivante."""
        self.load(*[self.make_jpeg(f"img_{i}.jpg") for i in range(5)])
        cancel_event = threading.Event()

        def annuler_apres_deux(done, total, filename):
            if done == 2:
                cancel_event.set()

        success, stats = self.model.process_and_export(
            default_options(), progress_callback=annuler_apres_deux, cancel_event=cancel_event
        )

        self.assertEqual(success, 2)
        self.assertTrue(stats["cancelled"])
        self.assertEqual(len(list(self.export_dir.glob("*.jpg"))), 2)

    def test_annulation_immediate(self):
        """Un événement déjà levé empêche tout traitement."""
        self.load(self.make_jpeg("a.jpg"))
        cancel_event = threading.Event()
        cancel_event.set()

        success, stats = self.model.process_and_export(
            default_options(), cancel_event=cancel_event
        )

        self.assertEqual(success, 0)
        self.assertTrue(stats["cancelled"])
        self.assertEqual(list(self.export_dir.glob("*.jpg")), [])

    def _save_failing_on(self, marker: str):
        """
        Fait échouer `Image.save` pour les fichiers dont le nom contient un motif.

        Args:
            marker: Le fragment de nom de fichier déclenchant l'échec simulé.

        Returns:
            Un gestionnaire de contexte appliquant la substitution.
        """
        original_save = Image.Image.save

        def save_qui_echoue(image_self, fp, *args, **kwargs):
            if marker in str(fp):
                raise OSError("échec simulé")
            return original_save(image_self, fp, *args, **kwargs)

        return mock.patch.object(Image.Image, "save", save_qui_echoue)


# ---------------------------------------------------------------------------
# Statistiques et rapport d'échecs
# ---------------------------------------------------------------------------

class StatisticsTests(ModelTestCase):
    """Fiabilité des chiffres présentés à l'utilisateur."""

    def test_les_statistiques_ignorent_les_images_en_echec(self):
        """
        Le poids d'origine d'une image en échec n'est pas comptabilisé.

        Sans cela, le gain affiché serait artificiellement gonflé par des
        fichiers qui n'ont jamais été écrits.
        """
        grosse = self.make_jpeg("grosse.jpg", size=(600, 600))
        petite = self.make_jpeg("petite.jpg", size=(60, 60))
        self.load(grosse, petite)

        original_save = Image.Image.save

        def save_qui_echoue(image_self, fp, *args, **kwargs):
            if "grosse" in str(fp):
                raise OSError("échec simulé")
            return original_save(image_self, fp, *args, **kwargs)

        with mock.patch.object(Image.Image, "save", save_qui_echoue):
            success, stats = self.model.process_and_export(default_options())

        self.assertEqual(success, 1)
        self.assertEqual(
            stats["total_old_mo"], round(os.path.getsize(petite) / 1000000, 2)
        )

    def test_le_fichier_partiel_est_nettoye_apres_une_erreur(self):
        """Un fichier écrit à moitié avant l'erreur ne reste pas dans la destination."""
        self.load(self.make_jpeg("a.jpg"))

        def save_qui_ecrit_puis_echoue(image_self, fp, *args, **kwargs):
            pathlib.Path(fp).write_bytes(b"donnees partielles")
            raise OSError("interruption simulée")

        with mock.patch.object(Image.Image, "save", save_qui_ecrit_puis_echoue):
            success, stats = self.model.process_and_export(default_options())

        self.assertEqual(success, 0)
        self.assertEqual(len(stats["failures"]), 1)
        self.assertEqual(list(self.export_dir.glob("*.jpg")), [])

    def test_echec_du_nettoyage_est_journalise(self):
        """Si le fichier partiel ne peut être effacé, l'erreur est tracée sans planter."""
        self.load(self.make_jpeg("a.jpg"))

        def save_qui_ecrit_puis_echoue(image_self, fp, *args, **kwargs):
            pathlib.Path(fp).write_bytes(b"partiel")
            raise OSError("interruption simulée")

        with mock.patch.object(Image.Image, "save", save_qui_ecrit_puis_echoue), \
             mock.patch("mvc.model.os.remove", side_effect=OSError("verrouillé")):
            success, stats = self.model.process_and_export(default_options())

        self.assertEqual(success, 0)
        self.assertEqual(len(stats["failures"]), 1)

    def test_statistiques_sans_aucune_reussite(self):
        """Un échec total renvoie des statistiques nulles mais complètes."""
        self.load(self.make_jpeg("a.jpg"))

        with mock.patch.object(Image.Image, "save", side_effect=OSError("échec")):
            success, stats = self.model.process_and_export(default_options())

        self.assertEqual(success, 0)
        self.assertEqual(stats["total_old_mo"], 0)
        self.assertEqual(stats["gain_percent"], 0)
        self.assertEqual(len(stats["failures"]), 1)


# ---------------------------------------------------------------------------
# Archive ZIP
# ---------------------------------------------------------------------------

class ZipExportTests(ModelTestCase):
    """Regroupement des images dans une archive."""

    def test_export_zip(self):
        """L'export ZIP regroupe les images et ne laisse aucun fichier isolé."""
        self.load(self.make_jpeg("a.jpg"), self.make_jpeg("b.jpg"))

        success, stats = self.model.process_and_export(default_options(use_zip=True))

        self.assertEqual(success, 2)
        archives = list(self.export_dir.glob("*.zip"))
        self.assertEqual(len(archives), 1)
        # Les fichiers intermédiaires ont été retirés du disque
        self.assertEqual(list(self.export_dir.glob("*.jpg")), [])

        with ZipFile(archives[0]) as archive:
            self.assertEqual(sorted(archive.namelist()), ["a.jpg", "b.jpg"])

        # La taille finale rapportée est celle de l'archive
        self.assertEqual(
            stats["total_new_mo"], round(os.path.getsize(archives[0]) / 1000000, 2)
        )
        self.assertEqual(stats["zip_path"], str(archives[0]))

    def test_archive_disparue_avant_le_calcul_des_tailles(self):
        """Si l'archive n'est plus lisible, les tailles individuelles sont conservées."""
        self.load(self.make_jpeg("a.jpg"))

        original_exists = os.path.exists

        def zip_introuvable(path):
            return False if str(path).endswith(".zip") else original_exists(path)

        with mock.patch("mvc.model.os.path.exists", zip_introuvable):
            success, stats = self.model.process_and_export(default_options(use_zip=True))

        self.assertEqual(success, 1)
        self.assertGreater(stats["total_new_mo"], 0)

    def test_echec_de_creation_du_zip(self):
        """Une archive impossible à créer interrompt l'export avec un message clair."""
        self.load(self.make_jpeg("a.jpg"))

        with mock.patch("mvc.model.ZipFile", side_effect=OSError("disque protégé")):
            success, stats = self.model.process_and_export(default_options(use_zip=True))

        self.assertEqual(success, 0)
        self.assertIn("Erreur ZIP", stats["error_msg"])
        self.assertIn("zip_path", stats)


# ---------------------------------------------------------------------------
# Suppression des originaux
# ---------------------------------------------------------------------------

class DeleteOriginalsTests(ModelTestCase):
    """Suppression des sources après compression."""

    def test_suppression_des_originaux(self):
        """Les fichiers sources sont supprimés une fois la compression réussie."""
        source = self.make_jpeg("a.jpg")
        self.load(source)

        success, _ = self.model.process_and_export(default_options(delete_originals=True))

        self.assertEqual(success, 1)
        self.assertFalse(source.exists())
        self.assertTrue((self.export_dir / "a.jpg").exists())

    def test_suppression_apres_redimensionnement(self):
        """
        Le descripteur de l'image dérivée est refermé avant la suppression.

        Sous Windows, `os.remove` échoue tant qu'un fichier reste ouvert.
        """
        source = self.make_jpeg("a.jpg", size=(200, 200))
        self.load(source)

        success, _ = self.model.process_and_export(
            default_options(delete_originals=True, resize_factor=0.5)
        )

        self.assertEqual(success, 1)
        self.assertFalse(source.exists())

    def test_suppression_dans_le_dossier_source_preserve_la_compression(self):
        """
        Exporter dans le dossier source avec suppression ne détruit pas l'image.

        C'était le scénario destructeur : l'original était écrasé par sa version
        compressée, puis supprimé. La résolution de collision garantit désormais
        que la version compressée occupe un nom distinct.
        """
        source = self.make_jpeg("a.jpg")
        self.model.write_config(str(self.source_dir))
        self.load(source)

        success, _ = self.model.process_and_export(default_options(delete_originals=True))

        self.assertEqual(success, 1)
        self.assertFalse(source.exists())                          # original supprimé
        self.assertTrue((self.source_dir / "a_1.jpg").exists())    # version compressée conservée

    def test_suppression_apres_un_echec_conserve_l_original(self):
        """
        Une image qui n'a pas pu être compressée n'est jamais supprimée.

        La suppression n'intervient qu'après un enregistrement réussi : c'est ce
        qui protège les fichiers en cas d'erreur d'écriture.
        """
        source = self.make_jpeg("a.jpg")
        self.load(source)

        with mock.patch.object(Image.Image, "save", side_effect=OSError("disque plein")):
            success, stats = self.model.process_and_export(
                default_options(delete_originals=True)
            )

        self.assertEqual(success, 0)
        self.assertEqual(len(stats["failures"]), 1)
        self.assertTrue(source.exists())


# ---------------------------------------------------------------------------
# Persistance du chemin d'exportation
# ---------------------------------------------------------------------------

class ConfigPersistenceTests(IsolatedTestCase):
    """Lecture et écriture du dossier d'exportation."""

    def test_persistance_du_chemin_export(self):
        """Le chemin écrit par une instance est relu par la suivante."""
        premier = ApplicationModel()
        premier.write_config(str(self.export_dir))

        config_file = self.workdir / ApplicationModel.CONFIG_FILE
        self.assertEqual(
            json.loads(config_file.read_text(encoding="utf-8")), str(self.export_dir)
        )

        second = ApplicationModel()
        self.assertEqual(second.export_path, str(self.export_dir))

    def test_chemin_sauvegarde_invalide_retombe_sur_le_dossier_personnel(self):
        """Un dossier sauvegardé qui n'existe plus est remplacé par le dossier personnel."""
        config_file = self.workdir / ApplicationModel.CONFIG_FILE
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps(str(self.workdir / "dossier_supprime")), encoding="utf-8"
        )

        model = ApplicationModel()

        self.assertEqual(model.export_path, str(pathlib.Path.home()))

    def test_config_corrompue_est_ignoree(self):
        """Un JSON invalide n'empêche pas le démarrage."""
        config_file = self.workdir / ApplicationModel.CONFIG_FILE
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("{ceci n'est pas du json", encoding="utf-8")

        model = ApplicationModel()

        self.assertEqual(model.export_path, str(pathlib.Path.home()))

    def test_config_contenant_autre_chose_qu_un_chemin(self):
        """Un JSON valide mais du mauvais type est traité comme absent."""
        config_file = self.workdir / ApplicationModel.CONFIG_FILE
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"chemin": "/tmp"}), encoding="utf-8")

        model = ApplicationModel()

        self.assertEqual(model.export_path, str(pathlib.Path.home()))

    def test_echec_d_ecriture_est_journalise(self):
        """Une écriture impossible est tracée sans interrompre l'application."""
        model = ApplicationModel()

        with mock.patch("mvc.model.io.open", side_effect=OSError("lecture seule")):
            model.write_config(str(self.export_dir))

        # Le chemin interne n'a pas été modifié par l'écriture ratée
        self.assertNotEqual(model.export_path, str(self.export_dir))


# ---------------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------------

class LoggingTests(IsolatedTestCase):
    """Installation différée du fichier de journal."""

    def test_configure_logging_cree_le_fichier(self):
        """L'appel explicite crée le répertoire de journalisation."""
        with mock.patch("mvc.model.logging.basicConfig") as basic_config:
            configure_logging()

        self.assertTrue((self.workdir / "logs").is_dir())
        basic_config.assert_called_once()

    def test_import_du_modele_sans_effet_de_bord(self):
        """Instancier le Modèle ne crée aucun répertoire de journalisation."""
        ApplicationModel()

        self.assertFalse((self.workdir / "logs").exists())


if __name__ == '__main__':
    unittest.main()
