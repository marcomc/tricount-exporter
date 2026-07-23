function sendThreeCountSuccessNotification_(message, share, exported, config) {
  if (!config.send_success_notification) {
    return 'disabled';
  }
  const recipient = String(config.notification_email || Session.getEffectiveUser().getEmail() || '').trim();
  if (!recipient) {
    return 'not-sent:no-recipient';
  }
  try {
    MailApp.sendEmail({
      to: recipient,
      subject: '[Tricount-Exporter] Imported: ' + exported.title,
      body: [
        'Tricount imported successfully.',
        '',
        'Title: ' + exported.title,
        'Export folder: ' + exported.folderUrl,
        'Tricount URL: ' + share.sourceUrl,
        'Source Gmail message: ' + getThreeCountGmailMessageUrl_(message),
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
