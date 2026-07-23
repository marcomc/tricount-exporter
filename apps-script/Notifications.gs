function sendThreeCountSuccessNotification_(message, share, exported, config) {
  if (!config.send_success_notification) {
    return 'disabled';
  }
  const recipient = String(config.notification_email || Session.getEffectiveUser().getEmail() || '').trim();
  if (!recipient) {
    return 'not-sent:no-recipient';
  }
  try {
    const title = normalizeThreeCountNotificationText_(exported.title);
    const folderUrl = normalizeThreeCountNotificationText_(exported.folderUrl);
    const sourceUrl = normalizeThreeCountNotificationText_(share.sourceUrl);
    const messageUrl = normalizeThreeCountNotificationText_(getThreeCountGmailMessageUrl_(message));
    MailApp.sendEmail({
      to: recipient,
      subject: '[Tricount-Exporter] Imported: ' + title,
      body: [
        'Tricount imported successfully.',
        '',
        'Title: ' + title,
        'Export folder: ' + folderUrl,
        'Tricount URL: ' + sourceUrl,
        'Source Gmail message: ' + messageUrl,
        'Attachments downloaded: ' + exported.attachmentCount,
        'Attachment failures: ' + exported.attachmentFailures
      ].join('\n')
    });
    return 'sent';
  } catch (error) {
    console.warn('Tricount success notification failed: ' + String(error.message || error));
    return 'not-sent:' + String(error.message || error);
  }
}

function normalizeThreeCountNotificationText_(value) {
  return String(value === undefined || value === null ? '' : value)
    .replace(/[\u0000-\u001F\u007F]/g, ' ').trim();
}
