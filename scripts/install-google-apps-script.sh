#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PROJECT_ROOT
readonly APPS_SOURCE_DIR="${PROJECT_ROOT}/apps-script"
readonly STATE_DIR="${PROJECT_ROOT}/.installer/tricount-exporter"
readonly STATE_FILE="${STATE_DIR}/state.json"
readonly CLASP_FILE="${STATE_DIR}/.clasp.json"
readonly AUTH_DIR="${STATE_DIR}/clasp-owner-auth"
readonly AUTH_FILE="${AUTH_DIR}/.clasprc.json"
readonly SOURCE_DIR="${STATE_DIR}/source"
readonly CONFIG_FILE="${PROJECT_ROOT}/config.apps-script.local.json"
readonly CONFIG_EXAMPLE="${PROJECT_ROOT}/config.apps-script.example.json"
readonly CLASP=(npx --yes @google/clasp@3.3.0)

MODE='install'

die() {
  printf '%s\n' "error: $*" >&2
  exit 1
}

info() {
  printf '%s\n' "tricount-exporter: $*"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

state_get() {
  jq -er "$1" "${STATE_FILE}"
}

state_set() {
  local key="$1"
  local value="$2"
  local temporary_file
  temporary_file="$(mktemp "${STATE_DIR}/state.XXXXXX")"
  jq --arg value "${value}" ".${key} = \$value" "${STATE_FILE}" >"${temporary_file}"
  mv "${temporary_file}" "${STATE_FILE}"
}

ensure_state_dir() {
  mkdir -p "${STATE_DIR}"
  chmod 700 "${PROJECT_ROOT}/.installer" "${STATE_DIR}"
  if [[ ! -f "${STATE_FILE}" ]]; then
    jq -n '{}' >"${STATE_FILE}"
    chmod 600 "${STATE_FILE}"
  fi
}

ensure_config() {
  local created_config='false'
  if [[ ! -f "${CONFIG_FILE}" ]]; then
    cp "${CONFIG_EXAMPLE}" "${CONFIG_FILE}"
    chmod 600 "${CONFIG_FILE}"
    info "Created ${CONFIG_FILE} from the safe example."
    created_config='true'
  fi
  migrate_config
  apply_config_overrides
  if [[ "${created_config}" == 'true' ]]; then
    prompt_initial_config
  fi
  jq -e '
    (.time_zone | type == "string" and length > 0) and
    (.run_interval_hours | type == "number" and floor == . and . >= 1 and . <= 23) and
    (.gmail_query | type == "string" and length > 0) and
    (.lookback_days | type == "number" and floor == . and . >= 1) and
    (.max_messages_per_run | type == "number" and floor == . and . >= 1 and . <= 500) and
    (.max_attachments_per_run | type == "number" and floor == . and . >= 1 and . <= 500) and
    (.drive_folder_name | type == "string" and length > 0) and
    (.drive_output_folder_url | type == "string" and
      (length == 0 or test("^https://drive\\.google\\.com/drive/(?:u/[0-9]+/)?folders/[A-Za-z0-9_-]+(?:[/?#].*)?$"))) and
    (.processed_label_name | type == "string" and length > 0) and
    (.archive_processed_threads | type == "boolean") and
    (.notification_email | type == "string") and
    (.send_success_notification | type == "boolean")
  ' "${CONFIG_FILE}" >/dev/null || die "Invalid ${CONFIG_FILE}."
}

migrate_config() {
  local temporary_file
  temporary_file="$(mktemp "${STATE_DIR}/config.XXXXXX")"
  jq '
    .run_interval_hours = (.run_interval_hours // 12) |
    del(.daily_trigger_hour) |
    .drive_output_folder_url = (.drive_output_folder_url // "") |
    .processed_label_name = (.processed_label_name // "Tricount-Exporter/Imported") |
    .archive_processed_threads = (.archive_processed_threads // true) |
    .notification_email = (.notification_email // "") |
    .send_success_notification = (.send_success_notification // true)
  ' "${CONFIG_FILE}" >"${temporary_file}"
  mv "${temporary_file}" "${CONFIG_FILE}"
}

set_config_string() {
  local key="$1"
  local value="$2"
  local temporary_file
  temporary_file="$(mktemp "${STATE_DIR}/config.XXXXXX")"
  jq --arg value "${value}" ".${key} = \$value" "${CONFIG_FILE}" >"${temporary_file}"
  mv "${temporary_file}" "${CONFIG_FILE}"
}

set_config_json() {
  local key="$1"
  local value="$2"
  local temporary_file
  temporary_file="$(mktemp "${STATE_DIR}/config.XXXXXX")"
  jq --argjson value "${value}" ".${key} = \$value" "${CONFIG_FILE}" >"${temporary_file}"
  mv "${temporary_file}" "${CONFIG_FILE}"
}

apply_config_overrides() {
  if [[ -n "${TRICOUNT_EXPORTER_DRIVE_OUTPUT_FOLDER_URL:-}" ]]; then
    set_config_string drive_output_folder_url "${TRICOUNT_EXPORTER_DRIVE_OUTPUT_FOLDER_URL}"
  fi
  if [[ -n "${TRICOUNT_EXPORTER_PROCESSED_LABEL_NAME:-}" ]]; then
    set_config_string processed_label_name "${TRICOUNT_EXPORTER_PROCESSED_LABEL_NAME}"
  fi
  if [[ -n "${TRICOUNT_EXPORTER_NOTIFICATION_EMAIL:-}" ]]; then
    set_config_string notification_email "${TRICOUNT_EXPORTER_NOTIFICATION_EMAIL}"
  fi
  if [[ -n "${TRICOUNT_EXPORTER_ARCHIVE_PROCESSED_THREADS:-}" ]]; then
    set_config_json archive_processed_threads "${TRICOUNT_EXPORTER_ARCHIVE_PROCESSED_THREADS}"
  fi
  if [[ -n "${TRICOUNT_EXPORTER_SEND_SUCCESS_NOTIFICATION:-}" ]]; then
    set_config_json send_success_notification "${TRICOUNT_EXPORTER_SEND_SUCCESS_NOTIFICATION}"
  fi
  if [[ -n "${TRICOUNT_EXPORTER_RUN_INTERVAL_HOURS:-}" ]]; then
    set_config_json run_interval_hours "${TRICOUNT_EXPORTER_RUN_INTERVAL_HOURS}"
  fi
}

prompt_initial_config() {
  [[ -t 0 && -t 1 && "${TRICOUNT_EXPORTER_NON_INTERACTIVE:-}" != '1' ]] || return
  info 'Optional Google Apps Script settings. Press Enter to accept each default.'
  prompt_string_config drive_output_folder_url 'Output folder URL (blank uses My Drive/Tricount-Exporter)' ''
  prompt_string_config processed_label_name 'Processed Gmail label' 'Tricount-Exporter/Imported'
  prompt_string_config notification_email 'Notification email (blank uses the installing account)' ''
  prompt_boolean_config archive_processed_threads 'Archive successfully processed threads' true
  prompt_boolean_config send_success_notification 'Send a success notification email' true
  prompt_number_config run_interval_hours 'Polling interval in hours' 12
}

prompt_string_config() {
  local key="$1"
  local prompt="$2"
  local display_default="$3"
  local value
  printf '%s [%s]: ' "${prompt}" "${display_default}"
  IFS= read -r value </dev/tty || return
  if [[ -n "${value}" ]]; then
    set_config_string "${key}" "${value}"
  fi
}

prompt_boolean_config() {
  local key="$1"
  local prompt="$2"
  local default_value="$3"
  local value
  printf '%s [%s]: ' "${prompt}" "${default_value}"
  IFS= read -r value </dev/tty || return
  case "${value}" in
    '') ;;
    y|Y|yes|YES|true|TRUE) set_config_json "${key}" true ;;
    n|N|no|NO|false|FALSE) set_config_json "${key}" false ;;
    *) die "Invalid boolean for ${key}: ${value}" ;;
  esac
}

prompt_number_config() {
  local key="$1"
  local prompt="$2"
  local default_value="$3"
  local value
  printf '%s [%s]: ' "${prompt}" "${default_value}"
  IFS= read -r value </dev/tty || return
  if [[ -n "${value}" ]]; then
    set_config_json "${key}" "${value}"
  fi
}

resolve_oauth_client() {
  local client_file
  if [[ -n "${TRICOUNT_EXPORTER_OAUTH_CLIENT_JSON:-}" ]]; then
    client_file="${TRICOUNT_EXPORTER_OAUTH_CLIENT_JSON}"
  else
    local candidates=("${PROJECT_ROOT}"/client_secret_*.apps.googleusercontent.com.json)
    if [[ "${#candidates[@]}" -ne 1 || ! -f "${candidates[0]}" ]]; then
      die 'Set TRICOUNT_EXPORTER_OAUTH_CLIENT_JSON to the private Desktop OAuth client JSON.'
    fi
    client_file="${candidates[0]}"
  fi
  [[ -f "${client_file}" ]] || die "OAuth client JSON not found: ${client_file}"
  jq -e '(.installed.client_id | type == "string" and length > 0) and
    (.installed.client_secret | type == "string" and length > 0)' \
    "${client_file}" >/dev/null || die 'OAuth client JSON is not a Desktop OAuth client.'
  printf '%s\n' "${client_file}"
}

clasp() {
  "${CLASP[@]}" -A "${AUTH_FILE}" "$@"
}

ensure_owner_authorization() {
  local authorization authorization_status client_file
  if [[ -f "${AUTH_FILE}" ]]; then
    set +e
    authorization="$(clasp --json show-authorized-user 2>/dev/null)"
    authorization_status=$?
    set -e
    if [[ "${authorization_status}" -eq 0 ]] && jq -e \
      '.loggedIn == true and (.email | type == "string" and length > 0)' \
      <<<"${authorization}" >/dev/null; then
      info 'Reusing private owner authorization.'
      return
    fi
    rm -rf "${AUTH_DIR}"
  fi
  client_file="$(resolve_oauth_client)"
  mkdir -p "${AUTH_DIR}"
  chmod 700 "${AUTH_DIR}"
  (
    cd "${SOURCE_DIR}"
    clasp login --creds "${client_file}" --use-project-scopes --include-clasp-scopes
  )
  chmod 600 "${AUTH_FILE}"
  authorization="$(clasp --json show-authorized-user)"
  jq -e '.loggedIn == true and (.email | type == "string" and length > 0)' \
    <<<"${authorization}" >/dev/null || die 'Private owner authorization did not complete.'
}

require_owner_authorization() {
  local authorization authorization_status
  [[ -f "${AUTH_FILE}" ]] || die \
    'Private owner authorization is missing. Run make apps-script-install to authorize again.'
  set +e
  authorization="$(clasp --json show-authorized-user 2>/dev/null)"
  authorization_status=$?
  set -e
  if [[ "${authorization_status}" -ne 0 ]] || ! jq -e \
    '.loggedIn == true and (.email | type == "string" and length > 0)' \
    <<<"${authorization}" >/dev/null; then
    die 'Private owner authorization is stale. Run make apps-script-install to authorize again.'
  fi
}

install_check() {
  require_command jq
  require_command node
  require_command npx
  require_command openssl
  "${CLASP[@]}" --version >/dev/null
  node "${PROJECT_ROOT}/scripts/validate-apps-script.js"
  info 'Local prerequisites and Apps Script source are valid.'
}

prepare_source() {
  local time_zone
  time_zone="$(jq -er '.time_zone' "${CONFIG_FILE}")"
  rm -rf "${SOURCE_DIR}"
  mkdir -p "${SOURCE_DIR}"
  cp -R "${APPS_SOURCE_DIR}/." "${SOURCE_DIR}/"
  if [[ -f "${CLASP_FILE}" ]]; then
    cp "${CLASP_FILE}" "${SOURCE_DIR}/.clasp.json"
  fi
  jq --arg time_zone "${time_zone}" \
    '.timeZone = $time_zone' "${SOURCE_DIR}/appsscript.json" >"${SOURCE_DIR}/appsscript.json.tmp"
  mv "${SOURCE_DIR}/appsscript.json.tmp" "${SOURCE_DIR}/appsscript.json"
}

ensure_script_project() {
  local script_id
  if [[ ! -f "${SOURCE_DIR}/.clasp.json" ]]; then
    (
      cd "${SOURCE_DIR}"
      clasp create --type standalone --title='Tricount-Exporter'
    )
  fi
  script_id="$(jq -er '.scriptId | select(type == "string" and length > 0)' "${SOURCE_DIR}/.clasp.json")"
  cp "${SOURCE_DIR}/.clasp.json" "${CLASP_FILE}"
  chmod 600 "${CLASP_FILE}"
  state_set scriptId "${script_id}"
}

push_source() {
  (
    cd "${SOURCE_DIR}"
    clasp push --force
  )
}

ensure_api_deployment() {
  local deployment_output deployment_id deployment_status
  deployment_id="$(jq -r '.deploymentId // empty' "${STATE_FILE}")"
  set +e
  if [[ -n "${deployment_id}" ]]; then
    deployment_output="$(
      cd "${SOURCE_DIR}"
      clasp --json deploy --deploymentId="${deployment_id}" \
        --description='Tricount-Exporter automation'
    )"
  else
    deployment_output="$(
      cd "${SOURCE_DIR}"
      clasp --json deploy --description='Tricount-Exporter automation'
    )"
  fi
  deployment_status=$?
  set -e
  if [[ "${deployment_status}" -ne 0 ]]; then
    printf '%s\n' "${deployment_output}" >&2
    die 'Apps Script execution deployment failed.'
  fi
  if [[ -z "${deployment_id}" ]]; then
    deployment_id="$(jq -er '.deploymentId | select(type == "string" and length > 0)' <<<"${deployment_output}")"
    state_set deploymentId "${deployment_id}"
  fi
}

generate_public_key() {
  local public_key="$1"
  local private_key
  private_key="$(mktemp "${STATE_DIR}/rsa-private.XXXXXX")"
  chmod 600 "${private_key}"
  if ! openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "${private_key}" >/dev/null 2>&1; then
    rm -f "${private_key}"
    return 1
  fi
  if ! openssl rsa -pubout -in "${private_key}" -out "${public_key}" >/dev/null 2>&1; then
    rm -f "${private_key}" "${public_key}"
    return 1
  fi
  rm -f "${private_key}"
}

bootstrap_script() {
  local bootstrap_status config_json options output parameters public_key public_key_file root_folder_id
  public_key_file="$(mktemp "${STATE_DIR}/rsa-public.XXXXXX")"
  chmod 600 "${public_key_file}"
  generate_public_key "${public_key_file}"
  public_key="$(<"${public_key_file}")"
  rm -f "${public_key_file}"
  config_json="$(jq -ce . "${CONFIG_FILE}")"
  options="$(jq -cn --arg publicKeyPem "${public_key}" --argjson config "${config_json}" \
    '{publicKeyPem:$publicKeyPem,config:$config}')"
  unset public_key
  parameters="$(jq -cn --argjson options "${options}" '[ $options ]')"
  set +e
  output="$(
    cd "${SOURCE_DIR}"
    clasp --json run bootstrapThreeCountExporterInstallation --params "${parameters}"
  )"
  bootstrap_status=$?
  set -e
  if [[ "${bootstrap_status}" -ne 0 ]]; then
    printf '%s\n' "${output}" >&2
    die 'Apps Script bootstrap failed.'
  fi
  if ! jq -e '.response.installed == true' <<<"${output}" >/dev/null; then
    printf '%s\n' "${output}" >&2
    die 'Apps Script bootstrap did not report success.'
  fi
  root_folder_id="$(jq -er '.response.driveRootId | select(type == "string" and length > 0)' <<<"${output}")"
  state_set driveRootFolderId "${root_folder_id}"
}

show_status() {
  [[ -f "${CLASP_FILE}" ]] || die 'No installed Apps Script mapping exists. Run make apps-script-install first.'
  (
    cd "${STATE_DIR}"
    clasp --json run validateThreeCountExporterInstallation
  )
}

uninstall() {
  [[ "${TRICOUNT_EXPORTER_CONFIRM_UNINSTALL:-}" == 'DELETE' ]] || die \
    'Set TRICOUNT_EXPORTER_CONFIRM_UNINSTALL=DELETE to remove the managed trigger.'
  [[ -f "${CLASP_FILE}" ]] || die 'No installed Apps Script mapping exists.'
  (
    cd "${STATE_DIR}"
    clasp --json run removeThreeCountAutomationTrigger >/dev/null
  )
  info 'Managed daily trigger removed. The Apps Script project and Drive exports were preserved.'
}

main() {
  case "${MODE}" in
    check)
      install_check
      return
      ;;
    status)
      install_check
      ensure_state_dir
      require_owner_authorization
      show_status
      return
      ;;
    uninstall)
      install_check
      ensure_state_dir
      ensure_owner_authorization
      uninstall
      return
      ;;
    install) ;;
    *) die 'Unsupported mode.' ;;
  esac
  ensure_state_dir
  ensure_config
  install_check
  prepare_source
  ensure_owner_authorization
  ensure_script_project
  push_source
  ensure_api_deployment
  bootstrap_script
  info 'Installation complete. The cloud automation now runs without this computer.'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) MODE='check' ;;
    --status) MODE='status' ;;
    --uninstall) MODE='uninstall' ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done

main
