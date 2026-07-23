#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..', 'apps-script');
const read = (name) => fs.readFileSync(path.join(root, name), 'utf8');
const projectRoot = path.resolve(__dirname, '..');
const gmailIntake = read('GmailIntake.gs');
const api = read('TricountApi.gs');
const drive = read('DriveExport.gs');
const importLog = read('ImportLog.gs');
const installer = read('Installer.gs');
const notifications = read('Notifications.gs');
const automation = read('Automation.gs');
const manifest = JSON.parse(read('appsscript.json'));

const installerConfig = JSON.parse(fs.readFileSync(
  path.join(projectRoot, 'config.apps-script.example.json'),
  'utf8'
));
assert.match(installerConfig.gmail_query, /subject:tricount/);
assert.equal(
  installerConfig.processed_label_name,
  'Tricount-Exporter/Imported'
);
assert.equal(installerConfig.drive_output_folder_url, '');
assert.equal(installerConfig.run_interval_hours, 12);
assert.equal(installerConfig.archive_processed_threads, true);
assert.equal(installerConfig.send_success_notification, true);
assert.match(gmailIntake, /host !== 'tricount\.com' && !host\.endsWith\('\.tricount\.com'\)/);
assert.doesNotMatch(gmailIntake, /endsWith\('tricount\.com'\)\) \{/);
assert.match(gmailIntake, /message\.getPlainBody\(\)/);
assert.match(api, /session-registry-installation/);
assert.match(api, /public_identifier_token/);
assert.match(drive, /folder\.createFile\(name, content, 'application\/json'\)/);
assert.match(importLog, /tricount-exporter-import-log\.csv/);
assert.match(importLog, /gmail_message_url/);
assert.match(importLog, /text\/csv/);
assert.match(importLog, /notification_status/);
assert.match(installer, /ensureThreeCountImportLog_\(root\)/);
assert.match(api, /attachment_result/);
assert.match(automation, /runDailyThreeCountExporter/);
assert.match(automation, /everyHours\(config\.run_interval_hours\)/);
assert.match(automation, /LockService\.getScriptLock\(\)/);
assert.match(gmailIntake, /threads\[threadIndex\]\.addLabel\(processedLabel\)/);
assert.match(gmailIntake, /thread\.moveToArchive\(\)/);
assert.match(gmailIntake, /const wasUnread = message\.isUnread\(\)/);
assert.match(gmailIntake, /message\.markUnread\(\)/);
assert.match(gmailIntake, /GmailApp\.createLabel\(name\)/);
assert.doesNotMatch(gmailIntake, /markRead\(/);
assert.match(notifications, /MailApp\.sendEmail/);
assert.deepEqual(manifest.executionApi, { access: 'MYSELF' });
assert.ok(manifest.oauthScopes.includes('https://mail.google.com/'));
assert.ok(manifest.oauthScopes.includes('https://www.googleapis.com/auth/drive'));
assert.ok(manifest.oauthScopes.includes('https://www.googleapis.com/auth/cloud-platform'));
assert.ok(manifest.oauthScopes.includes('https://www.googleapis.com/auth/script.send_mail'));

const appsScriptSandbox = vm.createContext({
  URL: undefined,
  decodeURIComponent,
});
vm.runInContext(gmailIntake, appsScriptSandbox);
assert.deepEqual(
  JSON.parse(JSON.stringify(appsScriptSandbox.normalizeThreeCountShareUrl_(
    'https://tricount.com/tfMjRIbpOmaoxdtCtd'
  ))),
  {
    key: 'tfMjRIbpOmaoxdtCtd',
    sourceUrl: 'https://tricount.com/tfMjRIbpOmaoxdtCtd',
  }
);
assert.equal(
  appsScriptSandbox.normalizeThreeCountShareUrl_('https://nottricount.com/tfMjRIbpOmaoxdtCtd'),
  null
);

const installerSandbox = vm.createContext({});
vm.runInContext(installer, installerSandbox);
assert.equal(
  installerSandbox.extractThreeCountDriveFolderId_(
    'https://drive.google.com/drive/folders/11vrL7GscWwahSFm4X3HTSQuF0GikrE1E?usp=share_link'
  ),
  '11vrL7GscWwahSFm4X3HTSQuF0GikrE1E'
);
assert.throws(
  () => installerSandbox.extractThreeCountDriveFolderId_('https://example.com/folder'),
  /Google Drive folder URL/
);

console.log('Apps Script contract tests passed.');
