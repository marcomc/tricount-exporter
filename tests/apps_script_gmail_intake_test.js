#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const gmailIntake = fs.readFileSync(
  path.resolve(__dirname, '..', 'apps-script', 'GmailIntake.gs'),
  'utf8'
);

function createMessage(body = 'Join: https://tricount.com/EXAMPLE_SHARE_KEY') {
  return {
    getDate: () => new Date(),
    getSubject: () => "Hey, I've added you to my tricount",
    getPlainBody: () => body,
    getId: () => 'EXAMPLE_MESSAGE_ID',
    isUnread: () => false,
    markUnread: () => {},
  };
}

function createScenario({ processed = {}, exportError = null, failingKey = '', body } = {}) {
  const message = createMessage(body);
  const effects = { archived: 0, labels: 0, logs: [], notifications: 0, saved: null };
  const thread = {
    addLabel: () => { effects.labels += 1; },
    getId: () => 'EXAMPLE_THREAD_ID',
    getMessages: () => [message],
    moveToArchive: () => { effects.archived += 1; },
  };
  const sandbox = vm.createContext({
    console: { log: () => {} },
    GmailApp: { search: () => [thread] },
  });
  vm.runInContext(gmailIntake, sandbox);
  Object.assign(sandbox, {
    assertThreeCountConfiguration_: () => {},
    getThreeCountConfig_: () => ({
      lookback_days: 30,
      gmail_query: 'in:inbox subject:tricount',
      max_messages_per_run: 100,
      archive_processed_threads: true,
    }),
    getProcessedThreeCountRecords_: () => ({ ...processed }),
    getOrCreateThreeCountProcessedLabel_: () => 'processed-label',
    shortThreeCountKey_: (key) => String(key).slice(-6),
    exportThreeCountShare_: (share) => {
      if (exportError && (!failingKey || share.key === failingKey)) {
        throw exportError;
      }
      return { title: 'Example', folderUrl: 'https://drive.google.com/example', attachmentCount: 0, attachmentFailures: 0 };
    },
    sendThreeCountSuccessNotification_: () => {
      effects.notifications += 1;
      return 'sent';
    },
    appendThreeCountImportLog_: (entry) => { effects.logs.push(entry); },
    saveProcessedThreeCountRecords_: (records) => { effects.saved = { ...records }; },
  });
  return { effects, run: sandbox.runThreeCountExporter_ };
}

const successful = createScenario({});
const successfulSummary = successful.run();
assert.equal(successfulSummary.exported.length, 1);
assert.equal(successful.effects.labels, 1);
assert.equal(successful.effects.archived, 1);
assert.equal(successful.effects.notifications, 1);
assert.equal(successful.effects.logs.length, 1);
assert.equal(successful.effects.logs[0].status, 'success');
assert.ok(successful.effects.saved['EXAMPLE_MESSAGE_ID:EXAMPLE_SHARE_KEY']);

const idempotent = createScenario({
  processed: { 'EXAMPLE_MESSAGE_ID:EXAMPLE_SHARE_KEY': '2026-07-23T00:00:00.000Z' },
  exportError: new Error('known exports must not be fetched again'),
});
const idempotentSummary = idempotent.run();
assert.equal(idempotentSummary.skipped.length, 1);
assert.equal(idempotent.effects.labels, 1);
assert.equal(idempotent.effects.archived, 1);
assert.equal(idempotent.effects.notifications, 0);

const failed = createScenario({ exportError: new Error('Tricount API failed') });
const failedSummary = failed.run();
assert.equal(failedSummary.errors.length, 1);
assert.equal(failed.effects.labels, 0);
assert.equal(failed.effects.archived, 0);
assert.equal(failed.effects.notifications, 0);
assert.equal(failed.effects.logs.length, 1);
assert.equal(failed.effects.logs[0].status, 'failed');
assert.deepEqual(failed.effects.saved, {});

const partial = createScenario({
  body: 'Join: https://tricount.com/EXAMPLE_SHARE_KEY https://tricount.com/FAILING_SHARE_KEY',
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
assert.ok(partial.effects.saved['EXAMPLE_MESSAGE_ID:EXAMPLE_SHARE_KEY']);

console.log('Apps Script Gmail intake tests passed.');
