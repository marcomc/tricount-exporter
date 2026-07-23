/** Owner-only bootstrap invoked by the local installer. */
function bootstrapThreeCountExporterInstallation(options) {
  const validated = validateThreeCountInstallerOptions_(options);
  const root = resolveThreeCountRootFolder_(validated.config);
  const properties = PropertiesService.getScriptProperties();
  properties.setProperties({
    AUTOMATION_CONFIG_JSON: JSON.stringify(validated.config),
    DRIVE_ROOT_FOLDER_ID: root.getId(),
    TRICOUNT_PUBLIC_KEY_PEM: validated.publicKeyPem,
    INSTALLER_COMPLETED_AT: new Date().toISOString()
  }, false);
  ensureThreeCountImportLog_(root);
  installThreeCountAutomationTrigger();
  const status = validateThreeCountExporterInstallation();
  return {
    installed: status.installed,
    driveRootId: root.getId(),
    driveRootUrl: root.getUrl(),
    triggerCounts: status.triggerCounts
  };
}

function validateThreeCountExporterInstallation() {
  assertThreeCountConfiguration_();
  const triggerStatus = getThreeCountTriggerStatus_();
  return {
    installed: triggerStatus.missingTriggerHandlers.length === 0 &&
      triggerStatus.duplicateTriggerHandlers.length === 0,
    driveRootUrl: getThreeCountRootFolder_().getUrl(),
    triggerCounts: triggerStatus.triggerCounts,
    missingTriggerHandlers: triggerStatus.missingTriggerHandlers,
    duplicateTriggerHandlers: triggerStatus.duplicateTriggerHandlers
  };
}

function validateThreeCountInstallerOptions_(options) {
  if (!options || typeof options !== 'object' || Array.isArray(options)) {
    throw new Error('Installer options must be an object.');
  }
  const config = options.config;
  validateThreeCountConfig_(config);
  const publicKeyPem = String(options.publicKeyPem || '').trim();
  if (publicKeyPem.indexOf('BEGIN PUBLIC KEY') < 0 || publicKeyPem.length < 200) {
    throw new Error('A valid 2048-bit public PEM is required.');
  }
  return { config: config, publicKeyPem: publicKeyPem };
}

function resolveThreeCountRootFolder_(config) {
  const configuredUrl = String(config.drive_output_folder_url || '').trim();
  if (configuredUrl) {
    return DriveApp.getFolderById(extractThreeCountDriveFolderId_(configuredUrl));
  }
  return findOrCreateThreeCountRootFolder_(config.drive_folder_name);
}

function extractThreeCountDriveFolderId_(url) {
  const match = /^https:\/\/drive\.google\.com\/drive\/(?:u\/\d+\/)?folders\/([A-Za-z0-9_-]+)(?:[/?#].*)?$/
    .exec(String(url || '').trim());
  if (!match) {
    throw new Error('drive_output_folder_url must be a Google Drive folder URL.');
  }
  return match[1];
}

function findOrCreateThreeCountRootFolder_(name) {
  const folders = DriveApp.getFoldersByName(name);
  if (folders.hasNext()) {
    return folders.next();
  }
  return DriveApp.createFolder(name);
}
