# RDPWrap Watcher

Petite app Python portable qui surveille et met à jour automatiquement `rdpwrap.ini` depuis la source [sebaxakerhtc](https://github.com/sebaxakerhtc/rdpwrap.ini), puis réinstalle RDPWrap si le fichier a changé.

Conçue pour tourner directement dans le dossier RDPWrap d'une VM Windows (à côté de `rdpwrap.ini` et `RDPWInst.exe`).

---

## À quoi ça sert

Après une mise à jour Windows, RDPWrap a souvent besoin d'un `rdpwrap.ini` à jour. Ce watcher :

1. Télécharge le fichier source sur GitHub
2. Compare le **hash SHA256** avec le fichier local
3. Si différent → remplace `rdpwrap.ini` et réinstalle RDPWrap
4. Envoie une notification **ntfy** selon le résultat

---

## Prérequis

- **Windows** (VM serveur)
- **Python 3** installé (3.14+ sur ta VM)
- **Droits administrateur** pour le `setup` (RDPWInst + tâches planifiées)
- Accès réseau vers GitHub et vers ton serveur ntfy

---

## Installation

### 1. Copier les fichiers dans le dossier RDPWrap

Le dossier RDPWrap doit ressembler à ça :

```
C:\RDPWrap\                     ← exemple de chemin
├── rdpwrap.ini
├── RDPWInst.exe
├── rdpwrap-watcher.bat
├── requirements.txt
├── config.yaml.example
└── rdpwrap_watcher\
    ├── __init__.py
    ├── __main__.py
    ├── cli.py
    ├── config.py
    ├── ntfy.py
    ├── scheduler.py
    └── watcher.py
```

> **Important** : lance toujours les commandes **depuis ce dossier** (là où se trouvent `rdpwrap.ini` et `RDPWInst.exe`).

### 2. Installer les dépendances Python (une seule fois)

Ouvrir PowerShell ou CMD dans le dossier RDPWrap :

```powershell
pip install -r requirements.txt
```

Dépendances : `pyyaml`, `requests`.

### 3. Setup initial (en administrateur)

Clic droit sur PowerShell → **Exécuter en tant qu'administrateur**, puis :

```powershell
cd C:\RDPWrap
.\rdpwrap-watcher.bat setup
```

Le setup :
- crée `config.yaml` (si absent)
- génère `run-watcher.bat` (script lancé par le planificateur)
- installe **2 tâches planifiées Windows** :
  - **RDPWrapWatcher-Startup** → 5 min après chaque démarrage
  - **RDPWrapWatcher-Daily** → tous les jours à 03:00

---

## Commandes

Toutes les commandes passent par le `.bat` ou directement par Python :

```powershell
.\rdpwrap-watcher.bat <commande>
# ou
python -m rdpwrap_watcher <commande>
```

| Commande | Description |
|---|---|
| `setup` | Crée la config + installe les tâches planifiées |
| `run` | Vérification **immédiate** (one-shot) |
| `run --no-notify` | Idem, sans notification ntfy |
| `config-show` | Affiche la configuration actuelle |
| `config-set <clé> <valeur>` | Modifie un paramètre |
| `uninstall` | Supprime les tâches planifiées |

### Exemples

```powershell
# Vérification manuelle tout de suite
.\rdpwrap-watcher.bat run

# Voir la config
.\rdpwrap-watcher.bat config-show

# Changer l'heure du check quotidien (recrée les tâches)
.\rdpwrap-watcher.bat config-set schedule-time 04:30 --reinstall-tasks

# Changer le délai après démarrage Windows
.\rdpwrap-watcher.bat config-set startup-delay 10 --reinstall-tasks

# Changer l'URL source
.\rdpwrap-watcher.bat config-set source-url https://raw.githubusercontent.com/sebaxakerhtc/rdpwrap.ini/master/rdpwrap.ini

# Changer le serveur ntfy
.\rdpwrap-watcher.bat config-set ntfy-url http://192.168.1.131:8090/rdpwrap-watcher
.\rdpwrap-watcher.bat config-set ntfy-user admin
.\rdpwrap-watcher.bat config-set ntfy-password admin

# Désinstaller les tâches planifiées
.\rdpwrap-watcher.bat uninstall
```

### Clés disponibles pour `config-set`

| Clé CLI | Paramètre YAML | Description |
|---|---|---|
| `source-url` | `source_url` | URL raw du fichier ini distant |
| `schedule-time` | `schedule_time` | Heure du check quotidien (`HH:MM`) |
| `startup-delay` | `startup_delay_minutes` | Minutes après boot avant check |
| `reinstall-wait` | `reinstall_wait_seconds` | Pause entre désinstall et réinstall |
| `ntfy-url` | `ntfy.url` | URL du topic ntfy |
| `ntfy-user` | `ntfy.user` | Utilisateur ntfy |
| `ntfy-password` | `ntfy.password` | Mot de passe ntfy |

> Ajouter `--reinstall-tasks` après un changement d'horaire ou de délai boot pour mettre à jour les tâches planifiées.

---

## Configuration (`config.yaml`)

Fichier créé automatiquement au `setup`. Exemple :

```yaml
source_url: https://raw.githubusercontent.com/sebaxakerhtc/rdpwrap.ini/master/rdpwrap.ini
local_ini: rdpwrap.ini
rdpwinst: RDPWInst.exe
schedule_time: "03:00"
startup_delay_minutes: 5
reinstall_wait_seconds: 5
ntfy:
  url: http://192.168.1.131:8090/rdpwrap-watcher
  user: admin
  password: admin
task_names:
  startup: RDPWrapWatcher-Startup
  daily: RDPWrapWatcher-Daily
```

Tu peux éditer ce fichier à la main ou via `config-set` / `config-show`.

> **Note** : utilise toujours l'URL **raw** GitHub (`raw.githubusercontent.com/...`), pas l'URL `blob/` qui renvoie du HTML.

---

## Fonctionnement détaillé

À chaque exécution (manuelle ou planifiée) :

```
Télécharger ini distant
        ↓
Comparer SHA256 avec rdpwrap.ini local
        ↓
   Identique ? ──→ Notif ntfy (priorité medium) → Fin
        ↓ Non
Sauvegarder l'ancien fichier en mémoire
        ↓
Écrire le nouveau rdpwrap.ini
        ↓
RDPWInst.exe -u -k
        ↓
Attendre 5 secondes
        ↓
RDPWInst.exe -i
        ↓
   Échec ? ──→ Restaurer l'ancien ini → Notif ntfy (priorité max)
        ↓ OK
Notif ntfy (priorité high) → Fin
```

---

## Notifications ntfy

| Situation | Priorité | Signification |
|---|---|---|
| Tout OK, pas de changement | **medium** (3) | Rien à faire |
| Ini mis à jour + réinstall OK | **high** (4) | Action effectuée |
| Erreur (réseau, RDPWInst, etc.) | **max** (5) | Intervention nécessaire |

Topic par défaut : `http://192.168.1.131:8090/rdpwrap-watcher`

---

## Tâches planifiées Windows

Vérifiables dans **Planificateur de tâches** (`taskschd.msc`) :

| Nom | Déclencheur | Privilèges |
|---|---|---|
| `RDPWrapWatcher-Startup` | Au démarrage, +5 min | Élevés |
| `RDPWrapWatcher-Daily` | Quotidien à 03:00 | Élevés |

Les deux tâches exécutent `run-watcher.bat`, généré automatiquement au setup.

Pour supprimer : `.\rdpwrap-watcher.bat uninstall`

---

## Dépannage

### Le setup échoue sur les tâches planifiées
→ Relancer PowerShell **en administrateur**.

### `RDPWInst.exe introuvable`
→ Vérifier que tu es bien dans le dossier RDPWrap et que `RDPWInst.exe` est présent.

### Pas de notification ntfy
→ Vérifier que le serveur ntfy est joignable depuis la VM (`http://192.168.1.131:8090`).
→ Tester manuellement : `.\rdpwrap-watcher.bat run`

### Forcer une vérification sans notif (debug)
```powershell
python -m rdpwrap_watcher run --no-notify
```

### Spécifier un autre dossier RDPWrap
```powershell
python -m rdpwrap_watcher run --dir "D:\Chemin\Vers\RDPWrap"
```

### Voir l'historique des exécutions planifiées
→ Planificateur de tâches → bibliothèque → clic droit sur la tâche → **Historique**.

---

## Fichiers du projet

| Fichier | Rôle |
|---|---|
| `rdpwrap-watcher.bat` | Lanceur principal (double-clic ou CLI) |
| `rdpwrap_watcher/` | Code Python du watcher |
| `config.yaml` | Config active (créée au setup) |
| `config.yaml.example` | Modèle de référence |
| `run-watcher.bat` | Script généré pour le planificateur |
| `requirements.txt` | Dépendances pip |

---

## Rappel rapide (version TL;DR)

```powershell
# Première fois
pip install -r requirements.txt
.\rdpwrap-watcher.bat setup          # en admin

# Check manuel
.\rdpwrap-watcher.bat run

# Voir / modifier la config
.\rdpwrap-watcher.bat config-show
.\rdpwrap-watcher.bat config-set schedule-time 03:00 --reinstall-tasks

# Tout retirer
.\rdpwrap-watcher.bat uninstall
```
