function resolveThreeCountExportFolder_(title, key) {
  const root = getThreeCountRootFolder_();
  const baseName = sanitizeThreeCountPathComponent_(title);
  const shortKey = shortThreeCountKey_(key);
  let candidateName = baseName;
  let suffix = 1;
  while (suffix <= 100) {
    const candidates = findThreeCountFoldersByName_(root, candidateName);
    const matching = candidates.find(function (folder) {
      return folderMatchesThreeCountKey_(folder, key);
    });
    if (matching) {
      return matching;
    }
    if (!candidates.length) {
      return root.createFolder(candidateName);
    }
    suffix += 1;
    candidateName = baseName + '-' + shortKey + (suffix === 2 ? '' : '-' + suffix);
  }
  throw new Error('Could not allocate a unique export folder.');
}

function findThreeCountFoldersByName_(root, name) {
  const folders = root.getFoldersByName(name);
  const result = [];
  while (folders.hasNext()) {
    result.push(folders.next());
  }
  return result;
}

function folderMatchesThreeCountKey_(folder, key) {
  const file = findThreeCountFileByName_(folder, 'tricount-info.json');
  if (!file) {
    return false;
  }
  try {
    return JSON.parse(file.getBlob().getDataAsString('UTF-8')).tricount_key === key;
  } catch (error) {
    return false;
  }
}

function writeThreeCountJsonFile_(folder, name, data) {
  const content = JSON.stringify(data, null, 2);
  const existing = findThreeCountFileByName_(folder, name);
  if (existing) {
    existing.setContent(content);
    return existing;
  }
  return folder.createFile(name, content, 'application/json');
}

function findThreeCountFileByName_(folder, name) {
  const files = folder.getFilesByName(name);
  return files.hasNext() ? files.next() : null;
}

function downloadThreeCountAttachments_(registry, exportFolder) {
  const downloads = collectThreeCountAttachmentDownloads_(registry);
  const result = { downloaded: 0, failures: [] };
  if (!downloads.length) {
    return result;
  }
  const maxAttachments = getThreeCountConfig_().max_attachments_per_run;
  const attachmentFolder = getOrCreateThreeCountChildFolder_(
    exportFolder,
    'Attachments ' + sanitizeThreeCountPathComponent_(String(registry.title || 'tricount'))
  );
  clearThreeCountFolder_(attachmentFolder);
  downloads.slice(0, maxAttachments).forEach(function (download) {
    try {
      const response = UrlFetchApp.fetch(download.url, { muteHttpExceptions: true });
      if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
        throw new Error('HTTP ' + response.getResponseCode());
      }
      attachmentFolder.createFile(response.getBlob().setName(download.name));
      result.downloaded += 1;
    } catch (error) {
      result.failures.push({ name: download.name, error: String(error.message || error) });
    }
  });
  if (downloads.length > maxAttachments) {
    result.failures.push({
      name: '', error: 'Attachment limit reached: ' + maxAttachments + ' of ' + downloads.length
    });
  }
  return result;
}

function collectThreeCountAttachmentDownloads_(registry) {
  const entries = Array.isArray(registry.all_registry_entry) ? registry.all_registry_entry : [];
  const downloads = [];
  let index = 1;
  entries.forEach(function (entry) {
    const transaction = entry && entry.RegistryEntry;
    const attachments = transaction && Array.isArray(transaction.attachment) ? transaction.attachment : [];
    attachments.forEach(function (attachment) {
      const url = attachment && attachment.urls && attachment.urls[0] && attachment.urls[0].url;
      if (!url || typeof url !== 'string' || !url.startsWith('https://')) {
        return;
      }
      downloads.push({ name: 'receipt_' + index + getThreeCountUrlExtension_(url), url: url });
      index += 1;
    });
  });
  return downloads;
}

function getOrCreateThreeCountChildFolder_(parent, name) {
  const folders = parent.getFoldersByName(name);
  return folders.hasNext() ? folders.next() : parent.createFolder(name);
}

function clearThreeCountFolder_(folder) {
  const files = folder.getFiles();
  while (files.hasNext()) {
    files.next().setTrashed(true);
  }
}

function sanitizeThreeCountPathComponent_(value) {
  const sanitized = String(value || '').trim().replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
  return sanitized || 'tricount';
}

function sanitizeThreeCountFileComponent_(value) {
  const sanitized = String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return sanitized || 'tricount';
}

function shortThreeCountKey_(key) {
  return sanitizeThreeCountPathComponent_(key).slice(-6) || 'shared';
}

function getThreeCountUrlExtension_(url) {
  const base = String(url || '').split('?')[0];
  const match = base.match(/(\.[A-Za-z0-9]{1,10})$/);
  return match ? match[1].toLowerCase() : '.file';
}
