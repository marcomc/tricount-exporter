const THREE_COUNT_PROCESSED_RECORD_LIMIT = 1000;
const THREE_COUNT_PROCESSED_SHARD_MAX_BYTES = 8000;

function runThreeCountExporter_() {
  assertThreeCountConfiguration_();
  const config = getThreeCountConfig_();
  const processed = getProcessedThreeCountRecords_();
  const processedLabel = getOrCreateThreeCountProcessedLabel_(config);
  const summary = {
    scannedMessages: 0, eligibleMessages: 0, discoveredUrls: 0,
    shareAttempts: 0, shareLimitReached: false,
    exported: [], skipped: [], errors: []
  };
  const cutoff = new Date(Date.now() - config.lookback_days * 24 * 60 * 60 * 1000);
  const pageSize = Math.min(100, config.max_messages_per_run);
  const seenThreadIds = {};
  const attachmentBudget = { remaining: config.max_attachments_per_run };
  const shareBudget = { remaining: config.max_share_urls_per_run };

  while (summary.eligibleMessages < config.max_messages_per_run &&
    shareBudget.remaining > 0 && !summary.shareLimitReached) {
    const threads = findUnseenThreeCountThreads_(
      config.gmail_query, pageSize, seenThreadIds
    );
    if (!threads.length) {
      break;
    }
    for (let threadIndex = 0;
      threadIndex < threads.length &&
      summary.eligibleMessages < config.max_messages_per_run &&
      shareBudget.remaining > 0 && !summary.shareLimitReached;
      threadIndex += 1) {
      const thread = threads[threadIndex];
      seenThreadIds[thread.getId()] = true;
      const messages = thread.getMessages();
      let shouldFinalizeThread = false;
      let threadHasFailure = false;
      let threadIncomplete = false;
      for (let messageIndex = 0; messageIndex < messages.length; messageIndex += 1) {
        const message = messages[messageIndex];
        summary.scannedMessages += 1;
        if (message.getDate() < cutoff || !isThreeCountInvitationSubject_(message.getSubject())) {
          continue;
        }
        const shares = extractThreeCountShareUrls_(message.getPlainBody());
        if (!shares.length) {
          continue;
        }
        summary.eligibleMessages += 1;
        for (let shareIndex = 0; shareIndex < shares.length; shareIndex += 1) {
          const share = shares[shareIndex];
          summary.discoveredUrls += 1;
          const recordId = getThreeCountProcessedRecordKey_(
            message.getId() + ':' + share.key
          );
          if (processed[recordId]) {
            shouldFinalizeThread = true;
            summary.skipped.push({ messageId: message.getId(), keySuffix: shortThreeCountKey_(share.key) });
            continue;
          }
          if (shareBudget.remaining <= 0) {
            summary.shareLimitReached = true;
            threadIncomplete = true;
            break;
          }
          shareBudget.remaining -= 1;
          summary.shareAttempts += 1;
          try {
            const exported = exportThreeCountShare_(
              share, message, attachmentBudget
            );
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
        if (threadIncomplete) {
          break;
        }
      }
      if (!threadIncomplete && shouldFinalizeThread && !threadHasFailure) {
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
      if (summary.shareLimitReached) {
        break;
      }
    }
  }
  saveProcessedThreeCountRecords_(processed);
  console.log(JSON.stringify({
    event: 'three_count_export_complete', scannedMessages: summary.scannedMessages,
    eligibleMessages: summary.eligibleMessages,
    shareAttempts: summary.shareAttempts,
    shareLimitReached: summary.shareLimitReached,
    discoveredUrls: summary.discoveredUrls, exported: summary.exported.length,
    skipped: summary.skipped.length, errors: summary.errors.length
  }));
  return summary;
}

function findUnseenThreeCountThreads_(query, pageSize, seenThreadIds) {
  let offset = 0;
  while (true) {
    const threads = GmailApp.search(query, offset, pageSize);
    if (!threads.length) {
      return [];
    }
    const unseenThreads = threads.filter(function (thread) {
      return !seenThreadIds[thread.getId()];
    });
    if (unseenThreads.length) {
      return unseenThreads;
    }
    if (threads.length < pageSize) {
      return [];
    }
    offset += threads.length;
  }
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
  const properties = PropertiesService.getScriptProperties();
  const manifestRaw = properties.getProperty(
    THREE_COUNT_CONFIG.PROPERTY_KEYS.PROCESSED_RECORDS_MANIFEST_JSON
  );
  if (manifestRaw) {
    return loadShardedThreeCountProcessedRecords_(properties, manifestRaw);
  }
  const raw = properties.getProperty(
    THREE_COUNT_CONFIG.PROPERTY_KEYS.PROCESSED_RECORDS_JSON
  );
  try {
    const parsed = raw ? JSON.parse(raw) : {};
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('legacy state must be an object');
    }
    const migrated = {};
    Object.keys(parsed).forEach(function (recordId) {
      migrated[getThreeCountProcessedRecordKey_(recordId)] = parsed[recordId];
    });
    return migrated;
  } catch (error) {
    throw new Error('Processed-record state is invalid.');
  }
}

function saveProcessedThreeCountRecords_(records) {
  const normalized = {};
  Object.keys(records).forEach(function (recordId) {
    const recordKey = /^[0-9a-f]{64}$/.test(recordId) ?
      recordId : getThreeCountProcessedRecordKey_(recordId);
    normalized[recordKey] = records[recordId];
  });
  const kept = {};
  Object.keys(normalized).sort(function (left, right) {
    return String(normalized[right]).localeCompare(String(normalized[left]));
  }).slice(0, THREE_COUNT_PROCESSED_RECORD_LIMIT).forEach(function (recordId) {
    kept[recordId] = normalized[recordId];
  });
  const shardValues = shardThreeCountProcessedRecords_(kept);
  const properties = PropertiesService.getScriptProperties();
  const manifestKey =
    THREE_COUNT_CONFIG.PROPERTY_KEYS.PROCESSED_RECORDS_MANIFEST_JSON;
  const previousManifest = parseThreeCountProcessedManifest_(
    properties.getProperty(manifestKey)
  );
  const targetBank = previousManifest && previousManifest.activeBank === 'A' ?
    'B' : 'A';
  deleteThreeCountProcessedRecordBank_(properties, targetBank);
  const shardKeys = shardValues.map(function (shardValue, index) {
    const shardKey =
      THREE_COUNT_CONFIG.PROPERTY_KEYS.PROCESSED_RECORDS_SHARD_PREFIX +
      targetBank + '_' + index;
    properties.setProperty(shardKey, shardValue);
    return shardKey;
  });
  properties.setProperty(manifestKey, JSON.stringify({
    version: 2,
    activeBank: targetBank,
    shards: shardKeys
  }));
  if (previousManifest && previousManifest.activeBank !== targetBank) {
    deleteThreeCountProcessedRecordBank_(
      properties, previousManifest.activeBank
    );
  }
  properties.deleteProperty(
    THREE_COUNT_CONFIG.PROPERTY_KEYS.PROCESSED_RECORDS_JSON
  );
}

function getThreeCountProcessedRecordKey_(recordId) {
  return Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    String(recordId),
    Utilities.Charset.UTF_8
  ).map(function (byte) {
    return ((byte + 256) % 256).toString(16).padStart(2, '0');
  }).join('');
}

function loadShardedThreeCountProcessedRecords_(properties, manifestRaw) {
  const manifest = parseThreeCountProcessedManifest_(manifestRaw);
  if (!manifest) {
    throw new Error('Processed-record state is invalid.');
  }
  const records = {};
  try {
    manifest.shards.forEach(function (shardKey) {
      const raw = properties.getProperty(shardKey);
      const parsed = raw ? JSON.parse(raw) : null;
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('processed-record shard must be an object');
      }
      Object.keys(parsed).forEach(function (recordKey) {
        if (!/^[0-9a-f]{64}$/.test(recordKey)) {
          throw new Error('processed-record key is invalid');
        }
        records[recordKey] = parsed[recordKey];
      });
    });
  } catch (error) {
    throw new Error('Processed-record state is invalid.');
  }
  return records;
}

function parseThreeCountProcessedManifest_(raw) {
  if (!raw) {
    return null;
  }
  try {
    const manifest = JSON.parse(raw);
    const prefix = THREE_COUNT_CONFIG.PROPERTY_KEYS.PROCESSED_RECORDS_SHARD_PREFIX;
    if (!manifest || manifest.version !== 2 ||
      (manifest.activeBank !== 'A' && manifest.activeBank !== 'B') ||
      !Array.isArray(manifest.shards) ||
      manifest.shards.some(function (shardKey) {
        return !new RegExp(
          '^' + prefix + manifest.activeBank + '_[0-9]+$'
        ).test(shardKey);
      })) {
      return null;
    }
    return manifest;
  } catch (error) {
    return null;
  }
}

function shardThreeCountProcessedRecords_(records) {
  const shards = [];
  let shard = {};
  Object.keys(records).forEach(function (recordKey) {
    const candidate = Object.assign({}, shard);
    candidate[recordKey] = records[recordKey];
    const serialized = JSON.stringify(candidate);
    if (getThreeCountUtf8ByteLength_(serialized) >
      THREE_COUNT_PROCESSED_SHARD_MAX_BYTES) {
      if (!Object.keys(shard).length) {
        throw new Error('A processed-record shard exceeds the storage limit.');
      }
      shards.push(JSON.stringify(shard));
      shard = {};
      shard[recordKey] = records[recordKey];
      if (getThreeCountUtf8ByteLength_(JSON.stringify(shard)) >
        THREE_COUNT_PROCESSED_SHARD_MAX_BYTES) {
        throw new Error('A processed-record shard exceeds the storage limit.');
      }
    } else {
      shard = candidate;
    }
  });
  if (Object.keys(shard).length) {
    shards.push(JSON.stringify(shard));
  }
  return shards;
}

function getThreeCountUtf8ByteLength_(value) {
  return Utilities.newBlob(String(value)).getBytes().length;
}

function deleteThreeCountProcessedRecordBank_(properties, bank) {
  const prefix =
    THREE_COUNT_CONFIG.PROPERTY_KEYS.PROCESSED_RECORDS_SHARD_PREFIX +
    bank + '_';
  Object.keys(properties.getProperties()).forEach(function (propertyKey) {
    if (propertyKey.indexOf(prefix) === 0) {
      properties.deleteProperty(propertyKey);
    }
  });
}
