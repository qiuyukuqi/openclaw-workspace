#!/bin/bash
# Memory LanceDB Health Check & Auto-Recovery
# 每小时检查一次，如果表丢失则自动从备份恢复

DB_PATH="$HOME/.openclaw/memory/lancedb-pro/memories.lance"
BACKUP_DIR="$HOME/.openclaw/memory/backups"
LOG_FILE="$HOME/.openclaw/logs/memory-healthcheck.log"
PLUGIN_DIR="$HOME/.openclaw/workspace/plugins/memory-lancedb-pro"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 检查数据库表是否存在
check_tables() {
    cd "$PLUGIN_DIR"
    node --import jiti/register -e "
import { connect } from '@lancedb/lancedb';

async function main() {
  const db = await connect('$DB_PATH');
  const tables = await db.tableNames();
  if (tables.length === 0) {
    console.log('EMPTY');
    process.exit(1);
  }
  const table = await db.openTable(tables[0]);
  const count = await table.countRows();
  console.log('OK:', count);
}

main().catch(e => { console.log('ERROR:', e.message); process.exit(1); });
" 2>&1
}

# 从备份恢复
restore_from_backup() {
    local latest_backup=$(ls -t "$BACKUP_DIR"/memory-backup-*.jsonl 2>/dev/null | head -1)
    
    if [ -z "$latest_backup" ]; then
        log "ERROR: No backup found!"
        return 1
    fi
    
    log "Restoring from: $latest_backup"
    
    # 删除损坏的数据库
    rm -rf "$DB_PATH"
    mkdir -p "$DB_PATH"
    
    # 读取备份并恢复
    cd "$PLUGIN_DIR"
    node --import jiti/register -e "
import { connect } from '@lancedb/lancedb';
import { readFileSync } from 'fs';

async function main() {
  const backupPath = '$latest_backup';
  const content = readFileSync(backupPath, 'utf-8');
  const lines = content.trim().split('\n');
  const memories = lines.map(line => JSON.parse(line));
  
  const db = await connect('$DB_PATH');
  const tableData = memories.map(m => ({
    id: m.id,
    text: m.text,
    scope: m.scope || 'agent:main',
    category: m.category || 'other',
    importance: m.importance || 0.7,
    createdAt: m.createdAt || new Date().toISOString(),
    lastAccessedAt: m.lastAccessedAt || new Date().toISOString(),
    accessCount: m.accessCount || 0,
    vector: new Array(1024).fill(0)
  }));
  
  await db.createTable('memories', tableData);
  console.log('Restored', tableData.length, 'memories');
}

main().catch(console.error);
" 2>&1 | while read line; do log "$line"; done
    
    log "Restore completed"
}

# 主逻辑
main() {
    log "Health check started"
    
    result=$(check_tables 2>&1) || true
    
    if echo "$result" | grep -q "EMPTY\|ERROR"; then
        log "Database issue detected: $result"
        log "Attempting auto-recovery..."
        restore_from_backup
        
        # 验证恢复结果
        result2=$(check_tables 2>&1)
        if echo "$result2" | grep -q "OK:"; then
            log "Auto-recovery SUCCESS: $result2"
            # 发送飞书通知
            curl -s -X POST "http://127.0.0.1:3434/message" \
                -H "Content-Type: application/json" \
                -d '{"action":"send","channel":"feishu","target":"user:ou_c5c98e2002a34a9b10f15fd0b6463d06","message":"🤖 记忆数据库已自动恢复：'"$result2"'"}' 2>/dev/null || true
        else
            log "Auto-recovery FAILED: $result2"
        fi
    else
        log "Database healthy: $result"
    fi
}

main
