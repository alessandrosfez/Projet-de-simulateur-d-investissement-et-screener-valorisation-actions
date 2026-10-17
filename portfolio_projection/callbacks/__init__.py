"""
Enregistrement de tous les callbacks Dash, un module par onglet plus un module commun. Importer
ce paquet (voir app.py) suffit à les enregistrer sur l'instance `app` partagée
(app_instance.py) : les fonctions des sous-modules ne sont pas appelées directement ailleurs.

Découpé par onglet plutôt qu'en un seul fichier de plus de 1 500 lignes : chaque onglet a ses
propres sorties, et aucun sous-module n'utilise de fonction d'un autre.
"""
from . import par_indice, portefeuille, portefeuille_reel, shared, validation  # noqa: F401
