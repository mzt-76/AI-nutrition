# Guide Docker -- AI Nutrition Assistant

Ce guide explique **chaque fichier Docker du projet**, ligne par ligne, pour que tu comprennes exactement ce qui se passe quand on deploie l'application.

---

## 1. C'est quoi Docker en 30 secondes

Imagine que tu veux donner ton appli a quelqu'un. Sans Docker, tu dois lui dire : "installe Python 3.11, puis Node 18, puis nginx, puis ces 47 packages pip, puis configure ceci...". Avec Docker :

**Un container = ton appli + toutes ses dependances, empaquetees ensemble.** Ca tourne de maniere identique sur ton PC, sur un serveur cloud, ou sur le PC d'un collegue. Zero surprise "ca marchait chez moi".

Concretement, Docker cree des mini-environnements isoles (des containers) qui partagent le noyau de ta machine mais sont completement separes les uns des autres. Chaque container a son propre systeme de fichiers, ses propres packages, son propre reseau interne.

Notre projet a **3 containers** :
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Backend   │  │  Frontend   │  │ RAG Pipeline│
│  (FastAPI)  │  │  (nginx +   │  │ (ingestion  │
│  port 8001  │  │   React)    │  │  documents) │
│             │  │  port 8080  │  │  pas de port│
└─────────────┘  └─────────────┘  └─────────────┘
```

---

## 2. Vocabulaire cle

| Terme | Definition |
|-------|-----------|
| **Image** | Un "snapshot" en lecture seule de ton appli + dependances. C'est le modele a partir duquel on cree des containers. Comme un `.iso` de Windows -- tu ne l'executes pas directement, tu crees une installation a partir de lui. |
| **Container** | Une instance vivante d'une image. C'est l'image qui *tourne*. Tu peux avoir plusieurs containers a partir de la meme image. |
| **Dockerfile** | La recette pour construire une image. Chaque ligne est une instruction : "pars de Python 3.11", "copie ces fichiers", "installe ces packages", etc. |
| **docker-compose.yml** | Le chef d'orchestre. Definit plusieurs services (containers) qui travaillent ensemble : quel Dockerfile utiliser, quels ports ouvrir, quelles variables d'environnement passer, dans quel ordre demarrer. |
| **Build context** | Le dossier que Docker "voit" pendant le build. Quand tu fais `build.context: .`, Docker envoie tout le dossier courant au daemon Docker. Plus c'est petit, plus le build est rapide. |
| **.dockerignore** | Comme `.gitignore` mais pour Docker. Liste les fichiers a NE PAS envoyer dans le build context. Crucial pour la vitesse (evite d'envoyer node_modules, .git, etc.) et la securite (evite de copier `.env` dans l'image). |
| **Layer (couche)** | Chaque instruction du Dockerfile cree une couche. Docker cache les couches qui n'ont pas change. Si tu changes une ligne de code mais pas `requirements.txt`, Docker reutilise la couche "pip install" deja construite -- gain de temps enorme. |
| **Volume** | Un dossier partage entre ta machine hote et le container. Les donnees persistent meme si le container est detruit. Exemple : `./rag-documents:/app/Local_Files/data` = le dossier `rag-documents` de ton PC est visible dans le container comme `/app/Local_Files/data`. |
| **Multi-stage build** | Un Dockerfile avec plusieurs etapes. Etape 1 : compile le code (gros environnement avec Node.js). Etape 2 : copie seulement le resultat compile dans une image legere (nginx). Resultat : image finale minuscule. |
| **Reverse proxy** | Un serveur qui se met "devant" tes services et redirige le trafic. Les utilisateurs parlent au proxy, le proxy parle a tes containers. Permet d'avoir des noms de domaine jolis et du HTTPS automatique. |
| **Health check** | Un test que Docker execute regulierement pour verifier que ton container est en vie. Si le test echoue plusieurs fois, Docker redemarre le container automatiquement. |

---

## 3. Nos fichiers Docker -- expliques ligne par ligne

### 3.1 `.dockerignore` (racine du projet)

Ce fichier dit a Docker : "quand tu construis l'image du backend, **ignore** ces fichiers". C'est critique pour deux raisons :
1. **Performance** : sans lui, Docker enverrait tout le projet (~500 Mo+) au daemon. Avec lui, seulement ~5 Mo.
2. **Securite** : empeche les fichiers `.env` (avec tes cles API) de se retrouver dans l'image.

```
# Python caches
__pycache__          # Fichiers compiles Python -- regeneres automatiquement
*.pyc                # Idem, format individuel
*.pyo                # Idem, version optimisee
.pytest_cache        # Cache des tests -- inutile en prod
.mypy_cache          # Cache du type checker -- inutile en prod
.ruff_cache          # Cache du linter -- inutile en prod
```

**Pourquoi :** Ces fichiers sont regeneres automatiquement. Les inclure ne ferait qu'alourdir l'image.

```
# Virtual environments
venv                 # Environnement Python local (souvent 200+ Mo)
.venv                # Meme chose, nom alternatif
```

**Pourquoi :** Le container installe ses propres dependances via `pip install`. Ton `venv` local est pour le dev sur ta machine, pas pour le container.

```
# Tests & dev -- not needed in prod container
tests/               # Tests unitaires
evals/               # Evaluations LLM
scripts/             # Scripts utilitaires
conftest.py          # Config pytest
pytest.ini           # Config pytest
ruff.toml            # Config linter
requirements-dev.txt # Dependances de dev (pytest, ruff, mypy...)
```

**Pourquoi :** En production, on ne lance pas les tests. Moins de fichiers = image plus petite et surface d'attaque reduite.

```
# Frontend -- separate container
frontend/            # Le frontend a son propre Dockerfile et son propre container

# RAG Pipeline -- separate container
src/RAG_Pipeline/    # La pipeline RAG a aussi son propre Dockerfile
```

**Pourquoi :** Chaque service est un container separe. Le backend n'a pas besoin du code React ni du code RAG.

```
# Documentation
*.md                 # Tous les fichiers Markdown
PRD.md               # Product Requirements Document
README.md            # Readme du projet
CLAUDE.md            # Instructions pour Claude
```

**Pourquoi :** La documentation est pour les humains et les LLMs, pas pour le serveur en production.

```
# Course material & prototypes
ai-agent-mastery/
custom-agent-with-skills/
fastapi-starter-for-ai-coding/
generative_UI_project_example/
prototype/
nutrition references/
```

**Pourquoi :** Ce sont des dossiers de cours/prototypes qui trainent dans le repo. Aucun rapport avec le code de prod.

```
# Environment files (secrets)
.env                 # Variables d'environnement avec tes cles API
.env.*               # Variantes (.env.dev, .env.prod)
".env dev"           # Nom avec espace (Windows)
".env prod"          # Idem
.env.example         # Template -- pas de secrets mais inutile en prod
```

**Pourquoi : SECURITE.** Si un `.env` finit dans l'image Docker, n'importe qui ayant acces a l'image peut extraire tes cles API. Les variables sont injectees au *runtime* via `docker-compose.yml`, jamais copiees dans l'image.

```
# IDE / OS / tooling
.vscode/             # Config VS Code
.idea/               # Config JetBrains
.claude/             # Config Claude Code
e2e-screenshots/     # Screenshots des tests visuels
logs/                # Fichiers de log locaux

# SQL migrations (run separately)
sql/                 # Scripts SQL -- executes independamment sur Supabase

# Git & Docker
.git                 # Historique Git (peut faire 100+ Mo)
.gitignore           # Config Git
Dockerfile           # Le Dockerfile lui-meme (meta, pas besoin dans l'image)
docker-compose*.yml  # Idem
```

**Pourquoi :** `.git` est souvent le fichier le plus lourd du projet. Les migrations SQL sont executees directement sur Supabase, pas par le container. Les fichiers Docker eux-memes ne servent a rien *dans* l'image.

---

### 3.2 `Dockerfile` (backend -- racine du projet)

C'est la recette pour construire l'image du backend (FastAPI + Agent + Skills).

```dockerfile
FROM python:3.11-slim
```

**Point de depart :** on part d'une image officielle Python 3.11 en version `slim`.

- `python:3.11` (image "full") = **~900 Mo** -- inclut des compilateurs, des outils de debug, la doc Python, etc.
- `python:3.11-slim` = **~150 Mo** -- le strict minimum pour faire tourner Python.

On economise 750 Mo. En prod, on n'a pas besoin du superflu.

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libopenblas-dev \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
```

**Installe des outils systeme :**
- `gcc` + `g++` : compilateurs C/C++. Certaines dependances Python (comme `pydantic`, `numpy`) ont des extensions C qui doivent etre compilees lors du `pip install`.
- `libopenblas-dev` : librairie d'algebre lineaire. Necessaire pour `scipy`, qui fait tourner notre solveur MILP (optimisation des portions dans le meal-planning).
- `curl` : pour le health check -- Docker appelle `curl http://localhost:8001/health` pour verifier que le serveur tourne.
- `--no-install-recommends` : n'installe que le strict necessaire, pas les packages "recommandes" optionnels.
- `apt-get clean && rm -rf /var/lib/apt/lists/*` : nettoie le cache APT. Economise ~30 Mo dans l'image finale.

```dockerfile
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser
```

**Cree un utilisateur non-root.** Par defaut, tout dans Docker tourne en `root` (administrateur). C'est une mauvaise pratique de securite : si un attaquant exploite une faille dans ton appli, il a les droits root dans le container. Avec un utilisateur limite (`appuser`), les degats sont contenus.

- `-r` : utilisateur systeme (pas de login interactif)
- `-g appuser` : appartient au groupe `appuser`
- `-m -d /home/appuser` : cree un repertoire home

```dockerfile
WORKDIR /app
```

**Definit le repertoire de travail.** Toutes les commandes suivantes s'executent depuis `/app`. C'est comme faire `cd /app`.

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
```

**Installe les dependances Python.** C'est ici qu'intervient le **layer caching** de Docker.

L'ordre est delibere : on copie `requirements.txt` **en premier**, puis on installe, et seulement **apres** on copie le code source. Pourquoi ?

- Docker cache chaque couche (layer).
- Si `requirements.txt` n'a pas change depuis le dernier build, Docker reutilise la couche "pip install" deja construite.
- `pip install` prend 2-3 minutes. Le copier le code prend 1 seconde.
- Si on avait fait `COPY . .` puis `pip install`, la moindre modification de code invaliderait le cache et forcerait un `pip install` complet a chaque build.

`--no-cache-dir` : ne stocke pas le cache pip dans l'image. Economise de l'espace.

```dockerfile
COPY src/ ./src/
COPY skills/ ./skills/
```

**Copie le code source.** On ne copie que ce dont le backend a besoin :
- `src/` : le code principal (agent, API, tools, nutrition, etc.)
- `skills/` : les scripts de skills (meal-planning, food-tracking, etc.)

On ne copie PAS `tests/`, `frontend/`, `evals/`, etc. grace au `.dockerignore` **et** a ces `COPY` cibles.

```dockerfile
RUN chown -R appuser:appuser /app /home/appuser
```

**Donne la propriete des fichiers a `appuser`.** Les fichiers copies par `COPY` appartiennent a `root`. On les reassigne a notre utilisateur non-root pour qu'il puisse les lire et les executer.

```dockerfile
USER appuser
```

**A partir d'ici, tout s'execute en tant que `appuser`**, pas `root`. Le serveur FastAPI tournera avec des privileges limites.

```dockerfile
EXPOSE 8001
```

**Documentation.** Dit "ce container ecoute sur le port 8001". Attention : `EXPOSE` n'ouvre PAS reellement le port. C'est juste un indice pour les humains et les outils. Le vrai mapping de port se fait dans `docker-compose.yml` avec `ports: "8001:8001"`.

```dockerfile
ENV PYTHONUNBUFFERED=1
```

**Force Python a afficher les logs immediatement** au lieu de les bufferiser. Sans ca, quand tu fais `docker logs`, tu pourrais voir les logs avec un delai de plusieurs secondes, ou pas du tout si le container crash. Avec `PYTHONUNBUFFERED=1`, chaque `print()` et chaque log apparait instantanement.

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1
```

**Health check :** Docker verifie que le container est en vie.

- `--interval=30s` : verifie toutes les 30 secondes
- `--timeout=10s` : si pas de reponse en 10s, le test echoue
- `--start-period=40s` : attend 40s avant le premier test (le temps que FastAPI demarre et charge les modeles)
- `--retries=3` : 3 echecs consecutifs = container marque "unhealthy" et redemarrage automatique (si `restart: always`)
- `curl -f http://localhost:8001/health` : appelle l'endpoint `/health` de notre API. `-f` fait echouer curl si le serveur repond avec une erreur HTTP.

```dockerfile
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8001"]
```

**La commande qui lance le container.** Demarre le serveur FastAPI avec uvicorn.
- `src.api:app` : l'objet `app` dans le module `src.api`
- `--host 0.0.0.0` : ecoute sur toutes les interfaces reseau (necessaire dans Docker -- `localhost` ne suffit pas car les requetes viennent de l'exterieur du container)
- `--port 8001` : ecoute sur le port 8001

`CMD` peut etre remplacee au lancement (`docker run ... python mon_script.py`). C'est different de `ENTRYPOINT` qui est "fixe".

---

### 3.3 `frontend/Dockerfile` (multi-stage build)

C'est le Dockerfile le plus interessant. Il utilise un **multi-stage build** : deux etapes dans un seul fichier. Le resultat est une image de ~30 Mo au lieu de ~1 Go.

#### Stage 1 : Build (compilation React)

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
```

**Premiere etape :** on part de Node.js 18 sur Alpine Linux (image ultra-legere). `AS builder` lui donne un nom pour y faire reference plus tard.

```dockerfile
COPY package.json package-lock.json ./
RUN npm ci
```

**Installe les dependances Node.** Meme strategie de layer caching que le backend :
1. Copie `package.json` et `package-lock.json` en premier
2. `npm ci` installe les dependances

`npm ci` vs `npm install` :
- `npm install` peut modifier `package-lock.json` si les versions ne correspondent pas
- `npm ci` utilise le lockfile **exactement** tel quel. Si ca ne colle pas, il echoue. C'est deterministe : tout le monde obtient exactement les memes versions.

```dockerfile
COPY . .
```

**Copie tout le code frontend.** Grace au `frontend/.dockerignore`, certains fichiers sont exclus (node_modules, dist, .env, *.md).

```dockerfile
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_AGENT_ENDPOINT
ARG VITE_ENABLE_STREAMING=true
ARG VITE_LANGFUSE_HOST_WITH_PROJECT
```

**`ARG` = variables de build.** Elles existent uniquement pendant la construction de l'image. Elles sont passees par `docker-compose.yml` via la section `build.args`.

```dockerfile
ENV VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
ENV VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}
ENV VITE_AGENT_ENDPOINT=${VITE_AGENT_ENDPOINT}
ENV VITE_ENABLE_STREAMING=${VITE_ENABLE_STREAMING}
ENV VITE_LANGFUSE_HOST_WITH_PROJECT=${VITE_LANGFUSE_HOST_WITH_PROJECT}
```

**`ARG` -> `ENV` :** On convertit les `ARG` en `ENV` pour que `npm run build` puisse les voir. Vite (notre bundler) cherche les variables d'environnement prefixees par `VITE_` et les **integre directement dans le code JavaScript** au moment de la compilation. C'est pour ca qu'on a besoin de l'URL Supabase au moment du build, pas au runtime.

**Pourquoi le prefixe `VITE_` :** C'est une convention de securite de Vite. Seules les variables commencant par `VITE_` sont exposees au code frontend. Ca evite de fuiter accidentellement des secrets serveur dans le JavaScript envoye aux navigateurs.

```dockerfile
RUN npm run build
```

**Compile l'application React.** Resultat : un dossier `dist/` contenant des fichiers HTML, CSS et JS statiques, optimises et minifies. C'est tout ce dont on a besoin pour servir l'appli.

#### Stage 2 : Serve (serveur nginx)

```dockerfile
FROM nginx:alpine
```

**Deuxieme etape :** on repart de zero avec une image nginx ultra-legere (~20 Mo). Tout ce qui existait dans l'etape 1 (Node.js, node_modules, le code source TypeScript) est **abandonne**. On ne garde que ce qu'on copie explicitement.

```dockerfile
RUN apk add --no-cache dumb-init
```

**Installe `dumb-init` :** un mini programme d'init. Dans un container, le processus principal a le PID 1. Le probleme : le PID 1 sous Linux a un comportement special -- il ne recoit pas les signaux par defaut (comme SIGTERM quand Docker veut arreter le container). `dumb-init` se met en PID 1 et transmet les signaux correctement a nginx. Sans lui, `docker stop` pourrait prendre 10s (timeout force) au lieu d'un arret propre.

```dockerfile
RUN addgroup -g 1001 -S appuser && \
    adduser -S appuser -u 1001
```

**Utilisateur non-root**, meme logique que le backend. Syntaxe differente car Alpine utilise `adduser`/`addgroup` au lieu de `useradd`/`groupadd`.

```dockerfile
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html
```

Deux copies cruciales :
1. Notre config nginx personnalisee (section 3.5)
2. `--from=builder` : copie le dossier `dist/` **depuis l'etape 1** (le builder) dans le dossier standard de nginx. C'est la magie du multi-stage : on recupere le resultat de la compilation sans trainer Node.js et 400 Mo de node_modules.

```dockerfile
RUN mkdir -p /var/cache/nginx /var/run/nginx && \
    chown -R appuser:appuser /var/cache/nginx /var/run/nginx /usr/share/nginx/html
```

**Permissions :** nginx a besoin d'ecrire dans ces dossiers (cache, PID file). On les cree et on les donne a `appuser`.

```dockerfile
EXPOSE 8080
USER appuser
```

Documentation du port et switch vers l'utilisateur non-root.

```dockerfile
ENTRYPOINT ["dumb-init", "--"]
CMD ["nginx", "-g", "daemon off;"]
```

- `ENTRYPOINT` : `dumb-init` est le point d'entree fixe (gestion des signaux)
- `CMD` : lance nginx au premier plan (`daemon off` empeche nginx de se detacher -- Docker a besoin que le processus principal reste au premier plan)

**Resultat :** une image de ~30 Mo qui sert notre appli React via nginx. Compare aux ~1 Go si on avait garde Node.js.

---

### 3.4 `src/RAG_Pipeline/Dockerfile`

Le Dockerfile le plus simple. La pipeline RAG est un **worker en arriere-plan** qui ingere des documents et les transforme en embeddings pour la base de donnees.

```dockerfile
FROM python:3.11-slim
```

Meme base que le backend.

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
```

Seulement `gcc` et `g++` ici. Pas besoin de :
- `libopenblas-dev` : pas de solveur MILP dans la pipeline RAG
- `curl` : pas de health check HTTP (ce n'est pas un serveur web, c'est un worker qui tourne en boucle)

```dockerfile
RUN groupadd -r ragpipeline && useradd -r -g ragpipeline ragpipeline
```

Utilisateur non-root dedie (`ragpipeline` au lieu de `appuser` -- noms differents pour plus de clarte).

```dockerfile
WORKDIR /app

COPY requirements.txt ./requirements_raw.txt
RUN iconv -f UTF-16LE -t UTF-8 requirements_raw.txt > requirements.txt 2>/dev/null || cp requirements_raw.txt requirements.txt && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    rm requirements_raw.txt
```

**L'astuce `iconv` :** le fichier `requirements.txt` de la pipeline RAG a ete sauvegarde en UTF-16 (encodage Windows). Docker/pip ont besoin d'UTF-8. La commande :
1. Essaie de convertir de UTF-16LE vers UTF-8
2. Si ca echoue (le fichier est deja en UTF-8), copie simplement le fichier tel quel (`||`)
3. Installe les dependances pip
4. Supprime le fichier temporaire

Ca gere les deux cas sans erreur.

```dockerfile
COPY . .
RUN chmod +x docker_entrypoint.py
```

Copie tout le code de la pipeline et rend l'entrypoint executable.

```dockerfile
RUN mkdir -p /app/Local_Files/data /app/Google_Drive/credentials && \
    chown -R ragpipeline:ragpipeline /app
```

Cree les dossiers ou seront montes les volumes (documents locaux et credentials Google Drive) et donne les permissions.

```dockerfile
USER ragpipeline
```

Switch vers l'utilisateur non-root.

```dockerfile
ENV RAG_PIPELINE_TYPE=local
ENV RUN_MODE=continuous
ENV CHECK_INTERVAL=60
ENV PYTHONUNBUFFERED=1
```

**Valeurs par defaut :**
- `RAG_PIPELINE_TYPE=local` : surveille un dossier local (pas Google Drive)
- `RUN_MODE=continuous` : tourne en boucle indefiniment
- `CHECK_INTERVAL=60` : verifie les nouveaux fichiers toutes les 60 secondes
- `PYTHONUNBUFFERED=1` : logs immediats (meme raison que le backend)

Ces valeurs sont des defauts -- `docker-compose.yml` peut les remplacer.

```dockerfile
ENTRYPOINT ["python", "docker_entrypoint.py"]
```

**`ENTRYPOINT` vs `CMD` :**
- `CMD` (utilise par le backend) : la commande par defaut, facilement remplacable avec `docker run ... ma_commande`
- `ENTRYPOINT` : la commande "fixe". Si tu fais `docker run rag-pipeline arg1`, ca execute `python docker_entrypoint.py arg1`. C'est plus adapte pour un worker qui ne devrait jamais etre lance autrement.

**Pas de `EXPOSE` :** cette pipeline n'est pas un serveur web. Elle ne recoit pas de requetes HTTP. Elle tourne en arriere-plan, lit des fichiers, et ecrit des embeddings dans Supabase.

---

### 3.5 `nginx.conf` (configuration frontend)

Nginx est le serveur web qui sert notre application React compilee. Voici la config complete expliquee :

```nginx
worker_processes auto;
```

**Nombre de workers :** `auto` = un worker par coeur CPU. Nginx utilise un modele evenementiel (non-bloquant) donc meme un seul worker gere des milliers de connexions simultanees.

```nginx
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx/nginx.pid;
```

Ou ecrire les logs d'erreur et le fichier PID (necessaire pour que nginx sache quel processus arreter).

```nginx
events {
    worker_connections 1024;
}
```

Chaque worker peut gerer 1024 connexions simultanees. Pour un site avec quelques utilisateurs, c'est largement suffisant.

```nginx
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
```

Charge les types MIME (pour que le navigateur sache que `.js` = JavaScript, `.css` = CSS, etc.). Si un fichier n'a pas de type reconnu, il est traite comme un fichier binaire generique.

```nginx
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent"';
    access_log /var/log/nginx/access.log main;
```

Format des logs d'acces. Chaque requete est loguee avec l'IP, la date, l'URL, le code HTTP, la taille de la reponse, etc.

```nginx
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
```

**Optimisations reseau :**
- `sendfile on` : utilise un appel systeme optimise pour envoyer des fichiers (evite de copier les donnees en memoire)
- `tcp_nopush on` : envoie les headers et le debut du fichier en un seul paquet TCP
- `tcp_nodelay on` : envoie les petits paquets immediatement (pas de delai Nagle)
- `keepalive_timeout 65` : garde les connexions TCP ouvertes 65s (evite de recreer une connexion pour chaque requete)

```nginx
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript
               application/javascript application/json
               application/xml+rss application/manifest+json
               image/svg+xml;
```

**Compression gzip :** nginx compresse les reponses avant de les envoyer au navigateur.
- Un fichier JavaScript de 500 Ko devient ~100 Ko compresse. Le navigateur le decompresse instantanement.
- `gzip_min_length 1024` : ne compresse pas les fichiers de moins de 1 Ko (le overhead de compression ne vaut pas le coup)
- `gzip_types` : ne compresse que les types texte. Les images (PNG, JPG) sont deja compressees -- les re-compresser serait du gaspillage.
- `gzip_vary on` : ajoute un header `Vary: Accept-Encoding` pour que les caches intermediaires sachent qu'il existe une version compressee et une non-compressee.

```nginx
    server {
        listen 8080;
        server_name localhost;
        root /usr/share/nginx/html;
        index index.html;
```

Le serveur ecoute sur le port 8080 et sert les fichiers depuis `/usr/share/nginx/html` (ou le Dockerfile a copie le `dist/` de React).

```nginx
        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "no-referrer-when-downgrade" always;
```

**Headers de securite :**
- `X-Frame-Options "SAMEORIGIN"` : empeche d'autres sites d'integrer notre appli dans une `<iframe>` (protection contre le clickjacking -- un attaquant met un bouton invisible par-dessus notre page)
- `X-Content-Type-Options "nosniff"` : empeche le navigateur de "deviner" le type d'un fichier. Sans ca, un navigateur pourrait traiter un fichier texte comme du JavaScript si le contenu y ressemble (vecteur d'attaque XSS)
- `X-XSS-Protection "1; mode=block"` : active le filtre XSS integre du navigateur
- `Referrer-Policy` : controle quelles informations d'URL sont envoyees quand l'utilisateur navigue vers un autre site

```nginx
        location / {
            try_files $uri $uri/ /index.html;
        }
```

**Le coeur du SPA routing.** C'est la ligne la plus importante pour une Single Page Application (React).

Quand l'utilisateur navigue vers `https://tonsite.com/plans/abc123`, nginx cherche :
1. Un fichier `/plans/abc123` -- n'existe pas
2. Un dossier `/plans/abc123/` -- n'existe pas
3. Fallback : `/index.html` -- **existe !** React se charge, React Router lit l'URL et affiche le bon composant.

Sans `try_files`, naviguer directement vers une URL (ou rafraichir la page) donnerait une erreur 404.

```nginx
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|webp)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
```

**Cache des fichiers statiques.** Vite genere des noms de fichiers avec un hash du contenu : `app.a1b2c3d4.js`. Si le code change, le hash change, donc le nom change, donc c'est une nouvelle URL.

Resultat : on peut dire au navigateur "cache ce fichier pendant 1 an" (`expires 1y`). Le navigateur ne le retelecharge jamais. Quand le code change, le nouveau fichier a un nouveau nom, donc le navigateur fait une nouvelle requete.

`immutable` : dit au navigateur "ce fichier ne changera JAMAIS, ne verifie meme pas".

```nginx
        location = /sw.js {
            add_header Cache-Control "no-cache, no-store, must-revalidate";
        }

        location = /manifest.json {
            add_header Cache-Control "no-cache";
            add_header Content-Type "application/manifest+json";
        }
```

**Exception PWA :** le service worker (`sw.js`) et le manifest ne doivent JAMAIS etre caches. Un service worker cache controlerait quelles versions de l'appli les utilisateurs voient -- potentiellement bloquant sur une vieille version pour toujours.

```nginx
        location = /index.html {
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Pragma "no-cache";
            add_header Expires "0";
        }
```

**`index.html` : JAMAIS cache.** C'est le fichier racine qui contient les liens `<script src="app.a1b2c3d4.js">`. Si on deploie une nouvelle version :
- Les fichiers JS/CSS ont de nouveaux hashes (nouveaux noms)
- `index.html` est mis a jour pour pointer vers ces nouveaux fichiers
- Le navigateur doit toujours telecharger le dernier `index.html` pour savoir quels fichiers JS/CSS charger

`Pragma: no-cache` et `Expires: 0` sont des fallbacks pour les vieux navigateurs/proxies.

```nginx
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
```

**Endpoint de sante.** Docker appelle cette URL pour verifier que nginx est en vie. `access_log off` evite de spammer les logs avec une requete toutes les 30 secondes.

---

### 3.6 `.dockerignore` files (frontend + RAG Pipeline)

#### `frontend/.dockerignore`

```
node_modules     # Les dependances sont reinstallees par npm ci
dist             # Le dossier de build est recree par npm run build
.env             # Secrets
.env.*           # Variantes
e2e-screenshots  # Screenshots de test
*.md             # Documentation
```

L'exclusion de `node_modules` est critique : ce dossier fait souvent 300+ Mo. Docker le recreerait de toute facon avec `npm ci`.

#### `src/RAG_Pipeline/.dockerignore`

```
__pycache__      # Cache Python
.pytest_cache    # Cache pytest
venv             # Environnement Python local
.env             # Secrets
tests/           # Tests unitaires
*.md             # Documentation
```

Meme logique : exclure ce qui sera regenere, ce qui n'est pas necessaire en prod, et surtout les secrets.

---

## 4. `docker-compose.yml` -- l'orchestrateur

Ce fichier definit les 3 services qui composent notre application et comment ils interagissent.

```yaml
services:
```

Tout est sous la cle `services`. Chaque service = un container.

### 4.1 Backend

```yaml
  backend:
    build:
      context: .
      dockerfile: Dockerfile
```

- `context: .` : le build context est la racine du projet. Docker envoie tout ce dossier (filtre par `.dockerignore`) au daemon Docker.
- `dockerfile: Dockerfile` : utilise le Dockerfile a la racine.

```yaml
    container_name: ai-nutrition-backend
```

Nom lisible pour le container. Sans ca, Docker genererait un nom comme `ai-nutrition-backend-1`. Avec ca, tu peux faire `docker logs ai-nutrition-backend` directement.

```yaml
    restart: always
```

Si le container crash, Docker le redemarre automatiquement. Toujours. Meme apres un reboot de la machine. Les alternatives sont `no` (defaut), `on-failure`, `unless-stopped`.

```yaml
    ports:
      - "8001:8001"
```

**Mapping de port :** `port_hote:port_container`. Le port 8001 de ta machine est relie au port 8001 du container. Quand tu vas sur `http://localhost:8001`, la requete arrive dans le container.

Si tu avais mis `"9000:8001"`, tu accederais au backend via `http://localhost:9000` mais a l'interieur du container, uvicorn ecoute toujours sur 8001.

```yaml
    environment:
      - ENVIRONMENT=${ENVIRONMENT:-production}
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - LLM_CHOICE=${LLM_CHOICE:-claude-haiku-4-5-20251001}
      - LLM_API_KEY=${LLM_API_KEY}
      # ... etc.
```

**Variables d'environnement** passees au container. La syntaxe `${VAR:-default}` signifie :
- Cherche la variable `VAR` dans le fichier `.env`
- Si elle n'existe pas, utilise `default` comme valeur de repli

Exemple : `${LLM_CHOICE:-claude-haiku-4-5-20251001}` = si `LLM_CHOICE` n'est pas defini dans `.env`, utilise `claude-haiku-4-5-20251001`.

`${LLM_API_KEY}` (sans `:-`) : pas de defaut. Si la variable n'existe pas dans `.env`, elle sera vide dans le container.

Les variables sont organisees par categorie :
- **LLM** : configuration du modele de langage (provider, API key, modele choisi)
- **Embeddings** : modele d'embeddings pour la recherche semantique
- **Database** : URL et cle Supabase
- **Search** : Brave Search ou SearXNG pour la recherche web
- **API** : CORS, log level, dossier des skills
- **Memory** : modele pour Mem0 (memoire long-terme)
- **Observability** : Langfuse pour le monitoring des conversations (optionnel)

```yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**Health check** au niveau docker-compose (meme chose que dans le Dockerfile mais ici ca permet de definir des dependances entre services). Docker execute la commande `curl -f http://localhost:8001/health` toutes les 30 secondes. Si elle echoue 3 fois de suite, le container est marque "unhealthy".

### 4.2 RAG Pipeline

```yaml
  rag-pipeline:
    build:
      context: ./src/RAG_Pipeline
      dockerfile: Dockerfile
```

Le build context est `./src/RAG_Pipeline` -- Docker ne voit que ce sous-dossier. Le `.dockerignore` de ce dossier s'applique.

```yaml
    container_name: ai-nutrition-rag-pipeline
    restart: always
    environment:
      - ENVIRONMENT=${ENVIRONMENT:-production}
      - RAG_PIPELINE_TYPE=${RAG_PIPELINE_TYPE:-local}
      - RUN_MODE=${RUN_MODE:-continuous}
      # ... memes DB et embedding que le backend ...
```

La pipeline RAG partage les memes credentials Supabase et embeddings que le backend (meme base de donnees), mais c'est un container separe. Pourquoi ?

**Separation des responsabilites :**
- Le backend repond aux requetes des utilisateurs (temps reel, doit etre rapide)
- La pipeline RAG ingere des documents (tache lourde en arriere-plan, peut prendre du temps)

Si la pipeline crash en traitant un gros PDF, le backend continue de fonctionner. Si le backend est mis a jour, la pipeline continue de tourner. Ils peuvent etre scales independamment.

```yaml
    volumes:
      - ./rag-documents:/app/Local_Files/data
      - ./google-credentials:/app/Google_Drive/credentials
```

**Volumes :** deux dossiers de ta machine sont "montes" dans le container.
- `./rag-documents` sur ton PC apparait comme `/app/Local_Files/data` dans le container. Tu poses un PDF dans `rag-documents/`, la pipeline le detecte et le traite.
- `./google-credentials` : credentials OAuth2 pour Google Drive.

Les donnees dans ces volumes persistent meme si le container est detruit et recree.

**Pas de `ports` :** la pipeline RAG n'est pas un serveur web. Elle ne recoit aucune requete HTTP. Elle lit des fichiers, cree des embeddings, et les envoie a Supabase. Pas besoin d'ouvrir un port.

### 4.3 Frontend

```yaml
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_SUPABASE_URL: ${VITE_SUPABASE_URL}
        VITE_SUPABASE_ANON_KEY: ${VITE_SUPABASE_ANON_KEY}
        VITE_AGENT_ENDPOINT: ${VITE_AGENT_ENDPOINT:-http://localhost:8001/api/agent}
        VITE_ENABLE_STREAMING: ${VITE_ENABLE_STREAMING:-true}
        VITE_LANGFUSE_HOST_WITH_PROJECT: ${VITE_LANGFUSE_HOST_WITH_PROJECT}
```

`build.args` : ce sont les variables de **build-time** (voir `ARG` dans le Dockerfile frontend). Elles sont passees pendant la construction de l'image, PAS au runtime. Vite les integre dans le bundle JavaScript. Une fois l'image construite, ces valeurs sont figees dans le code JS.

C'est pourquoi changer `VITE_SUPABASE_URL` dans `.env` necessite un **rebuild** de l'image frontend (`docker compose up --build`), pas juste un restart.

```yaml
    container_name: ai-nutrition-frontend
    restart: always
    ports:
      - "8080:8080"
```

Le frontend est accessible sur `http://localhost:8080`.

```yaml
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
```

Health check avec `wget` (car l'image nginx:alpine a `wget` mais pas `curl`). `--spider` verifie l'URL sans telecharger le contenu.

`start_period: 20s` au lieu de 40s : nginx demarre quasi instantanement (contrairement a FastAPI qui charge des modeles).

```yaml
    depends_on:
      backend:
        condition: service_healthy
```

**Ordre de demarrage avec condition.** Le frontend ne demarre PAS tant que le backend n'est pas "healthy" (c'est-a-dire que son health check a reussi au moins une fois).

Pourquoi ? Si le frontend demarre avant que le backend soit pret, les premieres requetes de l'utilisateur echoueraient. `service_healthy` (au lieu de `service_started`) garantit que le backend est non seulement demarre mais aussi **operationnel**.

---

## 5. Caddy -- le reverse proxy pour le cloud

### 5.1 C'est quoi un reverse proxy ?

En local, tu accedes a tes services directement :
- Backend : `http://localhost:8001`
- Frontend : `http://localhost:8080`

En production (cloud), tu veux :
- Un vrai nom de domaine (`chat.tonsite.com` au lieu de `http://123.45.67.89:8080`)
- Du HTTPS (certificat SSL) -- obligatoire pour la securite et le SEO
- Un seul point d'entree pour tout

C'est le role du **reverse proxy** :

```
          Internet
             │
             ▼
    ┌─────────────────┐
    │   Caddy          │
    │   :80 (HTTP)     │
    │   :443 (HTTPS)   │
    └────┬────────┬────┘
         │        │
         ▼        ▼
  ┌──────────┐  ┌──────────┐
  │ backend  │  │ frontend │
  │  :8001   │  │  :8080   │
  └──────────┘  └──────────┘

  api.tonsite.com  →  backend:8001
  chat.tonsite.com →  frontend:8080
```

L'utilisateur tape `https://chat.tonsite.com`. Caddy :
1. Recoit la requete sur le port 443 (HTTPS)
2. Verifie le nom de domaine
3. La transmet au container `frontend` sur le port 8080
4. Renvoie la reponse au client

Le gros avantage de Caddy : **SSL automatique via Let's Encrypt**. Il obtient et renouvelle les certificats HTTPS sans aucune configuration. Avec nginx ou Apache, c'est une galere de certbot + cron jobs.

### 5.2 `Caddyfile`

```
{
    email {$LETSENCRYPT_EMAIL}
}
```

**Bloc global.** Let's Encrypt a besoin d'une adresse email pour envoyer des notifications (expiration de certificat, problemes). `{$LETSENCRYPT_EMAIL}` est remplace par la variable d'environnement du meme nom.

```
{$AGENT_API_HOSTNAME} {
    request_body {
        max_size 10MB
    }
    reverse_proxy backend:8001
}
```

**Bloc pour l'API.** `{$AGENT_API_HOSTNAME}` = `api.tonsite.com` par exemple.
- `request_body max_size 10MB` : limite la taille des requetes a 10 Mo. Protege contre les abus (quelqu'un qui enverrait un fichier de 5 Go pour saturer ton serveur).
- `reverse_proxy backend:8001` : toutes les requetes vers `api.tonsite.com` sont transmises au container `backend` sur le port 8001. Docker Compose met tous les containers sur un reseau interne -- Caddy peut atteindre le backend par son nom de service (`backend`).

Le deuxieme bloc est identique pour le frontend (`{$FRONTEND_HOSTNAME}` -> `frontend:8080`).

**Ce que Caddy fait automatiquement :**
- Detecte que `api.tonsite.com` est un vrai domaine (pas `localhost`)
- Contacte Let's Encrypt pour obtenir un certificat SSL
- Configure HTTPS
- Redirige HTTP -> HTTPS
- Renouvelle le certificat avant expiration

Zero lignes de config pour tout ca.

### 5.3 `docker-compose.caddy.yml`

```yaml
services:
  caddy:
    image: caddy:2-alpine
    container_name: ai-nutrition-caddy
    restart: always
```

Ce fichier est un **overlay** Docker Compose. Il ne remplace pas `docker-compose.yml`, il s'y **ajoute**. Quand tu lances :

```bash
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up
```

Docker **fusionne** les deux fichiers. Les 3 services du fichier principal + le service Caddy de l'overlay = 4 services au total.

```yaml
    ports:
      - "80:80"
      - "443:443"
```

Ports standard du web :
- 80 : HTTP (Caddy redirige automatiquement vers HTTPS)
- 443 : HTTPS

```yaml
    expose:
      - "2019"
      - "443/udp"
```

- `2019` : API d'administration de Caddy (interne seulement, pas expose a l'exterieur)
- `443/udp` : pour HTTP/3 (QUIC), le nouveau protocole web plus rapide

`expose` vs `ports` : `expose` rend le port visible aux autres containers du meme reseau Docker, mais PAS a l'exterieur. `ports` expose a l'exterieur.

```yaml
    environment:
      - AGENT_API_HOSTNAME=${AGENT_API_HOSTNAME:-":8001"}
      - FRONTEND_HOSTNAME=${FRONTEND_HOSTNAME:-":8080"}
      - LETSENCRYPT_EMAIL=${LETSENCRYPT_EMAIL:-internal}
```

Variables passees a Caddy. Les valeurs par defaut (`:8001`, `:8080`) sont pour le dev local -- Caddy ecoute directement sur ces ports sans SSL. En prod, tu mets des vrais domaines.

```yaml
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data:rw
      - caddy_config:/config:rw
```

- `Caddyfile:ro` : monte la config en lecture seule (`:ro`). Le container peut la lire mais pas la modifier.
- `caddy_data` : volume nomme pour stocker les certificats SSL. Persiste entre les redemarrages -- sinon Caddy devrait redemander un certificat a chaque restart (Let's Encrypt a des rate limits).
- `caddy_config` : configuration generee par Caddy.

```yaml
    depends_on:
      - backend
      - frontend
```

Caddy demarre apres le backend et le frontend (logique -- il ne peut pas rediriger vers des services qui n'existent pas encore).

```yaml
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

**Capabilities Linux (securite avancee) :**
- `cap_drop ALL` : retire **toutes** les permissions speciales au container (modifier le systeme, charger des modules noyau, changer les permissions, etc.)
- `cap_add NET_BIND_SERVICE` : re-ajoute **uniquement** la permission de se lier aux ports < 1024 (ports 80 et 443).

Resultat : meme si quelqu'un compromet Caddy, il ne peut quasiment rien faire sur le systeme.

```yaml
    logging:
      driver: "json-file"
      options:
        max-size: "1m"
        max-file: "1"
```

Limite les logs a 1 Mo maximum. Sans ca, les logs Caddy pourraient remplir ton disque.

```yaml
volumes:
  caddy_data:
  caddy_config:
```

Declaration des volumes nommes. Docker les cree et les gere automatiquement. Ils survivent aux `docker compose down` (mais pas a `docker compose down -v` qui supprime aussi les volumes).

---

## 6. `deploy.py` -- le script de deploiement

`deploy.py` est un **wrapper de commodite** autour de `docker compose`. Il ne fait rien de magique -- il simplifie la commande a taper.

### Comparaison

```bash
# Sans deploy.py :
docker compose -p ai-nutrition -f docker-compose.yml up -d --build

# Avec deploy.py :
python deploy.py --type local
```

```bash
# Sans deploy.py (cloud avec Caddy) :
docker compose -p ai-nutrition -f docker-compose.yml -f docker-compose.caddy.yml up -d --build

# Avec deploy.py :
python deploy.py --type cloud
```

```bash
# Arreter :
docker compose -p ai-nutrition -f docker-compose.yml down

# Avec deploy.py :
python deploy.py --down --type local
```

### Ce qu'il ajoute

1. **Validation** : verifie que tous les fichiers necessaires existent avant de lancer. Si `Dockerfile` manque, tu as une erreur claire au lieu d'une stacktrace Docker.

2. **`--type local` vs `--type cloud`** :
   - `local` : seulement `docker-compose.yml` (3 services, acces direct sur localhost)
   - `cloud` : ajoute `docker-compose.caddy.yml` en overlay (4 services, avec Caddy pour SSL)

3. **`--down`** : arrete tout proprement.

4. **`--env-file`** : permet de specifier un fichier d'environnement alternatif (ex : `".env prod"`).

5. **Resume a la fin** :
   ```
   Services:
     Backend API:   http://localhost:8001
     Frontend:      http://localhost:8080
     RAG Pipeline:  running (no exposed port)

   Useful commands:
     docker compose -p ai-nutrition logs -f
     docker compose -p ai-nutrition ps
     python deploy.py --down --type local
   ```

---

## 7. `.env.example` -- les variables d'environnement

### Comment les variables circulent

```
┌──────────┐     ┌───────────────────┐     ┌─────────────┐
│  .env    │ ──> │ docker-compose.yml │ ──> │  Container  │
│ (secrets)│     │ ${VAR:-default}    │     │ (env vars)  │
└──────────┘     └───────────────────┘     └─────────────┘
```

1. Tu copies `.env.example` vers `.env` et tu remplis tes vraies valeurs (cles API, URLs, etc.)
2. `docker compose up` lit automatiquement le fichier `.env` dans le dossier courant
3. `docker-compose.yml` utilise la syntaxe `${VAR:-default}` pour injecter chaque variable dans le bon container
4. Le container recoit la variable comme une variable d'environnement classique (`os.environ["VAR"]` en Python)

### Cas special : variables frontend

Pour le frontend, le flux est plus long :

```
.env (VITE_SUPABASE_URL=...)
  │
  ▼
docker-compose.yml  →  build.args  →  VITE_SUPABASE_URL
  │
  ▼
Dockerfile          →  ARG VITE_SUPABASE_URL
                    →  ENV VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
  │
  ▼
npm run build       →  Vite lit process.env.VITE_SUPABASE_URL
                    →  Remplace dans le code JS : import.meta.env.VITE_SUPABASE_URL
  │
  ▼
dist/index.js       →  La valeur est FIGEE dans le JavaScript compile
```

C'est pourquoi modifier une variable `VITE_*` dans `.env` necessite un **rebuild** de l'image (`docker compose up --build`), pas juste un restart.

### Sections du `.env.example`

Le fichier est organise en sections documentees :

| Section | Variables principales | Obligatoire ? |
|---------|----------------------|---------------|
| LLM Configuration | `LLM_API_KEY`, `LLM_CHOICE`, `ANTHROPIC_API_KEY` | Oui |
| Embedding Configuration | `EMBEDDING_API_KEY`, `EMBEDDING_MODEL_CHOICE` | Oui |
| Database Configuration | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `DATABASE_URL` | Oui |
| Web Search | `BRAVE_API_KEY` ou `SEARXNG_BASE_URL` | Au moins un |
| API Configuration | `CORS_ORIGINS`, `LOG_LEVEL` | Defauts OK |
| Observability | `LANGFUSE_*` | Non (optionnel) |
| RAG Pipeline | `RAG_PIPELINE_TYPE`, `RUN_MODE` | Defauts OK |
| Google Drive | `GOOGLE_DRIVE_CREDENTIALS_JSON` | Non (si local) |
| Frontend | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | Oui |
| Reverse Proxy | `AGENT_API_HOSTNAME`, `FRONTEND_HOSTNAME` | Seulement cloud |

---

## 8. Comment tout s'assemble -- le flux complet

Voici ce qui se passe quand tu lances `python deploy.py --type local` :

### Etape 1 : Validation
```
deploy.py verifie que ces fichiers existent :
  ✓ docker-compose.yml
  ✓ Dockerfile
  ✓ frontend/Dockerfile
  ✓ src/RAG_Pipeline/Dockerfile
```

### Etape 2 : Commande Docker
```
deploy.py execute :
  docker compose -p ai-nutrition -f docker-compose.yml up -d --build

  -p ai-nutrition     → nom du projet (prefixe pour les containers)
  -f docker-compose.yml → fichier de configuration
  up                   → demarrer les services
  -d                   → en arriere-plan (detached)
  --build              → reconstruire les images si necessaire
```

### Etape 3 : Docker lit la config
```
docker-compose.yml + .env sont lus.
Docker decouvre 3 services : backend, rag-pipeline, frontend.
```

### Etape 4 : Build des images (pour chaque service)

```
Pour chaque service :
  a. Lit le .dockerignore correspondant
     → Backend : .dockerignore (racine)
     → Frontend : frontend/.dockerignore
     → RAG : src/RAG_Pipeline/.dockerignore

  b. Envoie le build context au daemon Docker
     (seulement les fichiers non-ignores)

  c. Execute le Dockerfile ligne par ligne
     Chaque ligne = une "couche" (layer)

     Si requirements.txt n'a pas change depuis le dernier build :
       → Docker reutilise les couches "COPY requirements.txt" + "pip install" du cache
       → Seules les couches "COPY src/" et suivantes sont reconstruites
       → Build en ~5 secondes au lieu de ~3 minutes

  d. Cree une image taguee avec le nom du service
```

### Etape 5 : Creation des containers

```
Docker cree un container a partir de chaque image.
Injecte les variables d'environnement.
Configure les ports, volumes, health checks.
```

### Etape 6 : Demarrage dans l'ordre

```
1. backend      → demarre en premier
   │               (uvicorn charge FastAPI + modeles)
   │               attend ~30-40s
   │
   ├─ health check passe ✓ (curl /health → 200 OK)
   │
   ▼
2. frontend     → demarre (condition: backend healthy)
   │               (nginx demarre quasi instantanement)
   │
3. rag-pipeline → demarre en parallele du frontend
                   (pas de depends_on, demarre des que possible)
```

### Etape 7 : Tout est accessible

```
  Backend API   →  http://localhost:8001
  Frontend      →  http://localhost:8080
  RAG Pipeline  →  tourne en arriere-plan (pas de port)
```

---

## 9. Commandes utiles

| Commande | Description |
|----------|-------------|
| `docker ps` | Liste les containers en cours d'execution (nom, status, ports, uptime) |
| `docker compose -p ai-nutrition ps` | Pareil mais filtre sur notre projet |
| `docker logs ai-nutrition-backend` | Affiche les logs du backend (stdout/stderr) |
| `docker logs ai-nutrition-backend --tail 50` | Les 50 dernieres lignes seulement |
| `docker compose -p ai-nutrition logs -f` | Suit les logs de TOUS les services en temps reel (`-f` = follow) |
| `docker compose -p ai-nutrition logs -f backend` | Suit les logs d'un seul service |
| `docker exec -it ai-nutrition-backend bash` | Ouvre un terminal interactif DANS le container (pour debugger) |
| `docker compose -p ai-nutrition up -d --build` | Rebuild et redemarrer tous les services |
| `docker compose -p ai-nutrition up -d --build frontend` | Rebuild et redemarrer seulement le frontend |
| `docker compose -p ai-nutrition down` | Arrete et supprime tous les containers (les volumes persistent) |
| `docker compose -p ai-nutrition down -v` | Idem + supprime les volumes (perte de donnees !) |
| `docker compose -p ai-nutrition restart backend` | Redemarrer un service sans rebuild |
| `docker system prune` | Supprime les images/containers/caches inutilises (libere de l'espace disque) |
| `docker system prune -a` | Supprime TOUT ce qui n'est pas utilise (images incluses) -- libere beaucoup d'espace |
| `docker stats` | Moniteur temps reel : CPU, RAM, reseau de chaque container |
| `docker inspect ai-nutrition-backend` | Details complets du container (config, reseau, volumes, env vars...) |

---

## 10. Pourquoi ces choix techniques ?

| Choix | Pourquoi |
|-------|----------|
| `python:3.11-slim` | 150 Mo au lieu de 900 Mo (image full). On installe seulement ce dont on a besoin. |
| Multi-stage frontend | Image finale de ~30 Mo au lieu de ~1 Go. Node.js et node_modules ne sont pas dans l'image finale -- seulement les fichiers HTML/JS/CSS compiles + nginx. |
| Utilisateur non-root | Securite -- si un attaquant exploite une faille dans l'appli, il n'a pas les droits administrateur dans le container. Limite les degats. |
| Layer caching (ordre des COPY) | `COPY requirements.txt` avant `COPY src/` = si le code change mais pas les dependances, `pip install` est reutilise du cache. Rebuild en 5s au lieu de 3 minutes. |
| `.dockerignore` | Build context petit (~5 Mo au lieu de 500+ Mo). Build plus rapide. Et surtout : empeche les secrets (`.env`) de se retrouver dans l'image. |
| Health checks | Docker sait si un container est vivant ou mort. Permet le redemarrage automatique (`restart: always`) et l'ordering (`depends_on: condition: service_healthy`). |
| Caddy | SSL automatique via Let's Encrypt, zero configuration. Alternative : nginx + certbot + cron = 50 lignes de config. Avec Caddy : 15 lignes. |
| 3 containers separes | Chacun peut crash/restart/scale independamment. Le backend peut etre mis a jour sans toucher au frontend. La pipeline RAG peut crash sans affecter les utilisateurs. |
| `PYTHONUNBUFFERED=1` | Les logs apparaissent immediatement dans `docker logs`. Sans ca, Python bufferise et tu vois les logs avec du retard (ou pas du tout si crash). |
| `dumb-init` (frontend) | Gestion correcte des signaux. `docker stop` envoie SIGTERM, `dumb-init` le transmet a nginx, nginx s'arrete proprement. Sans ca, Docker attend 10s puis force-kill. |
| `npm ci` au lieu de `npm install` | Deterministe : utilise le lockfile exactement. Tout le monde obtient les memes versions. Pas de surprises. |
| Volumes (RAG) | Les documents a ingerer persistent meme si le container est detruit. Tu ne perds pas tes fichiers. |
| `cap_drop ALL` (Caddy) | Principe du moindre privilege. Caddy n'a besoin que de se lier aux ports 80/443 -- on retire toutes les autres permissions systeme. |
