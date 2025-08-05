#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
資料庫管理模組 - 支援多種資料來源
"""

import os
import json
from typing import List, Dict, Any, Optional

# PostgreSQL 支援
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

class DatabaseManager:
    """資料庫管理器 - 支援從硬編碼到PostgreSQL的升級"""

    def __init__(self):
        self.db_mode = self._detect_db_mode()
        self.connection = None
        if self.db_mode == 'postgres':
            self._init_postgres()

    def _detect_db_mode(self) -> str:
        """自動偵測資料庫模式"""
        if os.environ.get('DATABASE_URL') and POSTGRES_AVAILABLE:
            return 'postgres'
        elif os.environ.get('CASES_DATA'):
            return 'env_vars'
        else:
            return 'hardcoded'

    def _init_postgres(self):
        """初始化PostgreSQL連接"""
        try:
            database_url = os.environ.get('DATABASE_URL')
            self.connection = psycopg2.connect(database_url)
            self._create_tables()
            print("✅ PostgreSQL 連接成功")
        except Exception as e:
            print(f"❌ PostgreSQL 連接失敗: {e}")
            self.db_mode = 'env_vars'  # 降級到環境變數模式

    def _create_tables(self):
        """建立PostgreSQL資料表"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cases (
                        case_id VARCHAR(50) PRIMARY KEY,
                        client VARCHAR(200) NOT NULL,
                        case_type VARCHAR(100) NOT NULL,
                        progress VARCHAR(100) NOT NULL,
                        lawyer VARCHAR(100),
                        court VARCHAR(100),
                        division VARCHAR(100),
                        created_date DATE,
                        updated_date DATE DEFAULT CURRENT_DATE
                    )
                """)
                self.connection.commit()
                print("✅ 資料表建立成功")
        except Exception as e:
            print(f"❌ 建立資料表失敗: {e}")

    def get_all_cases(self) -> List[Dict[str, Any]]:
        """取得所有案件 - 自動選擇資料來源"""
        if self.db_mode == 'postgres':
            return self._get_cases_postgres()
        elif self.db_mode == 'env_vars':
            return self._get_cases_env()
        else:
            return self._get_cases_hardcoded()

    def _get_cases_postgres(self) -> List[Dict[str, Any]]:
        """從PostgreSQL取得案件"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM cases ORDER BY updated_date DESC")
                rows = cursor.fetchall()
                cases = [dict(row) for row in rows]
                print(f"✅ 從PostgreSQL載入 {len(cases)} 筆案件")
                return cases
        except Exception as e:
            print(f"❌ PostgreSQL查詢失敗: {e}")
            return []

    def _get_cases_env(self) -> List[Dict[str, Any]]:
        """從環境變數取得案件"""
        try:
            cases_json = os.environ.get('CASES_DATA', '[]')
            cases = json.loads(cases_json)
            print(f"✅ 從環境變數載入 {len(cases)} 筆案件")
            return cases
        except json.JSONDecodeError as e:
            print(f"❌ 環境變數解析失敗: {e}")
            return self._get_cases_hardcoded()

    def _get_cases_hardcoded(self) -> List[Dict[str, Any]]:
        """硬編碼案件資料（開發/測試用）"""
        cases = [
            {
                "case_id": "113001",
                "client": "張三",
                "case_type": "民事糾紛",
                "progress": "起訴階段",
                "lawyer": "李律師",
                "court": "台北地方法院",
                "division": "民事股",
                "created_date": "2024-01-15",
                "updated_date": "2024-08-06"
            },
            {
                "case_id": "113002",
                "client": "李四",
                "case_type": "刑事案件",
                "progress": "偵查階段",
                "lawyer": "王律師",
                "court": "新北地方法院",
                "division": "刑事股",
                "created_date": "2024-02-01",
                "updated_date": "2024-08-05"
            }
        ]
        print(f"✅ 使用硬編碼資料 {len(cases)} 筆案件")
        return cases

    def save_case(self, case_data: Dict[str, Any]) -> bool:
        """儲存案件 - 只有PostgreSQL模式支援"""
        if self.db_mode == 'postgres' and self.connection:
            return self._save_case_postgres(case_data)
        else:
            print(f"⚠️ {self.db_mode} 模式不支援儲存案件")
            return False

    def _save_case_postgres(self, case_data: Dict[str, Any]) -> bool:
        """儲存案件到PostgreSQL"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO cases (case_id, client, case_type, progress, lawyer, court, division, created_date)
                    VALUES (%(case_id)s, %(client)s, %(case_type)s, %(progress)s, %(lawyer)s, %(court)s, %(division)s, %(created_date)s)
                    ON CONFLICT (case_id) DO UPDATE SET
                        client = EXCLUDED.client,
                        case_type = EXCLUDED.case_type,
                        progress = EXCLUDED.progress,
                        lawyer = EXCLUDED.lawyer,
                        court = EXCLUDED.court,
                        division = EXCLUDED.division,
                        updated_date = CURRENT_DATE
                """, case_data)
                self.connection.commit()
                return True
        except Exception as e:
            print(f"❌ PostgreSQL儲存失敗: {e}")
            return False

    def get_db_info(self) -> Dict[str, Any]:
        """取得資料庫資訊"""
        return {
            "mode": self.db_mode,
            "postgres_available": POSTGRES_AVAILABLE,
            "database_url_set": bool(os.environ.get('DATABASE_URL')),
            "cases_data_set": bool(os.environ.get('CASES_DATA')),
            "connection_status": "connected" if self.connection else "disconnected"
        }

# 全域資料庫實例
db_manager = None

def get_database():
    """取得資料庫管理器實例"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager