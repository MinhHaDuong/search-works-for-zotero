# Français. La référence est locale/en/sdt-pack-sitter.ftl : tout identifiant
# absent d'ici retombe sur l'anglais sans lever d'exception (ticket 0692).
#
# L'unité de travail est UNE PIÈCE ATTACHÉE, jamais la référence qui la porte.
# L'interface française de Zotero traduit *item* par « document » : aucun texte
# ici ne peut donc dire document, élément ni pièce jointe — on dit fichier. Le
# mot « pack » est le nom interne de l'artefact et ne s'affiche nulle part.

## Le bouton de la barre d'outils, et l'infobulle qu'il porte

index = Index
index-coverage = Index { $percent } %
scope-one = Bibliothèque : { $names }
scope-few = Bibliothèques : { $names }
scope-many = Toutes les bibliothèques ({ $count })

# Sensible au pluriel : le nombre fait tout le sens de cette phrase. En français
# zéro est au singulier, ce que la règle de pluriel de la locale décide seule.
files-indexed = { $count ->
        [one] { $count } fichier indexé
       *[other] { $count } fichiers indexés
    }

## Chaque phase qu'un lecteur peut rencontrer au survol, dans ses mots

phase-census = Recensement
phase-extracting = Indexation en cours
phase-error = Erreur
phase-disabled = Désactivé
phase-native-worker-busy = En attente : indexation native en cours
phase-cpu-busy = En pause : processeur occupé
phase-low-memory = En pause : mémoire insuffisante
phase-low-disk = En pause : espace disque insuffisant
phase-storage-unavailable = En pause : stockage indisponible
phase-resources-unavailable = En pause : ressources système illisibles
phase-launch-declined = Non lancé : désactiver puis réactiver l’extension

## Le cadre de la fenêtre d'état

dialog-title = Assistant d’indexation
section-global = Progression globale — bibliothèque
section-active = Indexation en cours
details-title = Détails
fulltext-title = Index de recherche textuelle
fulltext-body = Index de recherche textuelle de Zotero (distinct de l’index préparé par l’assistant) :
fulltext-unavailable = Statistiques indisponibles : { $error }
tech-title = Diagnostics techniques

## Couche 1 : la progression, ce qui est en cours, et la fin attendue

files-indexed-of = Fichiers indexés : { $current } / { $total }
files-indexed-count = Fichiers indexés : { $current }
global-estimate = Fin estimée vers { $median } (entre { $low } et { $high })
active-none = Aucune indexation en cours
active-file = Indexation : { $file } — { $progress } % — { $elapsed } écoulées
active-finalising = Finalisation…
active-references = Analyse des références…
active-estimate = Durée estimée : { $median } (entre { $low } et { $high })

# Sensible au pluriel, la seconde et dernière.
files-failed = { $count ->
        [one] { $count } fichier n’a pas pu être indexé
       *[other] { $count } fichiers n’ont pas pu être indexés
    }

## Couche 2 : les décomptes, et l'ajustement sur lequel reposent les estimations

observations-waiting = Durées observées : { $count } (3 nécessaires avant toute estimation)
observations = Durées observées : { $count }
observations-basis = Durées observées : { $count } — base de calcul : { $basis }
basis-pages = par page
basis-bytes = par octet
diagnostics-phase = État : { $phase }
diagnostics-census = Recensement : { $scanned } / { $total }
diagnostics-count = { $status } : { $count }
diagnostics-completed = Créés cette session : { $count }
diagnostics-failed = N’ont pas pu être indexés (dernier recensement) : { $count }
diagnostics-error = Erreur : { $error }
cache-not-saved = Cache non enregistré : { $error }

## Couche 3 : ce qu'un rapport de bogue demande et qu'un lecteur ne lit jamais

debug-label = Consigner chaque étape dans la sortie de débogage de Zotero
journal-copy = Copier le journal
journal-copied = Journal copié dans le presse-papiers.
journal-copy-failed = Copie impossible : presse-papiers indisponible.
journal-unreadable = Journal illisible : { $error }
environment-version = Version de l’extension : { $version }
environment-zotero = Zotero : { $version } (compatibilité déclarée { $min } – { $max })
environment-native = Format natif : version { $format }, schéma { $schema }
environment-extractors = Extracteurs natifs : { $extractors }
environment-root = Installée dans : { $root }
admission-none = Aucune mesure de ressources depuis le démarrage.
admission-age = Dernière mesure il y a { $age } — une lecture par admission, aucune tant que la bibliothèque est à jour
admission-memory = Mémoire disponible : { $available } (seuil { $threshold })
admission-load = Charge processeur : { $load } sur { $cpus } cœurs
admission-disk = Espace disque : { $available } (seuil { $threshold })

## Les quantités, et la façon de nommer un fichier

gibibytes = { $value } Gio
unknown-value = ?
unit-seconds = { $count } s
unit-minutes = { $count } min
unit-hours-minutes = { $hours } h { $minutes } min
unit-minutes-seconds = { $minutes } min { $seconds } s
file-unknown = fichier inconnu
file-number = fichier n° { $id }
settle-failed = Échec de « { $file } » : { $error }
resources-read = Lecture des ressources : { $error }

## L'invite de lancement, dont le corps est ces quatre messages, dans l'ordre

launch-title = Assistant d’indexation — expérimental
launch-question = Indexer toute la bibliothèque cette nuit ?
launch-conditions = Un fichier à la fois, avec au moins 4 Gio de RAM disponible et 8 Gio de disque libre. Les PDF et les préférences de l’index de recherche textuelle restent inchangés.
launch-worker = Le worker partagé ne peut être interrompu ni recevoir une priorité système indépendante. Un gros fichier peut retarder un travail natif arrivé ensuite. Les seuils ne plafonnent pas sa consommation.
launch-disable = Désactiver l’extension arrête les admissions ; le fichier en cours finit. Les erreurs restent propres à la session. Un cache local jetable conserve les vérifications et durées ; il ne contient ni texte ni tâche active.
