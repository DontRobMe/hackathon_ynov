---
tags: [lab, reseau, firewall, dnat, sophos, ollama, hyperv, windows-server, streamlit, https, letsencrypt, win-acme, ovh, cloudflared]
author: Durand Hippolyte (M1 Infra)
date: 2026-07-01
status: fonctionnel
version: Final
---

# 🚀 Lab Complet : Ollama Phi-3 + Interface Web via Double DNAT + HTTPS (Let's Encrypt)

**Auteur:** Durand Hippolyte, M1 Infra

## 🔗 Accès à l'application

| | |
|---|---|
| **URL** | `https://hackaton-ia.nexa-cloud.fr:8501` |
| **Modèle** | `phi3-financial:latest` |
| **Auth** | aucune (accès direct) |
| **Backend** | Ollama (localhost:8000 sur la VM) |

> Cadenas vert (cert Let's Encrypt valide). Accès **par le domaine uniquement** (pas l'IP). Sur la page: badge 🟢 = serveur joignable, puis chatter directement.

## Vue d'ensemble

Déploiement complet d'une instance **Ollama** + **interface web Streamlit** sur **Windows Server Hyper-V**, derrière un **double DNAT** (Sophos FW1 → FW2). L'architecture a évolué en 3 étapes: tunnel Cloudflare pour débloquer les devs → app centralisée sur la VM (Ollama en localhost) → **HTTPS sur nom de domaine** (`hackaton-ia.nexa-cloud.fr`, cert Let's Encrypt), tunnel Cloudflare retiré.

**Statut:** ✅ Fonctionnel, app servie en `https://hackaton-ia.nexa-cloud.fr:8501` (cadenas vert), Ollama en localhost.

> Voir [Évolution de l'architecture (3 étapes)](#🔀-évolution-de-larchitecture-3-étapes) pour le détail des flux à chaque étape.

---

## 📑 Sommaire

- [Phase 0 : Déploiement VM Windows Server](#🔧-phase-0--déploiement-vm-windows-server)
- [Phase 1 : Configuration Réseau (Double DNAT)](#📋-phase-1---configuration-réseau-double-dnat)
- [Phase 2 : Configuration Ollama sur Windows Server](#🖥️-phase-2--configuration-ollama-sur-windows-server)
- [Phase 3 : Chargement du modèle Phi-3 dans Ollama](#🌐-phase-3--chargement-du-modèle-phi-3-dans-ollama)
- [Phase 4 : Tunnel HTTPS Cloudflare](#🔐-phase-4--tunnel-https-cloudflare) *(étape intermédiaire, retirée en Phase 6)*
- [Phase 5 : Déploiement interface web (Streamlit)](#💻-phase-5--déploiement-interface-web-streamlit)
- [Évolution de l'architecture (3 étapes)](#🔀-évolution-de-larchitecture-3-étapes)
- [Phase 6 : HTTPS avec nom de domaine + Let's Encrypt](#🔐-phase-6--https-avec-nom-de-domaine--lets-encrypt)
- [Opérations quotidiennes](#⚙️-opérations-quotidiennes)
- [Troubleshooting](#🐛-troubleshooting)
- [Limitations & notes de sécurité](#📌-limitations--notes-de-sécurité)

---

# 🔧 Phase 0 : Déploiement VM Windows Server

## 0.1 Spécifications VM

VM déployée via dashboard Hyper-V:

| Spec           | Valeur                         |
| -------------- | ------------------------------ |
| **OS**         | Windows Server 2022            |
| **vCPU**       | 4                              |
| **RAM**        | 8 GB                           |
| **Storage**    | 100 GB (system + Ollama cache) |
| **Network**    | (10.251.10.60)                 |
| **Hypervisor** | Hyper-V                        |

**Screenshots déploiement automatisé via une application web dev en  sur un serveur web dédier dans l'infra :**

![[Capture d’écran 2026-07-01 à 09.52.26.png]]
![[Capture d’écran 2026-07-01 à 09.46.36.png]]
![[Capture d’écran 2026-07-01 à 09.46.46.png]]


---

## 0.2 Post-déploiement

Une fois VM up:

```powershell
# Vérifier connectivité
ping 8.8.8.8

# Mettre à jour Windows
Update-Help
```

---

## 0.3 Installation Ollama sur VM

Sur la VM, télécharger et installer **Ollama desktop**:

1. https://ollama.com/download → Windows
2. Exécuter installer
3. Attendre complétion (~5 min)
4. Ollama démarre automatiquement

---

## 0.4 Vérification initiale

```powershell
# Vérifier Ollama écoute (défaut: localhost:11434)
netstat -an | findstr :11434
# Output: TCP    127.0.0.1:11434        0.0.0.0:0              LISTENING
```

✅ Ollama installé et fonctionnel, localement accessible.

---

## Architecture globale (état final, étape 3)

```
Users (Internet)
   │  HTTPS  hackaton-ia.nexa-cloud.fr:8501
   ▼
[Box FAI] 82.66.253.80 ─ DMZ
   │
   ▼
[FW1 Sophos] ─ DNAT → FW2
   │
   ▼
[FW2 Sophos] ─ DNAT → VM
   │
   ▼
[VM Windows Server] ─ Streamlit:8501 (TLS Let's Encrypt)
   │  localhost /api/chat
   ▼
[Ollama:8000] (localhost, non exposé)
```

![Architecture finale (double firewall multi-tenant)](infra-sh%C3%A9ma-2.png)

> ℹ️ Ceci est l'**état final**. L'archi a évolué en 3 temps (tunnel Cloudflare → app centralisée → HTTPS domaine). Détail des flux intermédiaires: [🔀 Évolution de l'architecture (3 étapes)](#🔀-évolution-de-larchitecture-3-étapes).

**Infrastructure:**
- **VM IP:** 10.251.10.60
- **Ports:** Ollama 8000 (localhost), Streamlit 8501 (exposé HTTPS)
- **Firewall:** Sophos XGS (double DNAT) + box FAI (forward 8501)
- **Domaine/cert:** `hackaton-ia.nexa-cloud.fr` (OVH), Let's Encrypt (win-acme, DNS-01)

---

# 📋 Phase 1 - Configuration Réseau (Double DNAT)

## 1.1 Objectif

Valider que le trafic externe atteint réellement Ollama sur la VM (pas juste des logs "accept" vides).

---

## 1.2 Rattachement : Carte réseau Hyper-V

VM-LLM-01 rattachée au vSwitch LAB-LAN, (réseau 10.251.10.0/24, IP VM `10.251.10.60`).

![[Capture d’écran 2026-07-01 à 10.07.09.png]]

---

## 1.3 Configuration DNAT : Double firewall Sophos en cascade

**Pourquoi 2 firewalls** (ce n'est pas un doublon) : l'infra est **multi-tenant**.
- **FW1 (EDGE-PRD-FW-XGS-01)** : pare-feu de **bordure Internet** (frontière, exposition publique).
- **FW2 (LAB-PRD-FW-01)** : pare-feu de **segmentation** qui isole le **segment LAB/test** (ce projet) des **autres environnements de production** (autres tenants). Le trafic doit donc traverser les deux avant d'atteindre la VM.

Deux DNAT enchaînés. Chaîne complète:

```
Internet → [FW1 EDGE] 192.168.1.253 → [FW2 SEGMENTATION] 10.0.0.251 → [VM LAB] 10.251.10.60:8000
```

Services publiés sur chaque FW:  **8000** et **11434**

### 1.3.1 FW1 : EDGE-PRD-FW-XGS-01 (bord)

DNAT: `192.168.1.253` (public) → `10.0.0.251` (FW-LAB).

Définition des services TCP_11434 et TCP_8000:

![[Capture d’écran 2026-07-01 à 10.27.38.png]]
![[Capture d’écran 2026-07-01 à 10.28.03.png]]

Assistant d'accès serveur (DNAT), résumé des règles NAT (DNAT + SNAT + bouclage):

![[Capture d’écran 2026-07-01 à 10.32.43.png]]

### 1.3.2 FW2 : LAB-PRD-FW-01 (interne)

DNAT: `10.0.0.251` (relais) → `10.251.10.60` (VM-LLM-01).

Ex : Création Service TCP 11434 + hôte IP de la VM:

![[Capture d’écran 2026-07-01 à 10.12.01.png]]
![[Capture d’écran 2026-07-01 à 10.15.09.png]]

Assistant d'accès serveur (DNAT), résumé (services 11434 + 8000, source Tous):

![[Capture d’écran 2026-07-01 à 10.17.05.png]]

---

## 1.4 Validation réseau : Mini serveur HTTP PowerShell

Avant de lancer Ollama, valider que la chaîne double DNAT atteint réellement la VM sur le port 8000. Mini serveur HTTP sur la VM qui logue chaque requête entrante.

**Script** (exécuter sur VM Windows Server):

```powershell
$port = 8000
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://+:$port/")
$listener.Start()
Write-Host "En ecoute sur le port $port... (Ctrl+C pour arreter)" -ForegroundColor Green

while ($listener.IsListening) {
    $context = $listener.GetContext()
    $request = $context.Request
    $response = $context.Response

    Write-Host "$(Get-Date -Format 'HH:mm:ss') - Requete recue depuis $($request.RemoteEndPoint)" -ForegroundColor Cyan

    $html = "<html><body><h1>Ca fonctionne !</h1><p>Tu as atteint la VM.</p></body></html>"
    $buffer = [System.Text.Encoding]::UTF8.GetBytes($html)
    $response.ContentLength64 = $buffer.Length
    $response.OutputStream.Write($buffer, 0, $buffer.Length)
    $response.OutputStream.Close()
}
```

**Pré-requis** (PowerShell ADMIN):

```powershell
New-NetFirewallRule -DisplayName "Test8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

**Test depuis l'extérieur:**
1. Navigateur externe → `http://192.168.1.253:8000` (IP publique FW1) → doit afficher "Ca fonctionne !"
2. Ou https://canyouseeme.org → port 8000

**Résultat attendu:** ✅ ligne `Requete recue depuis X.X.X.X` dans la console PowerShell → **chaîne double DNAT validée de bout en bout**. Le trafic externe traverse FW1 → FW2 → VM:8000.

> Une fois validé: **Ctrl+C** pour arrêter le mini serveur (libère le port 8000 pour Ollama).

---

## 1.5 Checklist réseau (si problème)

| # | Vérification | Comment |
|---|---|---|
| 1 | FW1 reçoit paquets | Logs FW1, voir si DNAT vers FW2 IP |
| 2 | FW2 reçoit paquets | Logs FW2, voir si DNAT vers VM IP |
| 3 | VM répond | `tcpdump` sur interface VM, voir SYN/ACK retour |
| 4 | SNAT FW2 correct | Retour doit passer par FW2, pas contourner |

---

# 🖥️ Phase 2 : Configuration Ollama sur Windows Server

## 2.1 Contexte

- Ollama installé via **app desktop** (pas service Windows)
- Besoin: écouter `0.0.0.0:8000` (toutes interfaces, port 8000)

---

## 2.2 Configuration : Variable d'environnement système

PowerShell **ADMIN**:

```powershell
# Définir variable SYSTEM (pas USER!)
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:8000', 'Machine')

# Vérifier immédiatement
[System.Environment]::GetEnvironmentVariable('OLLAMA_HOST', 'Machine')
# Output: 0.0.0.0:8000
```

> ⚠️ **Piège:** Variable doit être `Machine` (système), pas `User`. Commande silencieusement ignorée sinon.

---

## 2.3 Redémarrage Ollama

L'app desktop relit variables uniquement au démarrage:

```powershell
# Voir les process Ollama
Get-Process -Name "ollama*" -ErrorAction SilentlyContinue

# Tuer tout (app + moteur)
Get-Process -Name "ollama*" | Stop-Process -Force

# Attendre 5sec, relancer depuis Menu Démarrer ou raccourci
```

---

## 2.4 Pare-feu Windows

```powershell
New-NetFirewallRule -DisplayName "Ollama-8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Any
```

> **Paramètre `-Profile Any`:** Essentiel sur Windows Server. Profils (Domain/Private/Public) isolés sans ce flag.

---

## 2.5 Vérification

```powershell
netstat -an | findstr :8000
```

**Résultat attendu:**

```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
TCP    [::]:8000              [::]:0                 LISTENING
```

✅ Ollama écoute sur **IPv4 et IPv6**, port 8000.

---

# 🌐 Phase 3 : Chargement du modèle Phi-3 dans Ollama

## 3.1 Contexte : Déploiement Test : Phi-3.5

**Charger Phi-3.5 base → marche immédiatement + comparaison possible**

> Pour fine-tuning custom futur: voir section Merge Models ci-bas.

---

## 3.2 Installation Python (si absent)

```powershell
python --version
```

Si error:

```powershell
# Télécharger Python 3.11
$url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
$installer = "C:\python-installer.exe"
Invoke-WebRequest -Uri $url -OutFile $installer

# Installer (quiet + add to PATH)
& $installer /quiet InstallAllUsers=1 PrependPath=1

# ⚠️ REBOOT OBLIGATOIRE
Restart-Computer -Force
```

Après reboot:

```powershell
python --version  # Affiche Python 3.11.9
```

---

## 3.3 Installation Visual C++ Redistributable

```powershell
Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile "C:\vc_redist.exe"
& C:\vc_redist.exe /install /quiet /norestart
```

**Reboot obligatoire:**

```powershell
Restart-Computer -Force
```

> Sans VC++ redist: erreur DLL lors import torch.

---

## 3.4 Créer Modelfile pour Phi-3.5

Sur VM, créer `Modelfile.financial`:

```powershell
$modelfile = @"
FROM phi3.5
PARAMETER temperature 0.7
PARAMETER num_predict 2048
"@

$modelfile | Out-File C:\Users\Administrateur\projet\hackathon_ynov\Modelfile.financial -Encoding UTF8
```

---

## 3.5 Charger le modèle dans Ollama

```powershell
cd C:\Users\Administrateur\projet\hackathon_ynov
ollama create phi3-financial -f Modelfile.financial
```

Attendre téléchargement phi3.5 (~3-5 min).

**Vérifier:**

```powershell
ollama list
```

Output doit afficher `phi3-financial`.

**Test rapide:**

```powershell
ollama run phi3-financial "Hello, explain financial planning"
```

Doit générer réponse.

---

# 🔐 Phase 4 : Tunnel HTTPS Cloudflare

## 4.1 Contexte : Pourquoi Cloudflare?

**Problème:** App web dev en HTTPS ne peut pas appeler `http://IP:8000` (mixed content error).

**Décision:** Cloudflare quick tunnel (gratuit, pas compte, setup 2 min, URL pas stable OK pour test).

---

## 4.2 Installation cloudflared

```powershell
mkdir C:\cloudflared
Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile "C:\cloudflared\cloudflared.exe"
```

---

## 4.3 Lancer le tunnel

**Terminal 1 (garder ouvert pendant toute la session):**

```powershell
cd C:\cloudflared
.\cloudflared.exe tunnel --url http://localhost:8000
```

Attendre output:

```
Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):
https://affiliate-apache-supervisor-white.trycloudflare.com
```

**Copier cette URL** → à communiquer au devs.

---

## 4.4 Vérifier le tunnel

**Terminal 2:**

```powershell
$url = "https://affiliate-apache-supervisor-white.trycloudflare.com/api/tags"
Invoke-WebRequest -Uri $url | Select-Object -ExpandProperty Content
```

Output: JSON liste modèles (dont `phi3-financial`).

---

## 4.5 Endpoints pour l'équipe dev

**URL publique:**

```
https://affiliate-apache-supervisor-white.trycloudflare.com
```

**Lister modèles:**

```bash
GET https://affiliate-apache-supervisor-white.trycloudflare.com/api/tags
```

**Générer réponse:**

```bash
POST https://affiliate-apache-supervisor-white.trycloudflare.com/api/generate
Content-Type: application/json

{
  "model": "phi3-financial",
  "prompt": "What is financial risk management?",
  "stream": false
}
```

---

# 💻 Phase 5 : Déploiement interface web (Streamlit)

## 5.1 Contexte

Interface de chat **Streamlit** (`rendu/devweb/app.py`) qui parle à l'API native Ollama (`/api/tags` + `/api/chat` en streaming). URL serveur et nom du modèle configurables (sidebar ou variables d'environnement).

- **Repo:** branche `devweb` (repo équipe)
- **Port:** 8501
- **Modèle ciblé:** `phi3-financial`

---

## 5.2 Récupération du code (git)

```powershell
cd C:\Users\Administrateur
git clone https://github.com/DontRobMe/hackathon_ynov.git techcorp-team
cd techcorp-team
git checkout devweb
cd rendu\devweb
```

---

## 5.3 Docker KO sur Windows Server → déploiement natif

> ⚠️ **Piège:** Docker sur cette VM tourne en mode **Windows containers** (Docker EE, pas Docker Desktop). L'image `python:3.12-slim` est Linux → `no matching manifest for windows/amd64`. Pas de moteur Linux (ni WSL2 ni `DockerCli.exe -SwitchLinuxEngine`).

**Décision:** lancer l'app en **Python natif** (le Dockerfile reste dans le repo pour un hôte Linux, inutilisable ici).

Vérif du mode Docker si doute:
```powershell
docker info | Select-String "OSType"
# OSType: windows  → containers Linux impossibles
```

---

## 5.4 Installation + lancement

```powershell
# environnement Python isolé
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# config: Ollama est sur la MEME VM → localhost, pas besoin du tunnel Ollama
$env:OLLAMA_URL="http://localhost:8000"
$env:OLLAMA_MODEL="phi3-financial"

# lancement exposé (0.0.0.0 + headless pour skip le prompt email)
streamlit run app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false
```

> Flags `--server.enableCORS=false --server.enableXsrfProtection=false` : évitent les soucis WebSocket derrière le proxy Cloudflare.

---

## 5.5 Exposer l'app : 2e tunnel Cloudflare

L'app écoute sur 8501. On ajoute un **second** tunnel (indépendant de celui d'Ollama sur 8000).

**Nouvelle fenêtre PowerShell:**
```powershell
& "C:\cloudflared\cloudflared.exe" tunnel --url http://localhost:8501
```

→ nouvelle URL `https://<xxx>.trycloudflare.com` = **app publique** à partager.

**Bilan des tunnels:**
| Service | Port local | Tunnel | Usage |
|---------|-----------|--------|-------|
| Ollama API | 8000 | tunnel #1 | Devs tapant l'API directement |
| App Streamlit | 8501 | tunnel #2 | Interface chat grand public |

> 2 tunnels = 2 process cloudflared = 2 fenêtres à garder ouvertes.

---

## 5.6 Redéploiement / arrêt propre

Vérifier si un ancien serveur tourne encore:
```powershell
netstat -ano | findstr :8501
# ligne LISTENING + PID (dernière colonne) = tourne encore
```

Arrêter (PID des lignes LISTENING):
```powershell
Stop-Process -Id <PID> -Force
```

Puis relancer via 5.4. Les `TIME_WAIT` résiduels disparaissent seuls en ~30s.

---

# 🔀 Évolution de l'architecture (3 étapes)

Le déploiement a évolué en 3 temps. Chaque étape = un état fonctionnel, mais avec des compromis levés au fur et à mesure.

## Étape 1 : Tunnel public pour servir l'API aux devs (front en dev local)

Au début, seule l'**API Ollama** existe. Les devs bossent leur front **en local sur leur poste**, mais ont besoin du modèle. On expose l'API via un tunnel Cloudflare pour qu'ils tapent dessus à distance.

```
[Front dev - poste local]  ──HTTPS──►  [Cloudflare Tunnel]  ──►  [VM] Ollama:8000
```

- ✅ Débloque les devs sans attendre le serveur web
- ⚠️ URL tunnel instable, app pas encore centralisée

## Étape 2 : App centralisée sur le serveur, Ollama en localhost

L'interface web (Streamlit) est déployée **sur la même VM** que Ollama. Plus besoin d'exposer l'API : l'app parle à Ollama en **localhost**. C'est l'**app** qu'on expose via tunnel public.

```
[Users]  ──HTTPS──►  [Cloudflare Tunnel]  ──►  [VM] Streamlit:8501  ──localhost──►  Ollama:8000
```

- ✅ Tout centralisé sur la VM, comm interne en localhost (rapide, pas exposée)
- ⚠️ Dépend toujours du tunnel Cloudflare (URL éphémère, process à garder ouvert)

## Étape 3 : HTTPS + nom de domaine, tunnel Cloudflare supprimé

Achat d'un **nom de domaine** (`hackaton-ia.nexa-cloud.fr` chez OVH) pointant sur l'IP publique. Certificat **Let's Encrypt** valide (win-acme, validation DNS-01). L'app est servie **directement** via le double DNAT + HTTPS. **Le tunnel Cloudflare est retiré.**

```
[Users]  ──HTTPS (cert valide)──►  hackaton-ia.nexa-cloud.fr:8501
        │
        ▼
[Box FAI] → [FW1 Sophos] → [FW2 Sophos] → [VM] Streamlit:8501 (TLS) ──localhost──► Ollama:8000
```

- ✅ URL stable, cert valide (cadenas vert), plus de dépendance Cloudflare
- ⚠️ Renouvellement cert manuel tous les 90j (DNS-01)

![Évolution de l'architecture en 3 étapes](infra-sh%C3%A9ma.png)

---

# 🔐 Phase 6 : HTTPS avec nom de domaine + Let's Encrypt

## 6.1 Nom de domaine (OVH)

Domaine `hackaton-ia.nexa-cloud.fr`, **record A** pointant sur l'IP publique `82.66.253.80`:

![[Capture d’écran 2026-07-01 à 17.36.36.png]]

Vérifier la résolution:
```bash
nslookup hackaton-ia.nexa-cloud.fr
# → 82.66.253.80
```

---

## 6.2 Étape intermédiaire : cert self-signed (warning)

Avant le vrai cert, test en self-signed → Edge affiche **"Votre connexion n'est pas privée"** (`NET::ERR_CERT_AUTHORITY_INVALID`). Normal: aucune autorité ne signe un self-signed.

![[Capture d’écran 2026-07-01 à 17.42.23.png]]

> ⚠️ Un cert self-signed **chiffre** mais ne supprime **pas** le warning. Et **aucune CA (Let's Encrypt inclus) ne signe une IP nue**, d'où le besoin d'un nom de domaine.

---

## 6.3 Certificat Let's Encrypt via win-acme

**win-acme** (client ACME Windows) génère un cert valide.

```powershell
cd C:\
Invoke-WebRequest -Uri "https://github.com/win-acme/win-acme/releases/latest/download/win-acme.v2.2.9.1701.x64.pluggable.zip" -OutFile win-acme.zip
Expand-Archive win-acme.zip -DestinationPath C:\win-acme
cd C:\win-acme
.\wacs.exe
```

Menu win-acme → **M** (full options) → Source **Manual** → host `hackaton-ia.nexa-cloud.fr`:

![[Capture d’écran 2026-07-01 à 17.45.13.png|567]]

---

## 6.4 Validation DNS-01 (record TXT)

Le port 80 n'est **pas** forwardé → HTTP-01 échoue (`Timeout during connect`). On valide par **DNS-01** (option **6** dans win-acme): il donne un record TXT à créer dans OVH.

| Champ OVH | Valeur |
|-----------|--------|
| Sous-domaine | `_acme-challenge.hackaton-ia` |
| Type | TXT |
| Valeur | (chaîne fournie par win-acme, sans guillemets) |

Attendre la propagation (`nslookup -type=TXT _acme-challenge.hackaton-ia.nexa-cloud.fr`) **avant** de presser Enter.

---

## 6.5 Export PEM (ligne de commande)

Le menu interactif sauve souvent en cache PFX (mot de passe random). Forcer le store PEM en CLI:

```powershell
cd C:\win-acme
mkdir C:\certs -Force
.\wacs.exe --source manual --host hackaton-ia.nexa-cloud.fr --validationmode dns-01 --validation manual --store pemfiles --pemfilespath C:\certs
```

Résultat dans `C:\certs`:
- `hackaton-ia.nexa-cloud.fr-chain.pem` → **fullchain** (cert + intermédiaires)
- `hackaton-ia.nexa-cloud.fr-key.pem` → clé privée

---

## 6.6 Lancer Streamlit avec le cert valide

```powershell
cd C:\Users\Administrateur\techcorp-team\rendu\devweb
.\.venv\Scripts\Activate.ps1
$env:OLLAMA_URL="http://localhost:8000"
$env:OLLAMA_MODEL="phi3-financial"
python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false --server.enableWebsocketCompression=false --server.sslCertFile=C:\certs\hackaton-ia.nexa-cloud.fr-chain.pem --server.sslKeyFile=C:\certs\hackaton-ia.nexa-cloud.fr-key.pem --browser.serverAddress=hackaton-ia.nexa-cloud.fr --browser.serverPort=8501
```

**Accès:** `https://hackaton-ia.nexa-cloud.fr:8501` → **cadenas vert, zéro warning** 🔒

Points clés:
- `--browser.serverAddress=hackaton-ia.nexa-cloud.fr` → le WebSocket cible le domaine (match le cert)
- Accès **uniquement par le domaine** (cert invalide pour l'IP nue)
- **Renouvellement:** avant J+90, refaire `wacs.exe` + nouveau TXT (DNS-01 = pas d'auto-renew)

> Pré-requis réseau: forward du port **8501** sur box FAI + double DNAT Sophos + règle pare-feu Windows `Streamlit-8501`.

---

# ⚙️ Opérations quotidiennes

## Checklist démarrage

| Étape | Commande | Valeur attendue |
|-------|----------|---|
| Ollama écoute | `netstat -an \| findstr :8000` | `0.0.0.0:8000 LISTENING` |
| Modèle chargé | `ollama list` | `phi3-financial` visible |
| Test local | `Invoke-WebRequest http://localhost:8000/api/tags` | JSON modèles |
| Tunnel Ollama lancé | Terminal cloudflared :8000 ouvert | URL affichée `https://...` |
| Tunnel OK | `curl https://.../api/tags` | JSON retourné |
| App web écoute | `netstat -ano \| findstr :8501` | `0.0.0.0:8501 LISTENING` |
| Tunnel app lancé | Terminal cloudflared :8501 ouvert | URL affichée `https://...` |

---

# 📚 Références

- **Ollama docs:** https://ollama.com
- **Cloudflare Tunnel:** https://developers.cloudflare.com/cloudflare-one/connections/connect-apps
- **Phi-3 model:** https://huggingface.co/microsoft/phi3.5
- **Sophos FW:** Double DNAT configuration (voir logs FW)

---

## Annexe : Merger modèle LoRA (Advanced)

Si besoin futur d'utiliser `phi3-financial` custom:

```powershell
# Installer dépendances Python
pip install peft torch transformers

# Créer script merge_model.py
$code = @'
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

adapter_path = r"C:\Users\Administrateur\projet\hackathon_ynov\models\phi3_financial"
output_path = r"C:\Users\Administrateur\projet\hackathon_ynov\models\phi3_financial_merged"

print("Loading model + adapter...")
model = AutoPeftModelForCausalLM.from_pretrained(adapter_path, device_map="cpu")
tokenizer = AutoTokenizer.from_pretrained("microsoft/Phi-3-mini-4k-instruct")

print("Merging...")
model.merge_and_unload()
model.save_pretrained(output_path)
tokenizer.save_pretrained(output_path)
print(f"✓ Merged at {output_path}")
'@

$code | Out-File merge_model.py -Encoding UTF8

# Exécuter
python merge_model.py  # ~20-30 min
```

Créer `Modelfile.custom`:

```
FROM C:\Users\Administrateur\projet\hackathon_ynov\models\phi3_financial_merged
```

Charger:

```powershell
ollama create phi3-custom -f Modelfile.custom
```

---

**Document final v1.0** | Durand Hippolyte (M1 Infra) | 2026-07-01 | Status: ✅ Fonctionnel