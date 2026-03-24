// ===== 配置区 =====
// 把你的 Google Sheet ID 填进来（Sheet URL 里 /d/ 和 /edit 之间那串字符）
const SHEET_ID = '1Wh8Oev_SV7tPNAZCnsI7kUhl-hgoYMs8w_cAqaM1WHE';
const SHEET_NAME = 'Sheet1'; // Sheet 标签页名字，默认是 Sheet1

// ===== 主逻辑 =====

function doGet(e) {
  const path = e.pathInfo || '';
  const params = e.parameter || {};

  try {
    if (path.startsWith('toggle/')) {
      const app = decodeURIComponent(path.slice(7));
      const result = toggle(app);
      return jsonResponse(result);
    }

    if (path === 'status') {
      const result = getStatus();
      return jsonResponse(result);
    }

    if (path === 'clear') {
      clearOldData();
      return jsonResponse({ message: 'cleared' });
    }

    return jsonResponse({ error: 'unknown path', path });

  } catch (err) {
    return jsonResponse({ error: err.message });
  }
}

function toggle(app) {
  const sheet = getSheet();
  const now = new Date();
  const rows = sheet.getDataRange().getValues();

  // 找这个 app 最后一条记录
  let lastRow = null;
  let lastRowIndex = -1;
  for (let i = rows.length - 1; i >= 1; i--) {
    if (rows[i][0] === app) {
      lastRow = rows[i];
      lastRowIndex = i + 1; // 1-based
      break;
    }
  }

  let action;
  if (!lastRow || lastRow[2] === 'close') {
    // 上次是 close 或没有记录 → 现在 open
    action = 'open';
    sheet.appendRow([app, now, action, '', '']);
  } else {
    // 上次是 open → 现在 close，计算时长
    const openTime = new Date(lastRow[1]);
    const durationSec = Math.round((now - openTime) / 1000);
    const durationMin = Math.round(durationSec / 60);

    // 更新那行的 close 信息
    const rowRange = sheet.getRange(lastRowIndex, 3, 1, 3);
    rowRange.setValues([['close', now, durationSec]]);

    action = `close|${durationMin}m`;
  }

  // 顺便清理 24 小时前的数据
  cleanOldRows(sheet);

  return { app, action };
}

function getStatus() {
  const sheet = getSheet();
  const rows = sheet.getDataRange().getValues();
  const now = new Date();
  const cutoff = new Date(now - 24 * 60 * 60 * 1000);

  // 统计每个 app
  const appMap = {};

  for (let i = 1; i < rows.length; i++) {
    const [app, openTime, action, closeTime, durationSec] = rows[i];
    if (!app || new Date(openTime) < cutoff) continue;

    if (!appMap[app]) appMap[app] = { sessions: 0, totalSec: 0, isOpen: false, openSince: null };

    if (action === 'open') {
      appMap[app].isOpen = true;
      appMap[app].openSince = openTime;
      appMap[app].sessions += 1;
    } else if (action === 'close') {
      appMap[app].isOpen = false;
      appMap[app].totalSec += Number(durationSec) || 0;
    }
  }

  const currentlyOpen = [];
  const today = [];

  for (const [app, data] of Object.entries(appMap)) {
    if (data.isOpen) {
      currentlyOpen.push(app);
      // 加上已经用了多久
      const soFarSec = Math.round((now - new Date(data.openSince)) / 1000);
      data.totalSec += soFarSec;
    }
    today.push({
      app,
      sessions: data.sessions,
      totalMinutes: Math.round(data.totalSec / 60),
    });
  }

  today.sort((a, b) => b.totalMinutes - a.totalMinutes);

  return {
    currentlyOpen,
    today,
    asOf: now.toISOString(),
  };
}

function cleanOldRows(sheet) {
  const cutoff = new Date(new Date() - 24 * 60 * 60 * 1000);
  const rows = sheet.getDataRange().getValues();
  // 从后往前删，避免行号错位
  for (let i = rows.length - 1; i >= 1; i--) {
    if (rows[i][0] && new Date(rows[i][1]) < cutoff) {
      sheet.deleteRow(i + 1);
    }
  }
}

function clearOldData() {
  cleanOldRows(getSheet());
}

function getSheet() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  // 确保有表头
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['app', 'openTime', 'action', 'closeTime', 'durationSec']);
  }
  return sheet;
}

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
