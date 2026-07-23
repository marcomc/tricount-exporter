function runDailyThreeCountExporter() {
  return withThreeCountLock_('daily', runThreeCountExporter_);
}

function runThreeCountExporter() {
  return withThreeCountLock_('manual', runThreeCountExporter_);
}

function withThreeCountLock_(source, callback) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(THREE_COUNT_CONFIG.MAX_RUNTIME_MS)) {
    throw new Error('Could not acquire the ' + source + ' export lock.');
  }
  try {
    return callback();
  } finally {
    lock.releaseLock();
  }
}

function installThreeCountAutomationTrigger() {
  return withThreeCountLock_('trigger-install', function () {
    const existing = getThreeCountManagedTriggers_();
    const config = getThreeCountConfig_();
    const created = ScriptApp.newTrigger(THREE_COUNT_CONFIG.DAILY_HANDLER).timeBased()
      .everyHours(config.run_interval_hours).create();
    try {
      existing.forEach(function (trigger) { ScriptApp.deleteTrigger(trigger); });
    } catch (error) {
      ScriptApp.deleteTrigger(created);
      throw new Error('Could not replace the daily trigger: ' + error.message);
    }
    const status = getThreeCountTriggerStatus_();
    if (status.missingTriggerHandlers.length || status.duplicateTriggerHandlers.length) {
      throw new Error('Daily trigger reconciliation did not converge: ' + JSON.stringify(status));
    }
    return status;
  });
}

function removeThreeCountAutomationTrigger() {
  return withThreeCountLock_('trigger-remove', function () {
    getThreeCountManagedTriggers_().forEach(function (trigger) { ScriptApp.deleteTrigger(trigger); });
    return getThreeCountTriggerStatus_();
  });
}

function getThreeCountManagedTriggers_() {
  return ScriptApp.getProjectTriggers().filter(function (trigger) {
    return trigger.getHandlerFunction() === THREE_COUNT_CONFIG.DAILY_HANDLER;
  });
}

function getThreeCountTriggerStatus_() {
  const triggers = getThreeCountManagedTriggers_();
  const valid = triggers.filter(function (trigger) {
    return trigger.getTriggerSource() === ScriptApp.TriggerSource.CLOCK &&
      trigger.getEventType() === ScriptApp.EventType.CLOCK;
  });
  const count = valid.length;
  return {
    triggerCounts: { runDailyThreeCountExporter: count },
    missingTriggerHandlers: count === 0 ? [THREE_COUNT_CONFIG.DAILY_HANDLER] : [],
    duplicateTriggerHandlers: count > 1 ? [THREE_COUNT_CONFIG.DAILY_HANDLER] : []
  };
}
