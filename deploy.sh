#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# deploy.sh — Install choriskills and write per-skill .env files.
# Keys are read from environment variables, never from CLI arguments.
# ---------------------------------------------------------------------------

SCRIPT_NAME="$(basename "$0")"
DRY_RUN=false
CLONE_DIR="$HOME/.choriskills"
REPO_URL="https://github.com/furylachori/choriskills.git"
LOCKFILE="/tmp/choriskills-deploy.lock"
FAILED_SKILLS=()

# ---- Cleanup trap ---------------------------------------------------------
cleanup() {
    rm -f "$LOCKFILE"
}
trap cleanup EXIT

# ---- Usage ----------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $SCRIPT_NAME [OPTIONS]

Install choriskills from GitHub and configure per-skill .env files.

API keys are read from environment variables (never passed as arguments):

    STEPFUN_API_KEY                Required. Used by stepfun-image, stepfun-tts, stepfun-asr.
    BAILIAN_TOKEN_PLAN_API_KEY     Optional. Enables bailian-image skill.
    MINIMAX_API_KEY                Optional. Enables minimax-video skill.

Options:
    -h, --help       Show this help message and exit.
    --dry-run        Preview what would happen without making changes.

Exit codes:
    0   Success.
    1   Runtime error (clone failure, install failure, etc.).
    2   Usage / validation error (bad args, missing keys, etc.).
EOF
    exit 0
}

# ---- Dependency checks ----------------------------------------------------
command -v git >/dev/null 2>&1 || { echo "ERROR: git is not installed or not in PATH." >&2; exit 1; }
command -v zeroclaw >/dev/null 2>&1 || { echo "ERROR: zeroclaw is not installed or not in PATH." >&2; exit 1; }

# ---- Parse arguments ------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)   usage ;;
        --dry-run)   DRY_RUN=true; shift ;;
        *)           echo "ERROR: Unknown option: $1" >&2; echo "Run '$SCRIPT_NAME --help' for usage." >&2; exit 2 ;;
    esac
done

# ---- Validate key format (non-empty, no newlines) -------------------------
validate_key() {
    local name="$1" value="$2"
    if [ -z "$value" ]; then
        echo "ERROR: $name is empty." >&2
        return 1
    fi
    if [[ "$value" == *$'\n'* ]] || [[ "$value" == *$'\r'* ]]; then
        echo "ERROR: $name contains newline characters." >&2
        return 1
    fi
}

# ---- Read required key from env -------------------------------------------
STEPFUN_API_KEY="${STEPFUN_API_KEY:-}"
validate_key "STEPFUN_API_KEY" "$STEPFUN_API_KEY" || {
    echo "ERROR: Set STEPFUN_API_KEY in your environment. Run '$SCRIPT_NAME --help' for details." >&2
    exit 2
}

# ---- Validate HOME --------------------------------------------------------
if [ -z "${HOME:-}" ] || [ "$HOME" = "/" ]; then
    echo "ERROR: HOME is unset or '/'. Cowardly refusing to proceed." >&2
    exit 1
fi

# ---- Concurrent-deploy lock -----------------------------------------------
exec 200>"$LOCKFILE"
if ! flock -n 200 2>/dev/null; then
    # flock unavailable (e.g. macOS without flock); fall back to PID-based lock.
    if [ -f "$LOCKFILE" ]; then
        old_pid="$(cat "$LOCKFILE" 2>/dev/null || true)"
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            echo "ERROR: Another deploy is running (PID $old_pid). Remove $LOCKFILE if stale." >&2
            exit 1
        fi
        echo "WARNING: Removing stale lockfile (PID $old_pid no longer running)." >&2
        rm -f "$LOCKFILE"
    fi
fi
echo $$ > "$LOCKFILE"

# ---- Guard against rm -rf on wrong directory ------------------------------
if [ -d "$CLONE_DIR" ]; then
    # Verify it looks like our repo or an empty dir before touching it.
    if [ -d "$CLONE_DIR/.git" ]; then
        remote_url="$(git -C "$CLONE_DIR" remote get-url origin 2>/dev/null || true)"
        if [ "$remote_url" != "$REPO_URL" ]; then
            echo "ERROR: $CLONE_DIR exists and its origin is '$remote_url', not '$REPO_URL'." >&2
            echo "       Remove it manually if you want to re-clone." >&2
            exit 1
        fi
    fi
fi

# ---- Clone or update the skill repository ---------------------------------
clone_or_update() {
    if [ -d "$CLONE_DIR/.git" ]; then
        echo "==> Updating existing repo at $CLONE_DIR ..."
        if $DRY_RUN; then
            echo "    [DRY RUN] Would run: git -C $CLONE_DIR pull --ff-only"
            return 0
        fi
        if ! git -C "$CLONE_DIR" pull --ff-only 2>/dev/null; then
            echo "WARNING: git pull failed; re-cloning from scratch..." >&2
            rm -rf "$CLONE_DIR"
            git clone --depth 1 "$REPO_URL" "$CLONE_DIR"
        fi
    else
        echo "==> Cloning repo into $CLONE_DIR ..."
        if $DRY_RUN; then
            echo "    [DRY RUN] Would run: git clone --depth 1 $REPO_URL $CLONE_DIR"
            return 0
        fi
        rm -rf "$CLONE_DIR"
        git clone --depth 1 "$REPO_URL" "$CLONE_DIR"
    fi
}

clone_or_update

# ---- Build the skill list --------------------------------------------------
declare -a SKILLS=()
declare -A SKILL_KEY_VAR=()

# Stepfun skills (required key — already validated)
for skill in stepfun-image stepfun-tts stepfun-asr; do
    SKILLS+=("$skill")
    SKILL_KEY_VAR["$skill"]="STEPFUN_API_KEY"
done

# Bailian skill (optional key)
BAILIAN_TOKEN_PLAN_API_KEY="${BAILIAN_TOKEN_PLAN_API_KEY:-}"
if [ -n "$BAILIAN_TOKEN_PLAN_API_KEY" ]; then
    validate_key "BAILIAN_TOKEN_PLAN_API_KEY" "$BAILIAN_TOKEN_PLAN_API_KEY" || exit 2
    SKILLS+=("bailian-image")
    SKILL_KEY_VAR["bailian-image"]="BAILIAN_TOKEN_PLAN_API_KEY"
else
    echo "==> Skipping bailian-image (BAILIAN_TOKEN_PLAN_API_KEY not set)."
fi

# Minimax skill (optional key)
MINIMAX_API_KEY="${MINIMAX_API_KEY:-}"
if [ -n "$MINIMAX_API_KEY" ]; then
    validate_key "MINIMAX_API_KEY" "$MINIMAX_API_KEY" || exit 2
    SKILLS+=("minimax-video")
    SKILL_KEY_VAR["minimax-video"]="MINIMAX_API_KEY"
else
    echo "==> Skipping minimax-video (MINIMAX_API_KEY not set)."
fi

TOTAL=${#SKILLS[@]}
if [ "$TOTAL" -eq 0 ]; then
    echo "ERROR: No skills to install (all API keys missing)." >&2
    exit 2
fi

# ---- Install loop ----------------------------------------------------------
for idx in "${!SKILLS[@]}"; do
    skill="${SKILLS[$idx]}"
    key_var="${SKILL_KEY_VAR[$skill]}"
    key_value="${!key_var}"
    num=$((idx + 1))

    echo "==> [$num/$TOTAL] Installing $skill ..."

    if $DRY_RUN; then
        echo "    [DRY RUN] Would install: zeroclaw skills install $CLONE_DIR/$skill"
        echo "    [DRY RUN] Would write ${key_var}=*** to .env"
        continue
    fi

    # Remove existing skill to allow reinstall
    SKILL_DIR="$HOME/.zeroclaw/workspace/skills/$skill"
    if [ -d "$SKILL_DIR" ]; then
        echo "    Removing existing $skill ..."
        rm -rf "$SKILL_DIR"
    fi

    if ! zeroclaw skills install "$CLONE_DIR/$skill"; then
        echo "ERROR: Failed to install $skill." >&2
        FAILED_SKILLS+=("$skill")
        continue
    fi

    SKILL_DIR="$HOME/.zeroclaw/workspace/skills/$skill"
    if [ -d "$SKILL_DIR" ]; then
        # Atomic .env write: tmpfile -> mv, with restricted permissions.
        umask 077
        tmpfile="$(mktemp "$SKILL_DIR/.env.XXXXXX")"
        printf '%s=%s\n' "$key_var" "$key_value" > "$tmpfile"
        chmod 600 "$tmpfile"
        mv "$tmpfile" "$SKILL_DIR/.env"
        echo "    .env written to $SKILL_DIR/.env"
    else
        echo "WARNING: $SKILL_DIR does not exist after install." >&2
        FAILED_SKILLS+=("$skill")
    fi
done

# ---- Summary ---------------------------------------------------------------
if [ ${#FAILED_SKILLS[@]} -gt 0 ]; then
    echo "" >&2
    echo "ERROR: ${#FAILED_SKILLS[@]} skill(s) failed: ${FAILED_SKILLS[*]}" >&2
    exit 1
fi

echo ""
echo "==> Done. Installed $TOTAL skill(s):"
if $DRY_RUN; then
    echo "    [DRY RUN] Would run: zeroclaw skills list"
    echo "    [DRY RUN] Would run: zeroclaw service restart"
else
    zeroclaw skills list
    echo "==> Restarting zeroclaw service ..."
    zeroclaw service restart
fi
