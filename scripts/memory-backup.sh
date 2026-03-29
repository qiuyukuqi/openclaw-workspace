#!/bin/bash
# Memory LanceDB 强制备份（每6小时）
# 比内置的每日备份更频繁

set -e

BACKUP_DIR="$HOME/.openclaw/memory/backups"
PLUGIN_DIR="$HOME/.openclaw/workspace/plugins/memory-lancedb-pro"
LOG_FILE="$HOME/.openclaw/logs/memory-backup.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 导出当前记忆到 JSONL
backup() {
    local timestamp=$(date '+%Y-%m-%d_%H%M')
    local backup_file="$BACKUP_DIR/memory-snapshot-$timestamp.jsonl"
    
    cd "$PLUGIN_DIR"
    node --import jiti/register -e "
import { connect } from '@lancedb/lancedb';
import { writeFileSync } from 'fs';

async function main() {
  const db = await connect(process.env.HOME + '/.openclaw/memory/lancedb-pro/memories.lance');
  const tables = await db.tableNames();
  if (tables.length === 0) {
    console.log('No tables to backup');
    return;
  }
  const table = await db.openTable(tables[0]);
  const rows = await table.query().toArray();
  
  const lines = rows.map(r => JSON.stringify({
    id: r.id,
    text: r.text,
    scope: r.scope,
    category: r.category,
    importance: r.importance,
    createdAt: r.createdAt,
    lastAccessedAt: r.lastAccessedAt,
    accessCount: r.accessCount
  }));
  
  writeFileSync('$backup_file', lines.join('\n') + '\n');
  console.log('Backed up', lines.length, 'memories to', '$backup_file');
}

main().catch(console.error);
" 2>&1 | while read line; do log "$line"; done

    # 清理超过 7 天的快照备份（保留每日备份）
    find "$BACKUP_DIR" -name "memory-snapshot-*.jsonl" -mtime +7 -delete 2>/dev/null || true
}

backup
