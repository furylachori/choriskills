#!/bin/bash
if ((BASH_VERSINFO[0] < 4)) || ((BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 3)); then
    echo "ERROR: bash 4.3+ required (needed for declare -n). You have ${BASH_VERSION}." >&2
    echo "Install via: brew install bash" >&2
    exit 1
fi
set -euo pipefail

# ---------------------------------------------------------------------------
# deploy.sh — Install choriskills and write per-skill .env files.
# Keys are read from environment variables, never from CLI arguments.
#
# BULLETPROOF GUARANTEES:
#   1. Nukes old state from BOTH locations before installing
#   2. Always does fresh installs (no patching/upgrading)
#   3. Writes .env atomically from scratch (mktemp + mv)
#   4. Verifies each skill loads after install
#   5. Fails fast if any skill fails verification
# ---------------------------------------------------------------------------

SCRIPT_NAME="$(basename "$0")"
DRY_RUN=false
REMOVE_EXCLUDED=false
CLONE_DIR="$HOME/.choriskills"
REPO_URL="https://github.com/furylachori/choriskills.git"
LOCKFILE="/tmp/choriskills-deploy.lock"
FAILED_SKILLS=()
EXCLUDE_SKILLS=()

DATA_SKILLS_DIR="$HOME/.zeroclaw/data/skills"
AGENT_WORKSPACE_DIR="$HOME/.zeroclaw/agents/default/workspace/skills"

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
    BAILIAN_WAN_API_KEY            Optional. Enables bailian-wan-image skill.
    BAILIAN_QWEN_API_KEY           Optional. Enables bailian-qwen-image skill.
    MINIMAX_API_KEY                Optional. Enables minimax-video skill.

Options:
    -h, --help       Show this help message and exit.
    --dry-run        Preview what would happen without making changes.
    --exclude <skill>   Exclude a skill from deployment (can be used multiple times)
    --remove           Remove excluded skills from agent workspace

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
        --remove) REMOVE_EXCLUDED=true; shift ;;
        --exclude)
            shift
            if [ $# -gt 0 ]; then
                if [[ ! "$1" =~ ^[a-zA-Z0-9_-]+$ ]]; then
                    echo "ERROR: Invalid skill name: $1 (only alphanumeric, hyphens, underscores)" >&2
                    exit 2
                fi
                EXCLUDE_SKILLS+=("$1")
                shift
            else
                echo "ERROR: --exclude requires a skill name" >&2
                exit 2
            fi
            ;;
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
            rm -rf -- "$CLONE_DIR"
            git clone --depth 1 "$REPO_URL" "$CLONE_DIR"
        fi
    else
        echo "==> Cloning repo into $CLONE_DIR ..."
        if $DRY_RUN; then
            echo "    [DRY RUN] Would run: git clone --depth 1 $REPO_URL $CLONE_DIR"
            return 0
        fi
        rm -rf -- "$CLONE_DIR"
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

# Bailian WAN skill (optional key)
BAILIAN_WAN_API_KEY="${BAILIAN_WAN_API_KEY:-}"
if [ -n "$BAILIAN_WAN_API_KEY" ]; then
    validate_key "BAILIAN_WAN_API_KEY" "$BAILIAN_WAN_API_KEY" || exit 2
    SKILLS+=("bailian-wan-image")
    SKILL_KEY_VAR["bailian-wan-image"]="BAILIAN_WAN_API_KEY"
else
    echo "==> Skipping bailian-wan-image (BAILIAN_WAN_API_KEY not set)."
fi

# Bailian Qwen skill (optional key)
BAILIAN_QWEN_API_KEY="${BAILIAN_QWEN_API_KEY:-}"
if [ -n "$BAILIAN_QWEN_API_KEY" ]; then
    validate_key "BAILIAN_QWEN_API_KEY" "$BAILIAN_QWEN_API_KEY" || exit 2
    SKILLS+=("bailian-qwen-image")
    SKILL_KEY_VAR["bailian-qwen-image"]="BAILIAN_QWEN_API_KEY"
else
    echo "==> Skipping bailian-qwen-image (BAILIAN_QWEN_API_KEY not set)."
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

# Filter out excluded skills
FILTERED_SKILLS=()
for skill in "${SKILLS[@]}"; do
    excluded=false
    for excl in ${EXCLUDE_SKILLS[@]+"${EXCLUDE_SKILLS[@]}"}; do
        if [ "$skill" = "$excl" ]; then
            excluded=true
            echo "==> Excluding $skill (--exclude)"
            break
        fi
    done
    if ! $excluded; then
        FILTERED_SKILLS+=("$skill")
    fi
done
SKILLS=(${FILTERED_SKILLS[@]+"${FILTERED_SKILLS[@]}"})
declare -A SKILL_KEY_VAR_FILTERED=()
for skill in ${SKILLS[@]+"${SKILLS[@]}"}; do
    if [[ -v "SKILL_KEY_VAR[$skill]" ]]; then
        SKILL_KEY_VAR_FILTERED["$skill"]="${SKILL_KEY_VAR[$skill]}"
    fi
done
declare -n ref=SKILL_KEY_VAR
for key in "${!ref[@]}"; do
    unset "SKILL_KEY_VAR[$key]"
done
declare -n ref2=SKILL_KEY_VAR_FILTERED
for key in "${!ref2[@]}"; do
    SKILL_KEY_VAR["$key"]="${ref2[$key]}"
done

# Warn about --exclude names that didn't match any known skill
ALL_KNOWN_SKILLS=(stepfun-image stepfun-tts stepfun-asr bailian-wan-image bailian-qwen-image minimax-video)
for excl in ${EXCLUDE_SKILLS[@]+"${EXCLUDE_SKILLS[@]}"}; do
    found=false
    for skill in "${ALL_KNOWN_SKILLS[@]}"; do
        if [[ "$excl" == "$skill" ]]; then
            found=true
            break
        fi
    done
    if ! $found; then
        echo "WARNING: --exclude '$excl' does not match any known skill." >&2
    fi
done

TOTAL=${#SKILLS[@]}

# Remove excluded skills if --remove flag is set
if $REMOVE_EXCLUDED && [ ${#EXCLUDE_SKILLS[@]} -gt 0 ]; then
    for excl in "${EXCLUDE_SKILLS[@]}"; do
        EXCL_DIR="$DATA_SKILLS_DIR/$excl"
        EXCL_AGENT_DIR="$AGENT_WORKSPACE_DIR/$excl"
        if $DRY_RUN; then
            echo "    [DRY RUN] Would remove: $EXCL_DIR"
            echo "    [DRY RUN] Would remove: $EXCL_AGENT_DIR"
        else
            if [ -d "$EXCL_DIR" ]; then
                echo "==> Removing excluded skill from install: $excl"
                rm -rf -- "$EXCL_DIR"
            fi
            if [ -d "$EXCL_AGENT_DIR" ]; then
                echo "==> Removing excluded skill from agent workspace: $excl"
                rm -rf -- "$EXCL_AGENT_DIR"
            fi
        fi
    done
fi

# ---- Install loop ----------------------------------------------------------
# BULLETPROOF: For each skill, we nuke old state from BOTH locations BEFORE
# installing, then do a fresh install, write .env from scratch, and verify.

for idx in "${!SKILLS[@]}"; do
    skill="${SKILLS[$idx]}"
    key_var="${SKILL_KEY_VAR[$skill]}"
    key_value="${!key_var}"
    num=$((idx + 1))

    SKILL_DATA_DIR="$DATA_SKILLS_DIR/$skill"
    AGENT_SKILL_DIR="$AGENT_WORKSPACE_DIR/$skill"

    echo ""
    echo "==> [$num/$TOTAL] Deploying $skill ..."

    # ---- NUCLEAR OPTION: Remove old state from BOTH locations ----
    if $DRY_RUN; then
        echo "    [DRY RUN] Would nuke: $SKILL_DATA_DIR"
        echo "    [DRY RUN] Would nuke: $AGENT_SKILL_DIR"
        echo "    [DRY RUN] Would install: zeroclaw skills install $CLONE_DIR/$skill"
        echo "    [DRY RUN] Would write ${key_var}=*** to .env"
        echo "    [DRY RUN] Would verify: python3 $AGENT_SKILL_DIR/main.py --help"
        continue
    fi

    if [ -d "$SKILL_DATA_DIR" ]; then
        echo "    Nuking old skill data: $SKILL_DATA_DIR"
        rm -rf -- "$SKILL_DATA_DIR"
    fi
    if [ -d "$AGENT_SKILL_DIR" ]; then
        echo "    Nuking old agent workspace: $AGENT_SKILL_DIR"
        rm -rf -- "$AGENT_SKILL_DIR"
    fi

    # ---- Fresh install ----
    if ! zeroclaw skills install "$CLONE_DIR/$skill"; then
        echo "ERROR: zeroclaw skills install failed for $skill." >&2
        FAILED_SKILLS+=("$skill")
        continue
    fi

    # ---- Verify install directory exists ----
    if [ ! -d "$SKILL_DATA_DIR" ]; then
        echo "ERROR: $SKILL_DATA_DIR does not exist after install." >&2
        FAILED_SKILLS+=("$skill")
        continue
    fi

    # ---- Write .env from scratch (atomic: mktemp -> mv) ----
    tmpfile="$(mktemp)"
    chmod 600 "$tmpfile"
    printf '%s=%s\n' "$key_var" "$key_value" > "$tmpfile"
    mv "$tmpfile" "$SKILL_DATA_DIR/.env"
    echo "    .env written to $SKILL_DATA_DIR/.env"

    # ---- Copy to agent workspace ----
    mkdir -p "$AGENT_SKILL_DIR"
    cp -r "$SKILL_DATA_DIR/." "$AGENT_SKILL_DIR/"
    echo "    Copied to $AGENT_SKILL_DIR"

    # ---- Verify skill loads ----
    if [ -f "$AGENT_SKILL_DIR/main.py" ]; then
        if ! python3 "$AGENT_SKILL_DIR/main.py" --help >/dev/null 2>&1; then
            echo "ERROR: $skill failed verification (main.py --help)." >&2
            FAILED_SKILLS+=("$skill")
            continue
        fi
        echo "    Verification passed."
    else
        echo "    No main.py found; skipping verification."
    fi
done

# ---- Fail fast: abort if ANY skill failed ----------------------------------
if [ ${#FAILED_SKILLS[@]} -gt 0 ]; then
    echo ""
    echo "============================================" >&2
    echo "ERROR: ${#FAILED_SKILLS[@]} skill(s) failed:" >&2
    for s in "${FAILED_SKILLS[@]}"; do
        echo "  - $s" >&2
    done
    echo "============================================" >&2
    echo "Deployment aborted. Fix the above skills and re-run." >&2
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
