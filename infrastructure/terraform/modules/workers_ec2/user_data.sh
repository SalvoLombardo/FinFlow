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
