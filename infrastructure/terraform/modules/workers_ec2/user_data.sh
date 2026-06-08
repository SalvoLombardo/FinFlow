#!/bin/bash
set -e

# Update system packages
yum update -y

# Install Docker
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# Install Docker Compose v2 (plugin)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose

# Create app directory — CI/CD (Phase 7) will clone the repo here
mkdir -p /opt/${project}
chown ec2-user:ec2-user /opt/${project}

# ---------------------------------------------------------------
# TLS for PostgreSQL — encrypts the wire between Lambda/backend and this
# publicly-reachable instance. The long random password alone doesn't stop
# passive sniffing of credentials/data in transit (the actual highest-severity
# risk of the public-Postgres trade-off — see PRODUCTION_READINESS.md "public
# Postgres" finding). Self-signed because there's no private CA in this $0
# setup; clients connect with sslmode=require / ssl=<unverified context> —
# i.e. encrypt, don't verify identity (matching libpq's "require" semantics,
# the realistic option without a CA distribution mechanism).
# ---------------------------------------------------------------
mkdir -p /opt/${project}/certs
openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
  -keyout /opt/${project}/certs/server.key \
  -out /opt/${project}/certs/server.crt \
  -subj "/CN=${project}-${environment}-postgres"
# The official postgres image runs as the `postgres` user (uid/gid 999) and
# refuses to start if its private key is group/world-readable.
chown 999:999 /opt/${project}/certs/server.key /opt/${project}/certs/server.crt
chmod 600 /opt/${project}/certs/server.key
chmod 644 /opt/${project}/certs/server.crt

# Write docker-compose for infrastructure services (PostgreSQL + Redis).
# Values below are injected by Terraform templatefile at apply time —
# the single-quoted heredoc markers prevent bash from re-expanding them.
cat > /opt/${project}/docker-compose.infra.yml <<'INFRA_EOF'
version: '3.8'
services:
  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: ${db_username}
      POSTGRES_PASSWORD: ${db_password}
      POSTGRES_DB: ${db_name}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - /opt/${project}/certs/server.crt:/var/lib/postgresql/server.crt:ro
      - /opt/${project}/certs/server.key:/var/lib/postgresql/server.key:ro
    command:
      - "-c"
      - "ssl=on"
      - "-c"
      - "ssl_cert_file=/var/lib/postgresql/server.crt"
      - "-c"
      - "ssl_key_file=/var/lib/postgresql/server.key"
      - "-c"
      - "log_connections=on"
      - "-c"
      - "log_destination=stderr"
    logging:
      driver: awslogs
      options:
        awslogs-region: "${aws_region}"
        awslogs-group: "${log_group_name}"
        awslogs-stream: postgres

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --requirepass ${db_password} --bind 0.0.0.0
    ports:
      - "6379:6379"

volumes:
  pgdata:
INFRA_EOF

# Start PostgreSQL and Redis immediately
cd /opt/${project}
docker compose -f docker-compose.infra.yml up -d

# Pre-populate .env for Celery workers deployed by CI/CD in Phase 7.
# Celery connects to localhost since it runs on this same EC2 instance.
cat > /opt/${project}/.env <<'DOTENV_EOF'
DATABASE_URL=postgresql+asyncpg://${db_username}:${db_password}@localhost:5432/${db_name}
CELERY_BROKER_URL=redis://:${db_password}@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:${db_password}@localhost:6379/1
KAFKA_BOOTSTRAP_SERVERS=
KAFKA_AUDIT_TOPIC=finflow.audit
AWS_SNS_TOPIC_ARN=__FILL_FROM_TERRAFORM_OUTPUT__
SECRET_KEY=__FILL_FROM_SSM__
ENCRYPTION_KEY=__FILL_FROM_SSM__
S3_AUDIT_BUCKET=__FILL_FROM_TERRAFORM_OUTPUT__
DOTENV_EOF

echo "Bootstrap complete — PostgreSQL and Redis running. Deploy Celery workers via CI/CD (Phase 7)."
