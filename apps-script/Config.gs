const THREE_COUNT_CONFIG = Object.freeze({
  APP_VERSION: '0.3.0',
  API_BASE_URL: 'https://api.tricount.bunq.com',
  DAILY_HANDLER: 'runDailyThreeCountExporter',
  MAX_RUNTIME_MS: 280000,
  PROPERTY_KEYS: Object.freeze({
    AUTOMATION_CONFIG_JSON: 'AUTOMATION_CONFIG_JSON',
    DRIVE_ROOT_FOLDER_ID: 'DRIVE_ROOT_FOLDER_ID',
    INSTALLER_COMPLETED_AT: 'INSTALLER_COMPLETED_AT',
    PROCESSED_RECORDS_MANIFEST_JSON: 'PROCESSED_RECORDS_MANIFEST_JSON',
    PROCESSED_RECORDS_JSON: 'PROCESSED_RECORDS_JSON',
    PROCESSED_RECORDS_SHARD_PREFIX: 'PROCESSED_RECORDS_V2_',
    TRICOUNT_PUBLIC_KEY_PEM: 'TRICOUNT_PUBLIC_KEY_PEM'
  })
});

function getThreeCountSetupStatus() {
  const properties = PropertiesService.getScriptProperties();
  const triggerStatus = getThreeCountTriggerStatus_();
  return {
    applicationVersion: THREE_COUNT_CONFIG.APP_VERSION,
    configured: Boolean(properties.getProperty(THREE_COUNT_CONFIG.PROPERTY_KEYS.AUTOMATION_CONFIG_JSON)),
    driveRootConfigured: Boolean(properties.getProperty(THREE_COUNT_CONFIG.PROPERTY_KEYS.DRIVE_ROOT_FOLDER_ID)),
    publicKeyConfigured: Boolean(properties.getProperty(THREE_COUNT_CONFIG.PROPERTY_KEYS.TRICOUNT_PUBLIC_KEY_PEM)),
    triggerCounts: triggerStatus.triggerCounts,
    missingTriggerHandlers: triggerStatus.missingTriggerHandlers,
    duplicateTriggerHandlers: triggerStatus.duplicateTriggerHandlers
  };
}

function getThreeCountConfig_() {
  const raw = PropertiesService.getScriptProperties().getProperty(
    THREE_COUNT_CONFIG.PROPERTY_KEYS.AUTOMATION_CONFIG_JSON
  );
  if (!raw) {
    throw new Error('Tricount-Exporter has not been configured.');
  }
  let config;
  try {
    config = JSON.parse(raw);
  } catch (error) {
    throw new Error('AUTOMATION_CONFIG_JSON is invalid: ' + error.message);
  }
  validateThreeCountConfig_(config);
  return config;
}

function validateThreeCountConfig_(config) {
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    throw new Error('Automation configuration must be an object.');
  }
  ['time_zone', 'gmail_query', 'drive_folder_name'].forEach(function (key) {
    if (!String(config[key] || '').trim()) {
      throw new Error('Automation configuration requires ' + key + '.');
    }
  });
  ['run_interval_hours', 'lookback_days', 'max_messages_per_run', 'max_attachments_per_run']
    .forEach(function (key) {
      if (!Number.isInteger(config[key]) || config[key] < 1) {
        throw new Error('Automation configuration requires a positive integer ' + key + '.');
      }
    });
  if (config.run_interval_hours > 23 || config.max_messages_per_run > 500 ||
    config.max_attachments_per_run > 500) {
    throw new Error('Automation configuration exceeds the supported bounds.');
  }
  ['archive_processed_threads', 'send_success_notification'].forEach(function (key) {
    if (typeof config[key] !== 'boolean') {
      throw new Error('Automation configuration requires boolean ' + key + '.');
    }
  });
  if (typeof config.notification_email !== 'string') {
    throw new Error('Automation configuration requires string notification_email.');
  }
  const outputFolderUrl = String(config.drive_output_folder_url || '').trim();
  if (outputFolderUrl) {
    extractThreeCountDriveFolderId_(outputFolderUrl);
  }
}

function getThreeCountRootFolder_() {
  const folderId = PropertiesService.getScriptProperties().getProperty(
    THREE_COUNT_CONFIG.PROPERTY_KEYS.DRIVE_ROOT_FOLDER_ID
  );
  if (!folderId) {
    throw new Error('DRIVE_ROOT_FOLDER_ID is not configured.');
  }
  return DriveApp.getFolderById(folderId);
}

function getThreeCountPublicKey_() {
  const publicKey = PropertiesService.getScriptProperties().getProperty(
    THREE_COUNT_CONFIG.PROPERTY_KEYS.TRICOUNT_PUBLIC_KEY_PEM
  );
  if (!publicKey || publicKey.indexOf('BEGIN PUBLIC KEY') < 0) {
    throw new Error('TRICOUNT_PUBLIC_KEY_PEM is not configured.');
  }
  return publicKey;
}

function assertThreeCountConfiguration_() {
  getThreeCountConfig_();
  getThreeCountRootFolder_();
  getThreeCountPublicKey_();
}
