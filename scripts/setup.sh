#!/usr/bin/env bash
# Idempotent setup for docbot on a fresh VM. Run as root.
set -euo pipefail

REPOS_ROOT="${REPOS_ROOT:-/opt/docbot/repos}"
APP_DIR="${APP_DIR:-/opt/docbot/app}"
ETC_DIR=/etc/docbot

# 1. Create docbot user.
if ! id -u docbot >/dev/null 2>&1; then
    useradd --system --create-home --home-dir /home/docbot --shell /bin/bash docbot
fi

# 2. Create directories.
install -d -o docbot -g docbot "$REPOS_ROOT" "$APP_DIR"
install -d -m 0750 -o root -g docbot "$ETC_DIR"

# 3. Place the env file template if missing.
if [[ ! -f "$ETC_DIR/env" ]]; then
    cat > "$ETC_DIR/env" <<'EOF'
SLACK_BOT_TOKEN=xoxb-FILL-ME-IN
SLACK_APP_TOKEN=xapp-FILL-ME-IN
SLACK_CHANNEL_ID=C-FILL-ME-IN
EOF
    chmod 0640 "$ETC_DIR/env"
    chown root:docbot "$ETC_DIR/env"
    echo "Edit $ETC_DIR/env with real secrets before starting docbot."
fi

# 4. Place config if missing.
if [[ ! -f "$ETC_DIR/config.yaml" ]]; then
    cp "$APP_DIR/config.example.yaml" "$ETC_DIR/config.yaml"
    chown root:docbot "$ETC_DIR/config.yaml"
    chmod 0640 "$ETC_DIR/config.yaml"
    echo "Edit $ETC_DIR/config.yaml for this deployment."
fi

# 5. Install systemd units.
install -m 0644 "$APP_DIR/systemd/docbot.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/systemd/docbot-refresh.service" /etc/systemd/system/
install -m 0644 "$APP_DIR/systemd/docbot-refresh.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now docbot-refresh.timer

echo "Setup complete. Next:"
echo "  1. As docbot, set up the venv:"
echo "     sudo -u docbot bash -c 'cd $APP_DIR && python3.11 -m venv .venv && .venv/bin/pip install -e .'"
echo "  2. Clone repos:"
echo "     sudo -u docbot $APP_DIR/scripts/refresh-repos.sh"
echo "  3. Run gh auth login as docbot."
echo "  4. Generate an SSH signing key for docbot:"
echo "     sudo -u docbot ssh-keygen -t ed25519 -N '' -f /home/docbot/.ssh/docbot_signing -C 'docbot signing'"
echo "  5. Configure git to sign with it (as docbot):"
echo "     sudo -u docbot git config --global gpg.format ssh"
echo "     sudo -u docbot git config --global user.signingkey /home/docbot/.ssh/docbot_signing.pub"
echo "     sudo -u docbot git config --global commit.gpgsign true"
echo "     sudo -u docbot git config --global user.name 'JR Houn'"
echo "     sudo -u docbot git config --global user.email 'jr.houn@liferay.com'"
echo "  6. Print the public key and add it to GitHub:"
echo "     sudo -u docbot cat /home/docbot/.ssh/docbot_signing.pub"
echo "     # Paste at https://github.com/settings/ssh/new?type=signing"
echo "  7. systemctl start docbot"
