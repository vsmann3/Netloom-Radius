#!/bin/sh
# Initial HTTPS provisioning for radius.netnoc.in on the Ubuntu VM.
set -eu
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo" >&2; exit 1; }
cd "$(dirname "$0")/.."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y nginx certbot
install -d -m 0755 /var/www/netloom-acme /etc/letsencrypt/renewal-hooks/deploy
site=/etc/nginx/sites-available/netloom-radius
if [ ! -s /etc/letsencrypt/live/radius.netnoc.in/fullchain.pem ]; then
    install -m 0644 deploy/nginx/radius-http.conf "$site"
    ln -sfn "$site" /etc/nginx/sites-enabled/netloom-radius
    nginx -t
    systemctl enable --now nginx
    systemctl reload nginx
    certbot certonly --webroot -w /var/www/netloom-acme -d radius.netnoc.in \
        --non-interactive --agree-tos --register-unsafely-without-email
fi
install -m 0644 deploy/nginx/radius-https.conf "$site"
ln -sfn "$site" /etc/nginx/sites-enabled/netloom-radius
nginx -t
systemctl enable --now nginx
systemctl reload nginx
printf '#!/bin/sh\nset -eu\nnginx -t\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/netloom-nginx
chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/netloom-nginx
systemctl enable --now certbot.timer
