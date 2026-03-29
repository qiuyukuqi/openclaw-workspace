#!/usr/bin/env node
/**
 * 倒班提醒脚本
 * 周期：4天一轮（夜班 -> 下夜班+休息 -> 休息 -> 白班）
 * 起始：2026年2月13日(周五)夜班
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// 配置路径
const CONFIG_PATH = '/root/.openclaw/openclaw.json';
const MEMORY_PATH = path.join(__dirname, '../data/sent_reminders.json');
const FEISHU_OPEN_ID = 'ou_c5c98e2002a34a9b10f15fd0b6463d06';

// 倒班算法：起始2026年2月13日(周五)夜班
const START_DATE = new Date(2026, 1, 13); // 2月13日

function getShiftDay(date) {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diff = Math.floor((d - START_DATE) / (24 * 60 * 60 * 1000));
  return (diff % 4 + 4) % 4 + 1; // 1-4
}

// 判断是否是周末（周五、周六、周日）
function isWeekend(date) {
  const day = date.getDay();
  return day === 0 || day === 5 || day === 6; // 日、五、六
}

// 获取班次信息
function getShiftInfo(date) {
  const shiftDay = getShiftDay(date);
  const dayNames = ['', '夜班', '下夜班+休息', '休息', '白班'];

  if (shiftDay === 1) {
    // 夜班
    const weekend = isWeekend(date);
    return {
      shiftDay,
      name: '夜班',
      workDay: true,
      startTime: weekend ? '19:50' : '19:20',
      endTime: '08:50', // 次日
      reminders: [
        { time: weekend ? '19:50' : '19:20', type: '上班', msg: '⏰ 夜班上班了，抓紧刷脸！' }
      ]
    };
  } else if (shiftDay === 2) {
    // 下夜班+休息
    return {
      shiftDay,
      name: '下夜班+休息',
      workDay: false,
      reminders: [
        { time: '08:50', type: '下班', msg: '🌅 下班了，抓紧刷脸！' }
      ]
    };
  } else if (shiftDay === 3) {
    // 休息
    return {
      shiftDay,
      name: '休息',
      workDay: false,
      reminders: []
    };
  } else if (shiftDay === 4) {
    // 白班
    return {
      shiftDay,
      name: '白班',
      workDay: true,
      startTime: '07:50',
      endTime: '20:50',
      reminders: [
        { time: '07:50', type: '上班', msg: '⏰ 白班上班了，抓紧刷脸！' },
        { time: '20:50', type: '下班', msg: '🌙 下班了，抓紧刷脸！' }
      ]
    };
  }

  return { shiftDay, name: '未知', workDay: false, reminders: [] };
}

// 获取飞书 Token
async function getFeishuToken() {
  const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  const feishu = config.channels.feishu.accounts.main;

  return new Promise((resolve) => {
    const data = JSON.stringify({
      app_id: feishu.appId,
      app_secret: feishu.appSecret
    });
    const req = https.request({
      hostname: 'open.feishu.cn',
      path: '/open-apis/auth/v3/tenant_access_token/internal',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }, (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        try {
          const json = JSON.parse(body);
          resolve(json.code === 0 ? json.tenant_access_token : null);
        } catch { resolve(null); }
      });
    });
    req.on('error', () => resolve(null));
    req.write(data);
    req.end();
  });
}

// 发送飞书消息
async function sendFeishuText(token, openId, text) {
  return new Promise((resolve) => {
    const data = JSON.stringify({
      receive_id: openId,
      msg_type: 'text',
      content: JSON.stringify({ text })
    });
    const req = https.request({
      hostname: 'open.feishu.cn',
      method: 'POST',
      path: '/open-apis/im/v1/messages?receive_id_type=open_id',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    }, (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        try {
          resolve(JSON.parse(body));
        } catch { resolve({ code: -1 }); }
      });
    });
    req.on('error', () => resolve({ code: -1 }));
    req.write(data);
    req.end();
  });
}

// 获取/保存已发送记录
function getSentReminders() {
  try {
    return JSON.parse(fs.readFileSync(MEMORY_PATH, 'utf8'));
  } catch { return {}; }
}

function saveSentReminder(key) {
  fs.mkdirSync(path.dirname(MEMORY_PATH), { recursive: true });
  const sent = getSentReminders();
  sent[key] = Date.now();
  fs.writeFileSync(MEMORY_PATH, JSON.stringify(sent, null, 2));
}

// 格式化日期
function formatDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

// 获取当前北京时间 (UTC+8)
function getBeijingTime() {
  return new Date();
}

// 主函数
async function main() {
  const now = getBeijingTime();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const currentTime = `${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}`;

  console.log(`[${formatDate(now)} ${currentTime}] 检查倒班提醒...`);

  // 获取今天的班次信息
  const todayShift = getShiftInfo(now);
  console.log(`今天: 第${todayShift.shiftDay}天 - ${todayShift.name}`);

  // 检查是否需要发送提醒
  const dateStr = formatDate(now);
  const sent = getSentReminders();

  for (const reminder of todayShift.reminders) {
    // 检查时间是否匹配（±1分钟容差）
    const [rHour, rMin] = reminder.time.split(':').map(Number);
    const rTime = rHour * 60 + rMin;
    const nTime = hour * 60 + minute;

    if (Math.abs(nTime - rTime) <= 1) {
      const key = `${dateStr}-${reminder.time}-${reminder.type}`;

      // 检查是否已发送（10分钟内不重复）
      if (sent[key] && (Date.now() - sent[key]) < 10 * 60 * 1000) {
        console.log(`已发送过: ${reminder.type} ${reminder.time}`);
        continue;
      }

      console.log(`发送提醒: ${reminder.msg}`);

      const token = await getFeishuToken();
      if (!token) {
        console.log('无法获取 Token');
        continue;
      }

      const result = await sendFeishuText(token, FEISHU_OPEN_ID, reminder.msg);

      if (result.code === 0) {
        saveSentReminder(key);
        console.log(`✅ 已发送: ${key}`);
      } else {
        console.log(`✗ 发送失败:`, result.msg);
      }
    }
  }
}

// 命令行参数
const args = process.argv.slice(2);
if (args[0] === 'test') {
  // 测试模式：显示今天和未来7天的班次
  console.log('=== 倒班日历 ===\n');
  for (let i = 0; i < 8; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    const info = getShiftInfo(d);
    const dateStr = formatDate(d);
    const dayName = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()];
    let line = `${dateStr} 周${dayName} - 第${info.shiftDay}天 ${info.name}`;
    if (info.reminders.length > 0) {
      line += ` [${info.reminders.map(r => r.time).join(', ')}]`;
    }
    console.log(line);
  }
} else if (args[0] === 'status') {
  // 显示今天的班次详情
  const now = new Date();
  const info = getShiftInfo(now);
  console.log(`\n📅 今天: ${formatDate(now)}`);
  console.log(`班次: 第${info.shiftDay}天 - ${info.name}`);
  console.log(`是否上班: ${info.workDay ? '是' : '否'}`);
  if (info.reminders.length > 0) {
    console.log(`提醒:`);
    for (const r of info.reminders) {
      console.log(`  ${r.time} ${r.type}: ${r.msg}`);
    }
  }
} else {
  main().catch(e => console.error('错误:', e.message));
}
