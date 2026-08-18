#!/usr/bin/env bash
#
# Manual deploy to Dokku, for when GitHub Actions is unavailable.
#
# Does by hand what .github/workflows/ci.yml does automatically on a push to
# main: run the test suites, then push the branch to the Dokku git remote. The
# release phase in the Procfile (migrate + import_csv + build_db) then runs on
# the server, exactly as it would after an automatic deploy.
#
#   scripts/deploy.sh              # test, then deploy HEAD
#   scripts/deploy.sh --skip-tests # deploy without running the suites first
#   scripts/deploy.sh --force      # let Dokku take a non-fast-forward push
#   scripts/deploy.sh --rebuild    # no push; just re-run release+build on the server
#
# Environment overrides: DOKKU_HOST, DOKKU_APP, DOKKU_REMOTE.

set -euo pipefail

DOKKU_HOST="${DOKKU_HOST:-cocoscrabble.vps.webdock.cloud}"
DOKKU_APP="${DOKKU_APP:-cocodb}"
DOKKU_REMOTE="${DOKKU_REMOTE:-dokku}"
# Dokku's deploy-branch is 'main' (set globally in ../vps dokku.yml); a push to
# any other branch name is accepted and then ignored, so always target main.
DEPLOY_BRANCH="main"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

skip_tests=0
force=0
rebuild_only=0
for arg in "$@"; do
  case "$arg" in
    --skip-tests) skip_tests=1 ;;
    --force) force=1 ;;
    --rebuild) rebuild_only=1 ;;
    # Print the header comment block (everything after the shebang up to the
    # first non-comment line) as the usage message.
    -h|--help) awk 'NR>1 && !/^#/{exit} NR>1{sub(/^# ?/,""); print}' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

if [ "$rebuild_only" = 1 ]; then
  # Rebuilds the running image and re-runs the release phase, which re-seeds
  # players and rebuilds the ratings projection from whatever is already
  # deployed. Use this when the code is current but the DB needs refreshing.
  say "Rebuilding $DOKKU_APP on $DOKKU_HOST (no push)"
  ssh "dokku@$DOKKU_HOST" ps:rebuild "$DOKKU_APP"
  exit 0
fi

# --- preflight -------------------------------------------------------------

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "main" ]; then
  echo "warning: on branch '$branch', not main; it will be deployed as $DEPLOY_BRANCH" >&2
  read -r -p "continue? [y/N] " reply
  [ "$reply" = "y" ] || [ "$reply" = "Y" ] || exit 1
fi

# Dokku deploys the commit you push, not your working tree: uncommitted work is
# silently left behind, which is the usual way a "deploy" appears to do nothing.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "warning: uncommitted changes will NOT be deployed:" >&2
  git status --short --untracked-files=no >&2
  read -r -p "continue? [y/N] " reply
  [ "$reply" = "y" ] || [ "$reply" = "Y" ] || exit 1
fi

# --- tests (the same gate the CI deploy job depends on) --------------------

if [ "$skip_tests" = 0 ]; then
  say "Installing dependencies (uv sync --extra web)"
  uv sync --extra web

  say "Engine tests"
  # The golden file's float-heavy values only reproduce on a matching
  # CPython/platform, so CI skips it; locally it should pass, so we run it.
  uv run python -m unittest

  say "Web/DB tests"
  uv run python web/manage.py test accounts players ratings

  say "Lint"
  uv run ruff check .
else
  say "Skipping tests (--skip-tests)"
fi

# --- deploy ----------------------------------------------------------------

remote_url="ssh://dokku@$DOKKU_HOST/$DOKKU_APP"
if ! git remote get-url "$DOKKU_REMOTE" >/dev/null 2>&1; then
  say "Adding git remote '$DOKKU_REMOTE' -> $remote_url"
  git remote add "$DOKKU_REMOTE" "$remote_url"
elif [ "$(git remote get-url "$DOKKU_REMOTE")" != "$remote_url" ]; then
  say "Updating git remote '$DOKKU_REMOTE' -> $remote_url"
  git remote set-url "$DOKKU_REMOTE" "$remote_url"
fi

say "Deploying $(git rev-parse --short HEAD) to $DOKKU_APP"
if [ "$force" = 1 ]; then
  git push --force "$DOKKU_REMOTE" "HEAD:$DEPLOY_BRANCH"
else
  git push "$DOKKU_REMOTE" "HEAD:$DEPLOY_BRANCH"
fi

say "Deployed. Check https://cocodb.cocoscrabble.org/ratings/"
echo "Note: this pushed straight to the server. Push to GitHub too, so the"
echo "repo matches what is deployed:  git push origin $branch"
