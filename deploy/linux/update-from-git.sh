#!/usr/bin/env bash
# Installed as /usr/local/sbin/patientfollowup-update; deploy origin/main only.
set -euo pipefail
export GIT_TERMINAL_PROMPT=0

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ ${EUID} -eq 0 ]] || die 'Run this command as root.'
mode=update
case "${1:-}" in
    '') ;;
    --check) mode=check ;;
    *) die 'Usage: patientfollowup-update [--check]' ;;
esac
[[ $# -le 1 ]] || die 'Too many arguments.'

base=$(realpath "${PATIENTFOLLOWUP_BASE:-/srv/apps/patientfollowup}")
source_dir="$base/source"
env_file=${PATIENTFOLLOWUP_ENV_FILE:-/etc/patientfollowup/app.env}
uv_bin=${PATIENTFOLLOWUP_UV_BIN:-/opt/patientfollowup-tools/bin/uv}
service=patientfollowup.service
[[ -d "$source_dir/.git" ]] || die 'Initialize the source repository first; see deploy/linux/README.md.'
[[ -L "$base/current" ]] || die 'current must be a release symlink.'
old=$(readlink -f "$base/current")
[[ "$old" == "$base/releases/"* && -d "$old" ]] || die 'Current release is outside this project.'
exec 9>"$base/.git-deploy.lock"
flock -n 9 || die 'Another deployment is running.'
[[ $(git -C "$source_dir" rev-parse --show-toplevel) == "$source_dir" ]] || die 'Unexpected repository root.'
[[ $(git -C "$source_dir" symbolic-ref --short HEAD) == main ]] || die 'The source checkout must be on main.'
# Older main revisions ignore .venv directories but not the deployment's symlink.
# The shared repository exclude keeps all linked releases clean without masking code.
exclude="$source_dir/.git/info/exclude"
if ! grep -qxF '.venv' "$exclude"; then printf '\n.venv\n' >> "$exclude"; fi
[[ -z $(git -C "$source_dir" status --porcelain --untracked-files=normal) ]] || die 'Source checkout has local changes; nothing was overwritten.'

running=legacy
if [[ -e "$old/.git" ]]; then
    [[ -z $(git -C "$old" status --porcelain --untracked-files=normal) ]] || die 'Running release has local changes; nothing was overwritten.'
    running=$(git -C "$old" rev-parse HEAD)
fi
fetched=0
for attempt in 1 2; do
    if timeout 45s git -c http.version=HTTP/1.1 -C "$source_dir" fetch --quiet --prune origin refs/heads/main:refs/remotes/origin/main; then
        fetched=1
        break
    fi
    printf 'Git fetch attempt %s failed or timed out.\n' "$attempt" >&2
done
[[ "$fetched" -eq 1 ]] || die 'Cannot fetch main; the running application was not changed.'
git -C "$source_dir" merge --ff-only --quiet origin/main
target=$(git -C "$source_dir" rev-parse 'origin/main^{commit}')
printf 'Running: %s\nGit main: %s\n' "$running" "$target"
if [[ "$running" != legacy ]]; then
    git -C "$source_dir" merge-base --is-ancestor "$running" "$target" || die 'main does not contain the running version; automatic rollback is refused.'
fi
if [[ "$mode" == check ]]; then
    [[ "$running" != "$target" ]] || printf 'Already synchronized.\n'
    exit 0
fi
if [[ "$running" == "$target" ]]; then
    curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8101/health >/dev/null
    printf 'Already synchronized; no restart or migration needed.\n'
    exit 0
fi

new="$base/releases/$(date -u +%Y%m%dT%H%M%SZ)-${target:0:12}"
[[ ! -e "$new" ]] || die 'Release directory already exists.'
git -C "$source_dir" worktree add --quiet --detach "$new" "$target"
old_venv=$(readlink -f "$old/.venv")
if [[ -x "$old_venv/bin/python" ]] && cmp -s "$old/uv.lock" "$new/uv.lock" && cmp -s "$old/pyproject.toml" "$new/pyproject.toml"; then
    # An unchanged lockfile can reuse the existing immutable dependencies.
    ln -s "$old_venv" "$new/.venv"
else
    [[ -x "$uv_bin" ]] || die 'uv is required for dependency changes; see deployment setup instructions.'
    requirements=$(mktemp "$base/.requirements.XXXXXX")
    (cd "$new"; "$uv_bin" export --frozen --no-dev --no-hashes --no-emit-project --output-file "$requirements" >/dev/null)
    python3 -m venv "$new/.venv"
    "$new/.venv/bin/pip" install --disable-pip-version-check --retries 2 --timeout 30 \
        --index-url https://mirrors.aliyun.com/pypi/simple/ -r "$requirements"
    rm -f -- "$requirements"
fi
"$new/.venv/bin/python" -c 'import ast,pathlib,sys; [ast.parse(p.read_text()) for p in pathlib.Path(sys.argv[1]).rglob("*.py")]' "$new/src"
[[ -f "$env_file" ]] || die 'Application environment file is missing.'
set -a
source "$env_file"
set +a
export PYTHONPATH="$new/src"
cd "$new"

stopped=0
switched=0
next="$base/.current.git-deploy.$$"
switch_to() {
    [[ -L "$base/current" ]] || return 1
    [[ ! -e "$next" && ! -L "$next" ]] || return 1
    ln -s "$1" "$next"
    mv -Tf -- "$next" "$base/current"
}
recover() {
    result=$?
    trap - EXIT
    if [[ -L "$next" ]]; then rm -- "$next"; fi
    if [[ "$result" -ne 0 && "$stopped" -eq 1 ]]; then
        printf 'Deployment failed; restoring previous code release. Database is not automatically downgraded.\n' >&2
        if [[ "$switched" -eq 1 ]]; then switch_to "$old" || true; fi
        systemctl start "$service" || true
    fi
    exit "$result"
}
trap recover EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

db_revision=$(runuser -u patientfollowup --preserve-environment -- "$new/.venv/bin/python" -m alembic current | awk 'NF {print $1}')
code_revision=$("$new/.venv/bin/python" -m alembic heads | awk 'NF {print $1}')
[[ -n "$code_revision" && "$code_revision" != *$'\n'* ]] || die 'Expected one Alembic head.'
stopped=1
systemctl stop "$service"
if [[ "$db_revision" != "$code_revision" ]]; then
    # A migration is the only normal update that needs a new data backup.
    runuser -u patientfollowup --preserve-environment -- "$new/.venv/bin/python" deploy/linux/backup.py
fi
runuser -u patientfollowup --preserve-environment -- "$new/.venv/bin/python" -m alembic upgrade head
switched=1
switch_to "$new"
systemctl start "$service"
healthy=0
for attempt in {1..30}; do
    if curl --fail --silent --max-time 5 http://127.0.0.1:8101/health >/dev/null; then healthy=1; break; fi
    sleep 1
done
[[ "$healthy" -eq 1 ]] || die 'Health check failed after switching versions.'
systemctl is-active --quiet "$service"
trap - EXIT INT TERM
printf 'Deployed main: %s\nCurrent release: %s\nPrevious release: %s\n' "$target" "$new" "$old"
