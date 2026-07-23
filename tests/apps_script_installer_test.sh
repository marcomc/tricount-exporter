#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary_dir="$(mktemp -d)"
trap 'rm -rf "${temporary_dir}"' EXIT

mkdir -p "${temporary_dir}/bin"
cat >"${temporary_dir}/bin/npx" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == *'--version'* ]]; then
  printf '%s\n' '3.3.0'
  exit 0
fi
printf 'unexpected npx invocation: %s\n' "$*" >&2
exit 1
EOF
chmod +x "${temporary_dir}/bin/npx"

PATH="${temporary_dir}/bin:${PATH}" \
  "${PROJECT_ROOT}/scripts/install-google-apps-script.sh" --check >/dev/null

printf 'Apps Script installer preflight test passed\n'
