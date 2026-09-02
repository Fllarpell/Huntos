#!/usr/bin/env bash
# 09 — unattended security updates. Reboots only in the window, never on a scrape job.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"
require_root

cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

cat >/etc/apt/apt.conf.d/51workfinding <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-WithUsers "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:42";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Origins-Pattern {
  "origin=Debian,codename=${distro_codename},label=Debian-Security";
  "origin=Ubuntu,archive=${distro_codename}-security";
  "origin=Docker,archive=stable";
};
EOF

systemctl enable --now unattended-upgrades
log "09-unattended: reboot window 04:42 UTC"
