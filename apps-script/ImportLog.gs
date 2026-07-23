const THREE_COUNT_IMPORT_LOG_FILE_NAME = 'tricount-exporter-import-log.csv';
const THREE_COUNT_IMPORT_LOG_HEADERS = Object.freeze([
  'logged_at',
  'status',
  'tricount_title',
  'tricount_url',
  'export_folder_url',
  'gmail_message_url',
  'gmail_message_id',
  'email_received_at',
  'attachments_downloaded',
  'attachment_failures',
  'notification_status',
  'error'
]);

function appendThreeCountImportLog_(entry) {
  const root = getThreeCountRootFolder_();
  const file = ensureThreeCountImportLog_(root);
  const existing = file.getBlob().getDataAsString('UTF-8');
  const exported = entry.exported || {};
  const row = [
    new Date().toISOString(),
    entry.status || '',
    exported.title || '',
    entry.share && entry.share.sourceUrl || '',
    exported.folderUrl || '',
    getThreeCountGmailMessageUrl_(entry.message),
    entry.message && entry.message.getId() || '',
    entry.message && entry.message.getDate().toISOString() || '',
    Number(exported.attachmentCount || 0),
    Number(exported.attachmentFailures || 0),
    entry.notificationStatus || '',
    entry.errorMessage || ''
  ].map(escapeThreeCountCsvValue_).join(',') + '\n';
  file.setContent(existing + row);
  return file;
}

function ensureThreeCountImportLog_(root) {
  const header = THREE_COUNT_IMPORT_LOG_HEADERS.join(',');
  for (let suffix = 1; suffix <= 1000; suffix += 1) {
    const name = getThreeCountImportLogFileName_(suffix);
    const files = root.getFilesByName(name);
    let foundFile = false;
    while (files.hasNext()) {
      foundFile = true;
      const file = files.next();
      if (hasThreeCountImportLogHeader_(file, header)) {
        return file;
      }
    }
    if (!foundFile) {
      return root.createFile(name, header + '\n', 'text/csv');
    }
  }
  throw new Error('Could not allocate a collision-safe Tricount import log file.');
}

function getThreeCountImportLogFileName_(suffix) {
  if (suffix === 1) {
    return THREE_COUNT_IMPORT_LOG_FILE_NAME;
  }
  return THREE_COUNT_IMPORT_LOG_FILE_NAME.replace(/\.csv$/, '-' + suffix + '.csv');
}

function hasThreeCountImportLogHeader_(file, header) {
  try {
    const content = file.getBlob().getDataAsString('UTF-8');
    return content.split(/\r?\n/, 1)[0] === header;
  } catch (error) {
    return false;
  }
}

function getThreeCountGmailMessageUrl_(message) {
  if (!message) {
    return '';
  }
  return 'https://mail.google.com/mail/u/0/#all/' + encodeURIComponent(message.getId());
}

function escapeThreeCountCsvValue_(value) {
  let text = String(value === undefined || value === null ? '' : value);
  if (/^[=+\-@]/.test(text)) {
    text = "'" + text;
  }
  return '"' + text.replace(/"/g, '""') + '"';
}
