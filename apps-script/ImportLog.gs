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
  const existing = findThreeCountFileByName_(root, THREE_COUNT_IMPORT_LOG_FILE_NAME);
  if (existing) {
    return existing;
  }
  return root.createFile(
    THREE_COUNT_IMPORT_LOG_FILE_NAME,
    THREE_COUNT_IMPORT_LOG_HEADERS.join(',') + '\n',
    'text/csv'
  );
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
