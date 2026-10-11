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

printf 'Waiting for GitHub Actions run for commit %s...\n' "$short_sha"
run_id=
for attempt in {1..10}; do
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
        printf 'Found GitHub Actions run %s.\n' "$run_id"
        break
    fi
    if (( attempt % 5 == 0 )); then
        printf 'Still waiting for the run (%s seconds elapsed).\n' "$((attempt * 3))"
    fi
    sleep 3
done

if [[ -z "$run_id" ]]; then
    printf 'No push-triggered run found; starting the workflow manually.\n'
    gh workflow run build-release-v2.yml \
        --repo "$repository" \
        --ref master \
        -f test_build=false

    for attempt in {1..60}; do
        run_id=$(gh run list \
            --repo "$repository" \
            --branch master \
            --commit "$commit" \
            --event workflow_dispatch \
            --workflow build-release-v2.yml \
            --limit 1 \
            --json databaseId \
            --jq '.[0].databaseId // empty')
        if [[ -n "$run_id" ]]; then
            printf 'Found manually started GitHub Actions run %s.\n' "$run_id"
            break
        fi
        if (( attempt % 5 == 0 )); then
            printf 'Still waiting for the manual run (%s seconds elapsed).\n' "$((attempt * 3))"
        fi
        sleep 3
    done
fi

if [[ -z "$run_id" ]]; then
    printf 'No GitHub Actions run found for commit %s.\n' "$commit" >&2
    exit 1
fi

gh run watch "$run_id" --repo "$repository" --compact --exit-status

if ! command -v python >/dev/null 2>&1; then
    printf 'Python is required to extract the Windows build.\n' >&2
    exit 1
fi

download_dir=dist/dev
mkdir -p "$download_dir"
find "$download_dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +

gh release download "dev-${short_sha}" \
    --repo "$repository" \
    --pattern "TinyPedal-dev-${short_sha}-windows.zip" \
    --dir "$download_dir" \
    --clobber

zip_file="$download_dir/TinyPedal-dev-${short_sha}-windows.zip"
python -m zipfile -e "$zip_file" "$download_dir"

printf 'Windows build downloaded and extracted to %s\n' "$download_dir"