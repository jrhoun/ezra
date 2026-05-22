#!/usr/bin/env bash
set -euo pipefail

REPOS_ROOT="${REPOS_ROOT:-/opt/docbot/repos}"

for repo in liferay-learn liferay-portal liferay-ide liferay-blade-cli; do
    dir="$REPOS_ROOT/$repo"
    if [[ -d "$dir/.git" ]]; then
        echo "Refreshing $repo..."
        git -C "$dir" fetch origin
        git -C "$dir" reset --hard origin/master
    else
        echo "Skipping $repo (not found at $dir)"
    fi
done
