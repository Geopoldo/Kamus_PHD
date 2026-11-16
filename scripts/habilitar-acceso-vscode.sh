#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Ejecuta este script con sudo.'; exit 1; }
project=/home/ewok/Documents/ChatGPT/MAP-H-NOV14-CADDOCS
apt-get update
apt-get install -y openssh-server acl
if ! id maphdev >/dev/null 2>&1; then
 adduser --disabled-password --gecos 'Colaborador MAP-H' maphdev
fi
echo 'Define una contraseña exclusiva para tu amigo (no tu contraseña personal):'
passwd maphdev
for parent in /home/ewok /home/ewok/Documents /home/ewok/Documents/ChatGPT; do
 setfacl -m u:maphdev:x "$parent"
done
setfacl -R -m u:maphdev:rwX "$project"
find "$project" -type d -exec setfacl -m d:u:maphdev:rwx {} +
cat > /etc/ssh/sshd_config.d/60-maph-colaborador.conf <<'EOF'
Match User maphdev
    PasswordAuthentication yes
    PermitEmptyPasswords no
    AllowTcpForwarding local
    X11Forwarding no
Match User maphdev Address *,!192.168.1.0/24,!127.0.0.1
    DenyUsers maphdev
Match all
EOF
install -d -m 0755 -o root -g root /run/sshd
/usr/sbin/sshd -t
if command -v ufw >/dev/null && ufw status | grep -q '^Status: active'; then
 ufw allow from 192.168.1.0/24 to any port 22 proto tcp
fi
systemctl enable --now ssh
systemctl reload ssh
echo 'Listo. Conectar desde VS Code Remote SSH: ssh maphdev@192.168.1.14'
echo "Abrir carpeta: $project"
echo 'La cuenta tiene terminal y permisos de edición del proyecto; no pertenece al grupo sudo.'
