#!/usr/bin/env bash
# Run as root from an unpacked release directory, after installing nginx/python3-venv.
set -euo pipefail
release=$(pwd -P)
case "$release" in /srv/apps/patientfollowup/releases/*) ;; *) echo "Unexpected release directory"; exit 1;; esac

if ! id patientfollowup >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/patientfollowup --shell /usr/sbin/nologin patientfollowup
fi
install -d -o root -g patientfollowup -m 0750 /etc/patientfollowup
install -d -o patientfollowup -g patientfollowup -m 0700 /var/lib/patientfollowup
install -d -o patientfollowup -g patientfollowup -m 0700 /var/lib/patientfollowup/uploads
for directory in clinical patient intake backups; do
    if [ "$directory" = backups ]; then
        install -d -o patientfollowup -g patientfollowup -m 0700 /var/lib/patientfollowup/backups
    else
        install -d -o patientfollowup -g patientfollowup -m 0700 "/var/lib/patientfollowup/uploads/$directory"
    fi
done

if [ ! -f /etc/patientfollowup/app.env ]; then
    python3 - <<'PY'
import os, secrets
from urllib.parse import urlsplit
public_url = os.environ.get('DEPLOY_PUBLIC_BASE_URL', '').rstrip('/')
parsed = urlsplit(public_url)
if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != '/patientfollowup':
    raise SystemExit('Set DEPLOY_PUBLIC_BASE_URL to the public origin plus /patientfollowup before the first installation.')
fd = os.open('/etc/patientfollowup/app.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
with os.fdopen(fd, 'w') as output:
    output.write('APP_ENV=trial\nAPP_NAME=patient-follow-up-system\nLOG_LEVEL=INFO\n')
    output.write('DATABASE_URL=sqlite:////var/lib/patientfollowup/app.db\n')
    output.write('AUTH_SECRET_KEY=' + secrets.token_urlsafe(48) + '\n')
    output.write('ACCESS_TOKEN_EXPIRE_MINUTES=30\nMODEL_ENABLED=false\n')
    output.write('LANGCHAIN_TRACING_V2=false\n')
    output.write('CLINICAL_UPLOAD_DIR=/var/lib/patientfollowup/uploads/clinical\n')
    output.write('PATIENT_UPLOAD_DIR=/var/lib/patientfollowup/uploads/patient\n')
    output.write('INTAKE_UPLOAD_DIR=/var/lib/patientfollowup/uploads/intake\n')
    output.write('PUBLIC_BASE_URL=' + public_url + '\n')
PY
    chown root:patientfollowup /etc/patientfollowup/app.env
fi

# Windows-created archive entries can have permissive Unix mode bits.
# Application service users must not be able to modify root-owned release code.
chmod -R go-w "$release"

python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check --retries 2 --timeout 30 -r requirements-deploy.txt -i https://mirrors.aliyun.com/pypi/simple/
set -a
source /etc/patientfollowup/app.env
set +a
export PYTHONPATH="$release/src"
if [ -f /var/lib/patientfollowup/app.db ]; then
    .venv/bin/python deploy/linux/backup.py
fi
.venv/bin/alembic upgrade head
.venv/bin/python deploy/linux/bootstrap_accounts.py
chown -R patientfollowup:patientfollowup /var/lib/patientfollowup
chmod -R o-rwx /var/lib/patientfollowup

ln -sfn "$release" /srv/apps/patientfollowup/current
install -m 0644 deploy/linux/patientfollowup.service /etc/systemd/system/
install -m 0644 deploy/linux/patientfollowup-backup.service /etc/systemd/system/
install -m 0644 deploy/linux/patientfollowup-backup.timer /etc/systemd/system/
install -d -m 0755 /etc/nginx/project-locations
install -m 0644 deploy/linux/patientfollowup.nginx.conf /etc/nginx/project-locations/patientfollowup.conf

# One shared HTTP listener; add future projects as separate location snippets.
if [ ! -f /etc/nginx/sites-available/projects ]; then
    cat > /etc/nginx/sites-available/projects <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    server_tokens off;
    include /etc/nginx/project-locations/*.conf;
    location / { return 404; }
}
NGINX
fi
if [ -L /etc/nginx/sites-enabled/default ] && [ "$(readlink -f /etc/nginx/sites-enabled/default)" = /etc/nginx/sites-available/default ]; then
    unlink /etc/nginx/sites-enabled/default
fi
ln -sfn /etc/nginx/sites-available/projects /etc/nginx/sites-enabled/projects
nginx -t
systemctl daemon-reload
systemctl enable patientfollowup.service patientfollowup-backup.timer nginx.service
systemctl restart patientfollowup.service
systemctl start patientfollowup-backup.timer
systemctl reload nginx
echo 'Deployment installed; check /patientfollowup/health and service status.'
