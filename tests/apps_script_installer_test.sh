#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary_dir="$(mktemp -d)"
trap 'rm -rf "${temporary_dir}"' EXIT

mkdir -p "${temporary_dir}/bin"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -euo pipefail' \
  'if [[ "$*" == *"--version"* ]]; then' \
  '  printf "%s\\n" "3.3.0"' \
  '  exit 0' \
  'fi' \
  'if [[ "$*" == *"show-authorized-user"* ]]; then' \
  "  if [[ \"\${FAKE_AUTH_STATE:-valid}\" == \"stale\" ]]; then" \
  "    printf '%s\\n' '{\"loggedIn\":false}'" \
  '  else' \
  "    printf '%s\\n' '{\"loggedIn\":true,\"email\":\"owner@example.test\"}'" \
  '  fi' \
  '  exit 0' \
  'fi' \
  'if [[ "$*" == *" run "* ]]; then' \
  "  printf '%s\\n' '{\"response\":{\"installed\":true}}'" \
  '  exit 0' \
  'fi' \
  'printf "unexpected npx invocation: %s\\n" "$*" >&2' \
  'exit 1' \
  >"${temporary_dir}/bin/npx"
chmod +x "${temporary_dir}/bin/npx"

PATH="${temporary_dir}/bin:${PATH}" \
  "${PROJECT_ROOT}/scripts/install-google-apps-script.sh" --check >/dev/null

create_fixture() {
  local name="$1"
  local fixture="${temporary_dir}/${name}"
  mkdir -p "${fixture}/scripts"
  cp "${PROJECT_ROOT}/scripts/install-google-apps-script.sh" "${fixture}/scripts/"
  cp "${PROJECT_ROOT}/scripts/validate-apps-script.js" "${fixture}/scripts/"
  cp "${PROJECT_ROOT}/config.apps-script.example.json" "${fixture}/"
  cp -R "${PROJECT_ROOT}/apps-script" "${fixture}/"
  printf '%s\n' "${fixture}"
}

assert_invalid_config_stops_before_remote_changes() {
  local fixture="$1"
  if PATH="${temporary_dir}/bin:${PATH}" \
    "${fixture}/scripts/install-google-apps-script.sh" >/dev/null 2>&1; then
    printf '%s\n' 'invalid configuration unexpectedly reached the installer' >&2
    exit 1
  fi
  [[ ! -e "${fixture}/.installer/tricount-exporter/source" ]] || {
    printf '%s\n' 'invalid configuration staged Apps Script source' >&2
    exit 1
  }
}

fractional_fixture="$(create_fixture fractional-config)"
jq '.run_interval_hours = 12.5' "${fractional_fixture}/config.apps-script.example.json" \
  >"${fractional_fixture}/config.apps-script.local.json"
assert_invalid_config_stops_before_remote_changes "${fractional_fixture}"

invalid_url_fixture="$(create_fixture invalid-folder-url)"
jq '.drive_output_folder_url = "https://example.test/not-a-drive-folder"' \
  "${invalid_url_fixture}/config.apps-script.example.json" \
  >"${invalid_url_fixture}/config.apps-script.local.json"
assert_invalid_config_stops_before_remote_changes "${invalid_url_fixture}"

status_fixture="$(create_fixture status-state)"
status_state_dir="${status_fixture}/.installer/tricount-exporter"
mkdir -p "${status_state_dir}/clasp-owner-auth"
printf '%s\n' '{"scriptId":"EXAMPLE_SCRIPT_ID"}' >"${status_state_dir}/.clasp.json"
printf '%s\n' '{}' >"${status_state_dir}/clasp-owner-auth/.clasprc.json"
if PATH="${temporary_dir}/bin:${PATH}" FAKE_AUTH_STATE=stale \
  "${status_fixture}/scripts/install-google-apps-script.sh" --status >/dev/null 2>&1; then
  printf '%s\n' 'stale status authorization unexpectedly succeeded' >&2
  exit 1
fi
[[ -f "${status_state_dir}/clasp-owner-auth/.clasprc.json" ]] || {
  printf '%s\n' 'status removed the stale private authorization' >&2
  exit 1
}
PATH="${temporary_dir}/bin:${PATH}" \
  "${status_fixture}/scripts/install-google-apps-script.sh" --status >/dev/null
[[ ! -e "${status_state_dir}/source" ]] || {
  printf '%s\n' 'status unexpectedly recreated disposable source state' >&2
  exit 1
}
TRICOUNT_EXPORTER_CONFIRM_UNINSTALL=DELETE PATH="${temporary_dir}/bin:${PATH}" \
  "${status_fixture}/scripts/install-google-apps-script.sh" --uninstall >/dev/null
[[ ! -e "${status_state_dir}/source" ]] || {
  printf '%s\n' 'uninstall unexpectedly recreated disposable source state' >&2
  exit 1
}

printf 'Apps Script installer preflight test passed\n'
