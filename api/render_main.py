#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Render 部署專用啟動檔案
簡化版 API，專門處理 N8N 工作流請求
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json

# 設定專案路徑
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# 建立 FastAPI 應用程式
app = FastAPI(
    title="LINE BOT 案件管理 API - Render版",
    version="1.0.0",
    description="專為 N8N 工作流設計的簡化版 API"
)

# 添加 CORS 中介軟體（N8N 需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境建議限制來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全域變數
controller = None
user_conversations = {}

# 資料模型
class LineMessage(BaseModel):
    type: str
    text: str

class LineWebhookEvent(BaseModel):
    type: str
    message: Optional[LineMessage] = None
    replyToken: str
    source: Dict[str, Any]

class LineWebhookRequest(BaseModel):
    events: list[LineWebhookEvent]

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

def get_controller():
    """取得控制器實例"""
    global controller
    if controller is None:
        try:
            from controllers.case_controller import CaseController
            controller = CaseController()
            print("✅ 控制器初始化成功")
        except Exception as e:
            print(f"❌ 控制器初始化失敗: {e}")
            controller = None
    return controller

# 健康檢查端點
@app.get("/health")
async def health_check():
    """健康檢查"""
    return {"status": "healthy", "service": "LINE BOT API"}

# N8N 工作流主要端點
@app.post("/webhook/line")
async def handle_line_webhook(request: LineWebhookRequest):
    """處理 LINE Webhook 請求（N8N 第3步調用）"""
    try:
        # 檢查控制器
        ctrl = get_controller()
        if not ctrl:
            raise HTTPException(status_code=503, detail="系統服務不可用")

        # 處理事件
        for event in request.events:
            if event.type == "message" and event.message and event.message.type == "text":
                user_id = event.source.get("userId", "unknown")
                message_text = event.message.text

                # 這裡調用您的業務邏輯
                response_text = process_user_message(user_id, message_text, ctrl)

                return APIResponse(
                    success=True,
                    message="處理成功",
                    data={
                        "reply_text": response_text,
                        "reply_token": event.replyToken
                    }
                )

        return APIResponse(success=True, message="無需處理的事件")

    except Exception as e:
        print(f"❌ Webhook 處理錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def process_user_message(user_id: str, message: str, ctrl) -> str:
    """處理用戶訊息的核心邏輯"""
    try:
        # 導入您現有的邏輯
        from api.logic.webhook_logic import WebhookLogic

        # 初始化邏輯處理器
        webhook_logic = WebhookLogic(ctrl, user_conversations)

        # 處理訊息
        result = webhook_logic.process_message(user_id, message)

        return result.get("text", "處理完成")

    except Exception as e:
        print(f"❌ 訊息處理錯誤: {e}")
        return "抱歉，系統處理時發生錯誤，請稍後再試。"

# 案件查詢端點（如果 N8N 需要）
@app.get("/api/cases/{case_id}")
async def get_case_detail(case_id: str):
    """取得案件詳細資料"""
    try:
        ctrl = get_controller()
        if not ctrl:
            raise HTTPException(status_code=503, detail="系統服務不可用")

        # 使用您現有的邏輯
        cases = ctrl.get_cases()
        case = next((c for c in cases if c.case_id == case_id), None)

        if not case:
            raise HTTPException(status_code=404, detail="案件不存在")

        return APIResponse(
            success=True,
            message="查詢成功",
            data={
                "case_id": case.case_id,
                "client": case.client,
                "case_type": case.case_type,
                "progress": case.progress,
                "lawyer": getattr(case, 'lawyer', None),
                "created_date": case.created_date,
                "updated_date": case.updated_date
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 案件查詢錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Render 會設定 PORT 環境變數
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)