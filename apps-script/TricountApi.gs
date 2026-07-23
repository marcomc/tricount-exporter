function exportThreeCountShare_(share, message, attachmentBudget) {
  const rawData = fetchThreeCountRegistry_(share.key);
  const registry = getThreeCountRegistry_(rawData);
  const title = String(registry.title || '').trim();
  if (!title) {
    throw new Error('The Tricount registry has no title.');
  }
  const exportFolder = resolveThreeCountExportFolder_(title, share.key);
  const fileStem = sanitizeThreeCountFileComponent_(title);
  writeThreeCountJsonFile_(exportFolder, 'transactions-' + fileStem + '.json', rawData);
  const metadata = {
    title: title,
    tricount_key: share.key,
    source_url: share.sourceUrl,
    gmail_message_id: message.getId(),
    received_at: message.getDate().toISOString(),
    downloaded_at: new Date().toISOString(),
    attachment_result: { downloaded: 0, failures: [] }
  };
  writeThreeCountJsonFile_(exportFolder, 'tricount-info.json', metadata);

  let attachmentResult;
  try {
    attachmentResult = downloadThreeCountAttachments_(
      registry, exportFolder, attachmentBudget
    );
  } catch (error) {
    attachmentResult = {
      downloaded: 0,
      failures: [{ name: '', error: String(error.message || error) }]
    };
    console.warn('Tricount attachment download failed: ' + attachmentResult.failures[0].error);
  }
  metadata.attachment_result = attachmentResult;
  writeThreeCountJsonFile_(exportFolder, 'tricount-info.json', metadata);
  return {
    title: title,
    folderUrl: exportFolder.getUrl(),
    attachmentCount: attachmentResult.downloaded,
    attachmentFailures: attachmentResult.failures.length
  };
}

function fetchThreeCountRegistry_(key) {
  const appInstallationId = Utilities.getUuid();
  const headers = {
    'User-Agent': 'com.bunq.tricount.android:RELEASE:7.0.7:3174:ANDROID:13:C',
    'app-id': appInstallationId,
    'X-Bunq-Client-Request-Id': Utilities.getUuid()
  };
  const sessionResponse = fetchThreeCountJson_(
    THREE_COUNT_CONFIG.API_BASE_URL + '/v1/session-registry-installation',
    {
      method: 'post', contentType: 'application/json', headers: headers,
      payload: JSON.stringify({
        app_installation_uuid: appInstallationId,
        client_public_key: getThreeCountPublicKey_(),
        device_description: 'Tricount-Exporter Apps Script'
      })
    },
    'authenticate'
  );
  const responseItems = Array.isArray(sessionResponse.Response) ? sessionResponse.Response : [];
  const tokenItem = responseItems.find(function (item) { return item && item.Token && item.Token.token; });
  const userItem = responseItems.find(function (item) { return item && item.UserPerson && item.UserPerson.id; });
  if (!tokenItem || !userItem) {
    throw new Error('The Tricount session response did not contain a token and user ID.');
  }
  headers['X-Bunq-Client-Authentication'] = tokenItem.Token.token;
  return fetchThreeCountJson_(
    THREE_COUNT_CONFIG.API_BASE_URL + '/v1/user/' + encodeURIComponent(userItem.UserPerson.id) +
      '/registry?public_identifier_token=' + encodeURIComponent(key),
    { method: 'get', headers: headers },
    'fetch registry'
  );
}

function fetchThreeCountJson_(url, options, operation) {
  const response = UrlFetchApp.fetch(url, Object.assign({ muteHttpExceptions: true }, options));
  if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
    throw new Error('Tricount ' + operation + ' failed with HTTP ' + response.getResponseCode() + '.');
  }
  try {
    return JSON.parse(response.getContentText());
  } catch (error) {
    throw new Error('Tricount ' + operation + ' returned invalid JSON.');
  }
}

function getThreeCountRegistry_(rawData) {
  if (!rawData || !Array.isArray(rawData.Response) || !rawData.Response.length ||
    !rawData.Response[0].Registry) {
    throw new Error('The Tricount registry response has an unexpected shape.');
  }
  return rawData.Response[0].Registry;
}
