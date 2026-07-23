function runThreeCountExporter_() {
  assertThreeCountConfiguration_();
  const config = getThreeCountConfig_();
  const processed = getProcessedThreeCountRecords_();
  const processedLabel = getOrCreateThreeCountProcessedLabel_(config);
  const summary = { scannedMessages: 0, discoveredUrls: 0, exported: [], skipped: [], errors: [] };
  const cutoff = new Date(Date.now() - config.lookback_days * 24 * 60 * 60 * 1000);
  let offset = 0;
  const pageSize = Math.min(100, config.max_messages_per_run);

  while (summary.scannedMessages < config.max_messages_per_run) {
    const threads = GmailApp.search(config.gmail_query, offset, pageSize);
    if (!threads.length) {
      break;
    }
    offset += threads.length;
    for (let threadIndex = 0; threadIndex < threads.length; threadIndex += 1) {
      const thread = threads[threadIndex];
      const messages = thread.getMessages();
      let shouldFinalizeThread = false;
      let threadHasFailure = false;
      for (let messageIndex = 0; messageIndex < messages.length; messageIndex += 1) {
        if (summary.scannedMessages >= config.max_messages_per_run) {
          break;
        }
        const message = messages[messageIndex];
        summary.scannedMessages += 1;
        if (message.getDate() < cutoff || !isThreeCountInvitationSubject_(message.getSubject())) {
          continue;
        }
        const shares = extractThreeCountShareUrls_(message.getPlainBody());
        for (let shareIndex = 0; shareIndex < shares.length; shareIndex += 1) {
          const share = shares[shareIndex];
          summary.discoveredUrls += 1;
          const recordId = message.getId() + ':' + share.key;
          if (processed[recordId]) {
            shouldFinalizeThread = true;
            summary.skipped.push({ messageId: message.getId(), keySuffix: shortThreeCountKey_(share.key) });
            continue;
          }
          try {
            const exported = exportThreeCountShare_(share, message);
            const notificationStatus = sendThreeCountSuccessNotification_(message, share, exported, config);
            appendThreeCountImportLog_({
              status: 'success', message: message, share: share, exported: exported,
              notificationStatus: notificationStatus
            });
            processed[recordId] = new Date().toISOString();
            shouldFinalizeThread = true;
            summary.exported.push(exported);
          } catch (error) {
            const errorMessage = String(error.message || error);
            try {
              appendThreeCountImportLog_({
                status: 'failed', message: message, share: share, errorMessage: errorMessage
              });
            } catch (logError) {
              summary.errors.push({
                keySuffix: shortThreeCountKey_(share.key),
                error: errorMessage + ' Audit log failure: ' + String(logError.message || logError)
              });
              threadHasFailure = true;
              continue;
            }
            threadHasFailure = true;
            summary.errors.push({ keySuffix: shortThreeCountKey_(share.key), error: errorMessage });
          }
        }
      }
      if (shouldFinalizeThread && !threadHasFailure) {
        try {
          thread.addLabel(processedLabel);
          archiveThreeCountProcessedThread_(thread, config);
        } catch (error) {
          summary.errors.push({
            threadId: thread.getId(),
            error: 'Could not finalize processed Gmail thread: ' + String(error.message || error)
          });
        }
      }
    }
    if (threads.length < pageSize) {
      break;
    }
  }
  saveProcessedThreeCountRecords_(processed);
  console.log(JSON.stringify({
    event: 'three_count_export_complete', scannedMessages: summary.scannedMessages,
    discoveredUrls: summary.discoveredUrls, exported: summary.exported.length,
    skipped: summary.skipped.length, errors: summary.errors.length
  }));
  return summary;
}

function archiveThreeCountProcessedThread_(thread, config) {
  if (config.archive_processed_threads) {
    const unreadMessages = thread.getMessages().filter(function (threadMessage) {
      return threadMessage.isUnread();
    });
    thread.moveToArchive();
    unreadMessages.forEach(function (threadMessage) { threadMessage.markUnread(); });
  }
}

function getOrCreateThreeCountProcessedLabel_(config) {
  const name = String(config.processed_label_name ||
    'Tricount-Exporter/Imported').trim();
  if (!name) {
    throw new Error('Automation configuration requires processed_label_name.');
  }
  const existing = GmailApp.getUserLabelByName(name);
  return existing || GmailApp.createLabel(name);
}

function isThreeCountInvitationSubject_(subject) {
  return String(subject || '').toLowerCase().indexOf('tricount') >= 0;
}

function extractThreeCountShareUrls_(body) {
  const candidates = String(body || '').match(/https:\/\/[^\s<>"')\]}]+/gi) || [];
  const found = {};
  candidates.forEach(function (candidate) {
    const normalized = normalizeThreeCountShareUrl_(candidate);
    if (normalized) {
      found[normalized.key] = normalized;
    }
  });
  return Object.keys(found).sort().map(function (key) { return found[key]; });
}

function normalizeThreeCountShareUrl_(value) {
  const candidate = String(value || '').trim();
  const match = /^https:\/\/([^/?#]+)(\/[^?#]*)?(?:\?([^#]*))?(?:#.*)?$/i.exec(candidate);
  if (!match) {
    return null;
  }
  const host = match[1].toLowerCase().replace(/\.$/, '');
  if (!/^[a-z0-9-]+(?:\.[a-z0-9-]+)*$/i.test(host) ||
    (host !== 'tricount.com' && !host.endsWith('.tricount.com'))) {
    return null;
  }
  const queryKeys = ['public_identifier_token', 'token', 'key'];
  const queryValues = parseThreeCountQuery_(match[3] || '');
  let key = '';
  for (let index = 0; index < queryKeys.length; index += 1) {
    key = queryValues[queryKeys[index]] || '';
    if (key.trim()) {
      break;
    }
  }
  if (!key.trim()) {
    const parts = (match[2] || '').split('/').filter(function (part) { return part.trim(); });
    key = parts.length ? decodeThreeCountUrlComponent_(parts[parts.length - 1]) : '';
  }
  key = String(key || '').trim();
  if (!key || key.length > 512) {
    return null;
  }
  return { key: key, sourceUrl: candidate };
}

function parseThreeCountQuery_(query) {
  const values = {};
  String(query || '').split('&').forEach(function (component) {
    const separator = component.indexOf('=');
    const rawName = separator < 0 ? component : component.slice(0, separator);
    const rawValue = separator < 0 ? '' : component.slice(separator + 1);
    const name = decodeThreeCountUrlComponent_(rawName);
    if (name && !Object.prototype.hasOwnProperty.call(values, name)) {
      values[name] = decodeThreeCountUrlComponent_(rawValue);
    }
  });
  return values;
}

function decodeThreeCountUrlComponent_(value) {
  try {
    return decodeURIComponent(String(value || '').replace(/\+/g, ' '));
  } catch (error) {
    return '';
  }
}

function getProcessedThreeCountRecords_() {
  const raw = PropertiesService.getScriptProperties().getProperty(
    THREE_COUNT_CONFIG.PROPERTY_KEYS.PROCESSED_RECORDS_JSON
  );
  if (!raw) {
    return {};
  }
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch (error) {
    throw new Error('Processed-record state is invalid.');
  }
}

function saveProcessedThreeCountRecords_(records) {
  const kept = {};
  Object.keys(records).sort(function (left, right) {
    return String(records[right]).localeCompare(String(records[left]));
  }).slice(0, 1000).forEach(function (recordId) {
    kept[recordId] = records[recordId];
  });
  PropertiesService.getScriptProperties().setProperty(
    THREE_COUNT_CONFIG.PROPERTY_KEYS.PROCESSED_RECORDS_JSON,
    JSON.stringify(kept)
  );
}
