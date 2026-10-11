#!/usr/bin/env bash
set -euo pipefail

branch=$(git branch --show-current)
if [[ "$branch" != "master" ]]; then
    printf 'Dev releases are built only from master (current branch: %s).\n' "$branch" >&2
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    printf 'GitHub CLI (gh) is required. Install it and run: gh auth login\n' >&2
    exit 1
fi

gh auth status --hostname github.com >/dev/null

remote_url=$(git remote get-url origin)
case "$remote_url" in
    https://github.com/*) repository=${remote_url#https://github.com/} ;;
    git@github.com:*) repository=${remote_url#git@github.com:} ;;
    ssh://git@github.com/*) repository=${remote_url#ssh://git@github.com/} ;;
    *)
        printf 'Unsupported GitHub remote URL: %s\n' "$remote_url" >&2
        exit 1
        ;;
esac
repository=${repository%.git}

commit=$(git rev-parse HEAD)
short_sha=${commit:0:12}

git push origin master

run_id=
for attempt in {1..60}; do
    run_id=$(gh run list \
        --repo "$repository" \
        --branch master \
        --commit "$commit" \
        --event push \
        --workflow build-release-v2.yml \
        --limit 1 \
        --json databaseId \
        --jq '.[0].databaseId // empty')
    if [[ -n "$run_id" ]]; then
        break
    fi
    sleep 3
done

if [[ -z "$run_id" ]]; then
    printf 'No GitHub Actions run found for commit %s.\n' "$commit" >&2
    exit 1
fi

gh run watch "$run_id" --repo "$repository" --compact --exit-status

mkdir -p dist/dev
gh release download "dev-${short_sha}" \
    --repo "$repository" \
    --pattern "TinyPedal-dev-${short_sha}-windows.zip" \
    --dir dist/dev \
    --clobber

printf 'Windows build downloaded to dist/dev/TinyPedal-dev-%s-windows.zip\n' "$short_sha"