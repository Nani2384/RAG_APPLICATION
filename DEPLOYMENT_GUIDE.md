# Nexus RAG Production Deployment Guide

This guide provides a comprehensive, step-by-step walkthrough for deploying the Nexus RAG platform in a hardened, production-ready environment using Docker Compose, Nginx, and Let's Encrypt SSL.

---

## 🏗️ 1. Production Architecture Overview

In a production environment, the Nexus RAG architecture is structured to enforce the principle of least privilege, optimize performance, and guarantee secure communications:

```
                      ┌────────────────────────────────────────┐
                      │             Internet User              │
                      └───────────────────┬────────────────────┘
                                          │ (Port 80/443: HTTPS)
                                          ▼
                      ┌────────────────────────────────────────┐
                      │          Nginx Reverse Proxy           │
                      │   • SSL Termination (Let's Encrypt)    │
                      │   • SSE Stream Buffer Bypassing        │
                      │   • Hardened Security Headers          │
                      └───────────┬────────────────┬───────────┘
                                  │ (Routing)      │ (Routing)
                                  ▼                ▼
         ┌────────────────────────┐        ┌────────────────────────┐
         │  rag_frontend_prod     │        │  rag_api_prod          │
         │  • Next.js Server      │        │  • FastAPI Application │
         │  • Port 3000 (Internal)│        │  • Port 8000 (Internal)│
         └────────────────────────┘        └───────────┬────────────┘
                                                       │
                                     ┌─────────────────┴─────────────────┐
                                     ▼                                   ▼
                      ┌────────────────────────┐          ┌────────────────────────┐
                      │  rag_celery_worker     │          │  rag_postgres_prod     │
                      │  • Ingestion & FAISS   │          │  • PostgreSQL DB       │
                      │  • Shared Vector Vol   │          │  • Port 5432 (Internal)│
                      └───────────┬────────────┘          └────────────────────────┘
                                  │
                                  ▼
                      ┌────────────────────────┐
                      │  rag_redis_prod        │
                      │  • Celery Message Broker│
                      │  • Port 6379 (Internal)│
                      └────────────────────────┘
```

### Key Security & Architectural Features:
- **Port Isolation**: Database (PostgreSQL) and Cache/Broker (Redis) ports are not exposed to the public host. They are only reachable via the Docker bridge network.
- **Immutable Containers**: No developer volume mounts (`./backend:/app` or `./frontend:/app`) are configured in production. Containers are fully built and static.
- **SSE Tuning**: Nginx is optimized to disable proxy buffering (`proxy_buffering off`) for instantaneous, character-by-character Server-Sent Events (SSE) chat streaming.
- **Robust Healthchecks**: Redis, Postgres, and FastAPI have active health checks to ensure dependencies are fully ready before child services initiate.

---

## ⚙️ 2. Environment Configuration

Create a file named `.env.production` in the root of the project `/Users/saipavan/rag_application/.env.production`. This file will hold secure, environment-specific secrets.

> [!WARNING]
> Never commit the `.env.production` file to version control. Keep it securely backed up in your secret manager.

### `.env.production` Example Template
```ini
# --- Core Environment ---
ENV=production
SECRET_KEY=generate-a-secure-random-64-character-string-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# --- Database Credentials ---
POSTGRES_USER=nexus_db_admin
POSTGRES_PASSWORD=use-a-strong-random-password-here
POSTGRES_DB=nexus_rag_production
DATABASE_URL=postgresql+asyncpg://nexus_db_admin:use-a-strong-random-password-here@db:5432/nexus_rag_production

# --- Redis Broker Connection ---
REDIS_URL=redis://redis:6379/0

# --- RAG Configs & AI API Credentials ---
OPENAI_API_KEY=sk-proj-your-actual-production-openai-api-key-here
EMBEDDING_MODEL=text-embedding-3-small
FAISS_INDEX_PATH=/app/storage/faiss_index

# --- API Rate Limiter Setup ---
RATE_LIMIT_CALLS=15
RATE_LIMIT_PERIOD_SECONDS=60
```

---

## 🚀 3. Step-by-Step Initial Deployment

Follow these sequential steps to perform a fresh, secure production deployment.

### Step 3.1: Prepare the Target Host
Ensure Docker and Docker Compose are installed on your production VM (Ubuntu, Debian, macOS, or RHEL):
```bash
# Check Docker version
docker --version
# Check Compose version
docker compose version
```

### Step 3.2: Create Directories and Copy Configuration
Copy the project code to your server's deployment directory (e.g., `/var/www/nexus-rag`). Ensure the `nginx.conf`, `docker-compose.prod.yml`, and your `.env.production` are in place.

### Step 3.3: Perform Initial Image Build
Build the optimized frontend and backend production images. This uses multi-stage builds and pulls optimized dependencies:
```bash
docker compose -f docker-compose.prod.yml build
```

### Step 3.4: Boot the Environment in Detached Mode
Launch the service group. The dependencies (`db` and `redis`) will boot first and report `healthy` before the API and Celery worker launch:
```bash
docker compose -f docker-compose.prod.yml up -d
```

### Step 3.5: Apply Alembic Database Migrations
Run Alembic schema migrations directly inside the production API container to initialize or upgrade the database schema:
```bash
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

### Step 3.6: Verify Container Health
Check the container status to make sure all 6 services are up and healthy:
```bash
docker compose -f docker-compose.prod.yml ps
```

---

## 🔒 4. Let's Encrypt SSL & HTTPS Configuration

To secure communication between clients and your Nginx reverse proxy, you must configure TLS (HTTPS).

### Step 4.1: Install Certbot on the Host Machine
On your host server (e.g. Ubuntu):
```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx -y
```

### Step 4.2: Modify `nginx.conf` to handle HTTP validation
Certbot needs to respond to a challenge at `http://yourdomain.com/.well-known/acme-challenge/`.
Ensure your Nginx configuration in `nginx.conf` exposes port 80 and maps the location. (For a clean start, you can temporarily allow let's encrypt to run standalone or map the folder).

Run Certbot to fetch certificates:
```bash
sudo certbot certonly --webroot -w /var/www/html -d yourdomain.com -d www.yourdomain.com
```

### Step 4.3: Secure the Certificate Volume Mounts
The generated certificates will reside at `/etc/letsencrypt/live/yourdomain.com/`.
The `docker-compose.prod.yml` mounts `/etc/letsencrypt:/etc/letsencrypt:ro` so Nginx can access the public certificate and private keys.

### Step 4.4: Update `nginx.conf` for Production HTTPS
Update the `server` block in your `nginx.conf` to serve TLS. Replace the existing server block with:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Certificate Paths
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Strong SSL Protocol Hardening
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';

    # Limit Upload Size (matches MAX_UPLOAD_SIZE_MB setting)
    client_max_body_size 50M;

    # Hardened Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline' 'unsafe-eval';" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # API Reverse Proxy Route (strip /api prefix)
    location /api/ {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://api:8000;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Core Streaming & SSE Optimization
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 24h;
    }

    # Next.js Frontend Proxy Route
    location / {
        proxy_pass http://frontend:3000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Next.js websockets support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Reload Nginx to apply the changes:
```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### Step 4.5: Automatic SSL Certificate Renewal
Configure a daily cron job to run the Certbot renewal script and reload Nginx:
```bash
sudo crontab -e
```
Add the following line to run every day at 3 AM:
```cron
0 3 * * * certbot renew --quiet && docker compose -f /var/www/nexus-rag/docker-compose.prod.yml exec -T nginx nginx -s reload
```

---

## 🔄 5. Continuous Integration / Continuous Deployment (CI/CD)

For automated production deployments, integrate the following steps into your CI/CD pipelines (e.g., GitHub Actions, GitLab CI):

1. **Lint & Test**: Run the automated test suites inside short-lived containers.
   ```bash
   docker compose -f docker-compose.yml run --entrypoint "pytest -v tests/" api
   ```
2. **Build and Tag**: Build Docker images tagged with the commit SHA and push to your container registry (e.g., Docker Hub, AWS ECR, GCP GCR).
3. **Deploy**: Update target host environments, pulling the new images and restarting services gracefully:
   ```bash
   docker compose -f docker-compose.prod.yml pull
   docker compose -f docker-compose.prod.yml up -d --no-deps api worker frontend
   docker compose -f docker-compose.prod.yml exec api alembic upgrade head
   ```

---

## 📊 6. Health Checks & Verification Runbook

To confirm a successful, high-quality installation:

| Service | Protocol | Local Internal URL | Expected Health Check |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | TCP | `db:5432` | `pg_isready -U postgres` returns `0` |
| **Redis** | TCP | `redis:6379` | `redis-cli ping` returns `PONG` |
| **FastAPI API** | HTTP | `api:8000` | `GET /health` returns `{"status":"healthy"}` |
| **Frontend** | HTTP | `frontend:3000`| `GET /` returns HTML `200 OK` |
| **Nginx Proxy** | HTTP/S | `nginx:80` / `nginx:443` | Passes browser E2E test flows |
