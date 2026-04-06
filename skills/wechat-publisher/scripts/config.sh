#!/bin/bash
# 微信公众号自动发布系统 - 配置文件
source ~/.openclaw/workspace/.env.wechat

TAVILY_API_KEY="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"
ZHIPU_API_KEY="579714647a6c40d7bb95632559736fb2.VqYfT1pnRPS34CQu"

WORK_DIR="/tmp/openclaw/wechat-publisher"
DATA_DIR="$WORK_DIR/data"

mkdir -p "$DATA_DIR"
