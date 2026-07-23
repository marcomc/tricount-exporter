#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const appsScriptRoot = path.resolve(__dirname, '..', 'apps-script');
const gmailIntake = fs.readFileSync(
  path.join(appsScriptRoot, 'GmailIntake.gs'),
  'utf8'
);
const configSource = fs.readFileSync(
  path.join(appsScriptRoot, 'Config.gs'),
  'utf8'
);

function createUtilities() {
  return {
    Charset: { UTF_8: 'UTF_8' },
    DigestAlgorithm: { SHA_256: 'SHA_256' },
    computeDigest: (_algorithm, value) => Array.from(
      crypto.createHash('sha256').update(String(value), 'utf8').digest()
    ),
    newBlob: (value) => ({
      getBytes: () => Array.from(Buffer.from(String(value), 'utf8')),
    }),
  };
}

function createMessage({
  body = 'Join: https://tricount.com/EXAMPLE_SHARE_KEY',
  date = new Date(),
  id = 'EXAMPLE_MESSAGE_ID',
  subject = "Hey, I've added you to my tricount",
} = {}) {
  return {
    getDate: () => date,
    getSubject: () => subject,
    getPlainBody: () => body,
    getId: () => id,
    isUnread: () => false,
    markUnread: () => {},
  };
}

function createScenario({
  processed = {},
  exportError = null,
  failingKey = '',
  messages = [createMessage()],
  maxMessages = 100,
  threadCount = 1,
  threadMessages = null,
} = {}) {
  const effects = {
    archived: 0,
    labels: 0,
    logs: [],
    notifications: 0,
    saved: null,
    searchCalls: [],
  };
  const inbox = [];
  const scenarioThreadCount = threadMessages ? threadMessages.length : threadCount;
  for (let index = 0; index < scenarioThreadCount; index += 1) {
    const messagesForThread = threadMessages ? threadMessages[index] :
      threadCount === 1 ? messages : [
      createMessage({
        body: `Join: https://tricount.com/SHARE_KEY_${index}`,
        id: `MESSAGE_${index}`,
      }),
      ];
    const thread = {
      addLabel: () => { effects.labels += 1; },
      getId: () => `THREAD_${index}`,
      getMessages: () => messagesForThread,
      moveToArchive: () => {
        effects.archived += 1;
        const inboxIndex = inbox.indexOf(thread);
        if (inboxIndex >= 0) {
          inbox.splice(inboxIndex, 1);
        }
      },
    };
    inbox.push(thread);
  }
  const sandbox = vm.createContext({
    console: { log: () => {} },
    GmailApp: {
      search: (_query, offset, limit) => {
        effects.searchCalls.push({ offset, limit });
        return inbox.slice(offset, offset + limit);
      },
    },
    Utilities: createUtilities(),
  });
  vm.runInContext(gmailIntake, sandbox);
  const normalizedProcessed = {};
  Object.keys(processed).forEach((recordId) => {
    normalizedProcessed[sandbox.getThreeCountProcessedRecordKey_(recordId)] =
      processed[recordId];
  });
  Object.assign(sandbox, {
    assertThreeCountConfiguration_: () => {},
    getThreeCountConfig_: () => ({
      lookback_days: 30,
      gmail_query: 'in:inbox subject:tricount',
      max_messages_per_run: maxMessages,
      archive_processed_threads: true,
    }),
    getProcessedThreeCountRecords_: () => ({ ...normalizedProcessed }),
    getOrCreateThreeCountProcessedLabel_: () => 'processed-label',
    shortThreeCountKey_: (key) => String(key).slice(-6),
    exportThreeCountShare_: (share) => {
      if (exportError && (!failingKey || share.key === failingKey)) {
        throw exportError;
      }
      return {
        title: 'Example',
        folderUrl: 'https://drive.google.com/example',
        attachmentCount: 0,
        attachmentFailures: 0,
      };
    },
    sendThreeCountSuccessNotification_: () => {
      effects.notifications += 1;
      return 'sent';
    },
    appendThreeCountImportLog_: (entry) => { effects.logs.push(entry); },
    saveProcessedThreeCountRecords_: (records) => {
      effects.saved = { ...records };
    },
  });
  return {
    effects,
    recordKey: (recordId) => sandbox.getThreeCountProcessedRecordKey_(recordId),
    run: sandbox.runThreeCountExporter_,
  };
}

const successful = createScenario();
const successfulSummary = successful.run();
assert.equal(successfulSummary.exported.length, 1);
assert.equal(successful.effects.labels, 1);
assert.equal(successful.effects.archived, 1);
assert.equal(successful.effects.notifications, 1);
assert.equal(successful.effects.logs.length, 1);
assert.equal(successful.effects.logs[0].status, 'success');
assert.ok(successful.effects.saved[
  successful.recordKey('EXAMPLE_MESSAGE_ID:EXAMPLE_SHARE_KEY')
]);

const idempotent = createScenario({
  processed: {
    'EXAMPLE_MESSAGE_ID:EXAMPLE_SHARE_KEY': '2026-07-23T00:00:00.000Z',
  },
  exportError: new Error('known exports must not be fetched again'),
});
const idempotentSummary = idempotent.run();
assert.equal(idempotentSummary.skipped.length, 1);
assert.equal(idempotent.effects.labels, 1);
assert.equal(idempotent.effects.archived, 1);
assert.equal(idempotent.effects.notifications, 0);

const failed = createScenario({
  exportError: new Error('Tricount API failed'),
});
const failedSummary = failed.run();
assert.equal(failedSummary.errors.length, 1);
assert.equal(failed.effects.labels, 0);
assert.equal(failed.effects.archived, 0);
assert.equal(failed.effects.notifications, 0);
assert.equal(failed.effects.logs.length, 1);
assert.equal(failed.effects.logs[0].status, 'failed');
assert.deepEqual(failed.effects.saved, {});

const partial = createScenario({
  messages: [createMessage({
    body: [
      'Join: https://tricount.com/EXAMPLE_SHARE_KEY',
      'https://tricount.com/FAILING_SHARE_KEY',
    ].join(' '),
  })],
  exportError: new Error('Tricount API failed'),
  failingKey: 'FAILING_SHARE_KEY',
});
const partialSummary = partial.run();
assert.equal(partialSummary.exported.length, 1);
assert.equal(partialSummary.errors.length, 1);
assert.equal(partial.effects.labels, 0);
assert.equal(partial.effects.archived, 0);
assert.equal(partial.effects.logs.length, 2);
assert.equal(partial.effects.notifications, 1);
assert.ok(partial.effects.saved[
  partial.recordKey('EXAMPLE_MESSAGE_ID:EXAMPLE_SHARE_KEY')
]);

const cappedThread = createScenario({
  maxMessages: 1,
  messages: [
    createMessage({
      body: 'Join: https://tricount.com/FIRST_KEY',
      id: 'FIRST_MESSAGE',
    }),
    createMessage({
      body: 'Join: https://tricount.com/SECOND_KEY',
      id: 'SECOND_MESSAGE',
    }),
  ],
});
const cappedSummary = cappedThread.run();
assert.equal(cappedSummary.scannedMessages, 2);
assert.equal(cappedSummary.exported.length, 2);
assert.equal(cappedThread.effects.labels, 1);
assert.equal(cappedThread.effects.archived, 1);
assert.ok(cappedThread.effects.saved[
  cappedThread.recordKey('FIRST_MESSAGE:FIRST_KEY')
]);
assert.ok(cappedThread.effects.saved[
  cappedThread.recordKey('SECOND_MESSAGE:SECOND_KEY')
]);

const paginated = createScenario({ maxMessages: 150, threadCount: 150 });
const paginatedSummary = paginated.run();
assert.equal(paginatedSummary.scannedMessages, 150);
assert.equal(paginatedSummary.exported.length, 150);
assert.equal(paginated.effects.archived, 150);
assert.equal(paginated.effects.labels, 150);
assert.ok(paginated.effects.searchCalls.length >= 2);
assert.equal(paginated.effects.searchCalls[0].offset, 0);
assert.equal(paginated.effects.searchCalls[1].offset, 0);

const ineligibleBeforeEligible = createScenario({
  maxMessages: 1,
  threadMessages: [
    [createMessage({
      id: 'WRONG_SUBJECT',
      subject: 'An unrelated inbox message',
    })],
    [createMessage({
      date: new Date('2020-01-01T00:00:00.000Z'),
      id: 'TOO_OLD',
    })],
    [createMessage({
      body: 'Join: https://example.com/NOT_A_TRICOUNT_KEY',
      id: 'NO_VALID_SHARE_URL',
    })],
    [createMessage({
      body: 'Join: https://tricount.com/LATER_ELIGIBLE_KEY',
      id: 'LATER_ELIGIBLE',
    })],
  ],
});
const ineligibleSummary = ineligibleBeforeEligible.run();
assert.equal(ineligibleSummary.scannedMessages, 4);
assert.equal(ineligibleSummary.eligibleMessages, 1);
assert.equal(ineligibleSummary.exported.length, 1);
assert.equal(ineligibleBeforeEligible.effects.labels, 1);
assert.equal(ineligibleBeforeEligible.effects.archived, 1);
assert.ok(ineligibleBeforeEligible.effects.saved[
  ineligibleBeforeEligible.recordKey(
    'LATER_ELIGIBLE:LATER_ELIGIBLE_KEY'
  )
]);

function createPropertyStore(initial = {}) {
  const values = { ...initial };
  const getTotalBytes = () => Object.entries(values).reduce(
    (total, [key, value]) => total +
      Buffer.byteLength(key, 'utf8') +
      Buffer.byteLength(value, 'utf8'),
    0
  );
  let maximumTotalBytes = getTotalBytes();
  const trackTotalBytes = () => {
    maximumTotalBytes = Math.max(maximumTotalBytes, getTotalBytes());
  };
  return {
    deleteProperty: (key) => {
      delete values[key];
      trackTotalBytes();
    },
    getProperties: () => ({ ...values }),
    getProperty: (key) => values[key] ?? null,
    setProperty: (key, value) => {
      values[key] = String(value);
      trackTotalBytes();
    },
    getMaximumTotalBytes: () => maximumTotalBytes,
    values,
  };
}

const legacyRecordId = 'LEGACY_MESSAGE:LEGACY_SHARE_KEY';
const propertyStore = createPropertyStore({
  PROCESSED_RECORDS_JSON: JSON.stringify({
    [legacyRecordId]: '2026-07-22T00:00:00.000Z',
  }),
});
const persistenceSandbox = vm.createContext({
  PropertiesService: { getScriptProperties: () => propertyStore },
  Utilities: createUtilities(),
});
vm.runInContext(configSource, persistenceSandbox);
vm.runInContext(gmailIntake, persistenceSandbox);
const migrated = persistenceSandbox.getProcessedThreeCountRecords_();
const legacyRecordKey =
  persistenceSandbox.getThreeCountProcessedRecordKey_(legacyRecordId);
assert.equal(migrated[legacyRecordKey], '2026-07-22T00:00:00.000Z');
persistenceSandbox.saveProcessedThreeCountRecords_(migrated);
assert.equal(propertyStore.values.PROCESSED_RECORDS_JSON, undefined);
assert.ok(propertyStore.values.PROCESSED_RECORDS_MANIFEST_JSON);
assert.equal(
  persistenceSandbox.getProcessedThreeCountRecords_()[legacyRecordKey],
  '2026-07-22T00:00:00.000Z'
);

const boundaryRecords = {};
for (let index = 0; index < 1000; index += 1) {
  const recordKey = persistenceSandbox.getThreeCountProcessedRecordKey_(
    `MESSAGE_${index}:${'K'.repeat(512)}_${index}`
  );
  boundaryRecords[recordKey] =
    new Date(Date.UTC(2026, 0, 1, 0, 0, index)).toISOString();
}
persistenceSandbox.saveProcessedThreeCountRecords_(boundaryRecords);
persistenceSandbox.saveProcessedThreeCountRecords_(boundaryRecords);
const manifest = JSON.parse(
  propertyStore.values.PROCESSED_RECORDS_MANIFEST_JSON
);
assert.ok(manifest.shards.length > 1);
manifest.shards.forEach((shardKey) => {
  assert.ok(Buffer.byteLength(propertyStore.values[shardKey], 'utf8') <= 8000);
  assert.ok(Buffer.byteLength(propertyStore.values[shardKey], 'utf8') < 9000);
});
assert.equal(
  Object.keys(persistenceSandbox.getProcessedThreeCountRecords_()).length,
  1000
);
assert.deepEqual(
  Object.keys(propertyStore.values)
    .filter((key) => key.startsWith('PROCESSED_RECORDS_V2_'))
    .sort(),
  [...manifest.shards].sort()
);
assert.ok(propertyStore.getMaximumTotalBytes() < 500000);

console.log('Apps Script Gmail intake tests passed.');
