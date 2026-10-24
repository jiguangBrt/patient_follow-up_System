#!/usr/bin/env bash
# Run only after a trusted IP certificate has been issued.
set -euo pipefail
source_dir=/srv/apps/patientfollowup/current/deploy/linux
public_url=$(sed -n 's/^PUBLIC_BASE_URL=//p' /etc/patientfollowup/app.env)
public_ip=$(python3 -c 'import ipaddress,sys; from urllib.parse import urlsplit; print(ipaddress.IPv4Address(urlsplit(sys.argv[1]).hostname))' "$public_url")
certificate="/etc/letsencrypt/live/$public_ip/fullchain.pem"
test -f "$certificate"
openssl x509 -in "$certificate" -noout -checkip "$public_ip"
openssl x509 -in "$certificate" -noout -checkend 3600
install -d -m 0700 /etc/patientfollowup/https-rollback
cp -p /etc/nginx/sites-available/projects /etc/patientfollowup/https-rollback/projects
cp -p /etc/patientfollowup/app.env /etc/patientfollowup/https-rollback/app.env
rollback() {
    cp -p /etc/patientfollowup/https-rollback/projects /etc/nginx/sites-available/projects
    cp -p /etc/patientfollowup/https-rollback/app.env /etc/patientfollowup/app.env
    nginx -t && systemctl reload nginx
    systemctl restart patientfollowup
}
trap rollback ERR
PUBLIC_IP="$public_ip" python3 - <<'PY'
import os
from pathlib import Path
source = Path('/srv/apps/patientfollowup/current/deploy/linux/projects-https.nginx.conf')
Path('/etc/nginx/sites-available/projects').write_text(source.read_text().replace('__PUBLIC_IP__', os.environ['PUBLIC_IP']))
PY
nginx -t
sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://$public_ip/patientfollowup|" /etc/patientfollowup/app.env
systemctl restart patientfollowup
systemctl reload nginx
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
install -m 0755 "$source_dir/certbot-reload-nginx.sh" /etc/letsencrypt/renewal-hooks/deploy/reload-nginx
install -m 0644 "$source_dir/certbot-renew.service" /etc/systemd/system/
install -m 0644 "$source_dir/certbot-renew.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now certbot-renew.timer
trap - ERR
echo 'HTTPS configuration activated; verify externally and test certificate renewal.'
