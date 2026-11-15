#!/bin/bash
# Deploy or update Evident on the API server (run as root, e.g. through SSM Run Command):
#   bash /opt/evident/deploy/deploy.sh [git-ref]        default ref: main
# Secrets come from SSM Parameter Store (/evident/*) into a root-only .env; never from the repo.
set -euo pipefail

REF="${1:-main}"
APP=/opt/evident
REPO=https://github.com/aadilsal/Evident.git
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-ap-southeast-2}"
COMPOSE=(docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml)

[ -d "$APP/.git" ] || git clone --quiet "$REPO" "$APP"
cd "$APP"
git fetch --quiet --tags origin
git checkout --quiet --force "$REF"
git reset --quiet --hard "origin/$REF" 2>/dev/null || true  # branches track origin; tags stay put
echo "deploying $(git rev-parse --short HEAD) ($REF)"

umask 077
aws ssm get-parameters-by-path --path /evident/ --with-decryption \
  --query 'Parameters[].[Name,Value]' --output text |
  while IFS=$'\t' read -r name value; do printf '%s=%s\n' "${name##*/}" "$value"; done > .env.new
grep -q '^GROQ_API_KEY=' .env.new || echo 'EVIDENT_LLM=off' >> .env.new
mv .env.new .env

"${COMPOSE[@]}" up -d --build --remove-orphans
docker image prune -f >/dev/null

# Nightly pg_dump to S3 (bucket evident-backups-<account>, 30-day expiry).
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
cat > /usr/local/bin/evident-backup <<EOF
#!/bin/bash
set -euo pipefail
cd $APP
${COMPOSE[*]} exec -T postgres pg_dump -U evident -Fc evident \
  | aws s3 cp - "s3://evident-backups-$ACCOUNT/pg/\$(date -u +%F).dump" --region $AWS_DEFAULT_REGION
EOF
chmod 700 /usr/local/bin/evident-backup
cat > /etc/systemd/system/evident-backup.service <<'EOF'
[Unit]
Description=Evident Postgres backup to S3
[Service]
Type=oneshot
ExecStart=/usr/local/bin/evident-backup
EOF
cat > /etc/systemd/system/evident-backup.timer <<'EOF'
[Unit]
Description=Nightly Evident backup
[Timer]
OnCalendar=*-*-* 03:15:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now evident-backup.timer >/dev/null

"${COMPOSE[@]}" ps --format 'table {{.Service}}\t{{.Status}}'
