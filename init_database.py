#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
資料庫初始化腳本
在 Render 部署後執行，將匯出的案件資料初始化到 PostgreSQL 資料庫
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, date

# PostgreSQL 支援
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    print("❌ 請先安裝 psycopg2: pip install psycopg2-binary")

class DatabaseInitializer:
    """資料庫初始化器"""

    def __init__(self):
        self.connection = None
        self.database_url = os.environ.get('DATABASE_URL')

        if not self.database_url:
            print("❌ 未設定 DATABASE_URL 環境變數")
            sys.exit(1)

        if not POSTGRES_AVAILABLE:
            print("❌ PostgreSQL 套件不可用")
            sys.exit(1)

        self._connect_database()

    def _connect_database(self):
        """連接資料庫"""
        try:
            self.connection = psycopg2.connect(self.database_url)
            print("✅ PostgreSQL 資料庫連接成功")
        except Exception as e:
            print(f"❌ 資料庫連接失敗: {e}")
            sys.exit(1)

    def create_tables(self):
        """建立所有必要的資料表"""
        try:
            with self.connection.cursor() as cursor:
                # 建立案件主資料表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cases (
                        case_id VARCHAR(50) PRIMARY KEY,
                        client VARCHAR(200) NOT NULL,
                        case_type VARCHAR(100) NOT NULL,
                        progress VARCHAR(100) NOT NULL,
                        lawyer VARCHAR(100),
                        legal_affairs VARCHAR(100),
                        case_reason VARCHAR(500),
                        case_number VARCHAR(100),
                        opposing_party VARCHAR(200),
                        court VARCHAR(100),
                        division VARCHAR(100),
                        progress_date DATE,
                        progress_stages JSONB,
                        progress_notes JSONB,
                        progress_times JSONB,
                        created_date DATE,
                        updated_date DATE DEFAULT CURRENT_DATE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 建立索引以提高查詢效能
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cases_client ON cases(client);
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cases_case_type ON cases(case_type);
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cases_progress ON cases(progress);
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cases_lawyer ON cases(lawyer);
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cases_court ON cases(court);
                """)

                # 建立更新時間自動觸發器
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION update_updated_at_column()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = CURRENT_TIMESTAMP;
                        RETURN NEW;
                    END;
                    $$ language 'plpgsql';
                """)

                cursor.execute("""
                    DROP TRIGGER IF EXISTS update_cases_updated_at ON cases;
                """)

                cursor.execute("""
                    CREATE TRIGGER update_cases_updated_at
                        BEFORE UPDATE ON cases
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                """)

                self.connection.commit()
                print("✅ 資料表建立成功")

        except Exception as e:
            print(f"❌ 建立資料表失敗: {e}")
            self.connection.rollback()
            raise

    def load_cases_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """從檔案載入案件資料"""
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                print(f"❌ 檔案不存在: {file_path}")
                return []

            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix == '.json':
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    else:
                        return [data]
                else:
                    print(f"❌ 不支援的檔案格式: {file_path.suffix}")
                    return []

        except Exception as e:
            print(f"❌ 載入檔案失敗: {e}")
            return []

    def load_cases_from_env(self) -> List[Dict[str, Any]]:
        """從環境變數載入案件資料"""
        try:
            cases_data = os.environ.get('CASES_DATA')
            if not cases_data:
                print("❌ 未設定 CASES_DATA 環境變數")
                return []

            data = json.loads(cases_data)
            if isinstance(data, list):
                return data
            else:
                return [data]

        except json.JSONDecodeError as e:
            print(f"❌ 解析環境變數 CASES_DATA 失敗: {e}")
            return []
        except Exception as e:
            print(f"❌ 從環境變數載入失敗: {e}")
            return []

    def _process_case_data(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """處理案件資料，確保格式正確"""
        processed = {}

        # 必填欄位
        processed['case_id'] = str(case_data.get('case_id', ''))
        processed['client'] = str(case_data.get('client', ''))
        processed['case_type'] = str(case_data.get('case_type', ''))
        processed['progress'] = str(case_data.get('progress', ''))

        # 可選欄位
        processed['lawyer'] = case_data.get('lawyer')
        processed['legal_affairs'] = case_data.get('legal_affairs')
        processed['case_reason'] = case_data.get('case_reason')
        processed['case_number'] = case_data.get('case_number')
        processed['opposing_party'] = case_data.get('opposing_party')
        processed['court'] = case_data.get('court')
        processed['division'] = case_data.get('division')

        # 日期欄位處理
        for date_field in ['progress_date', 'created_date', 'updated_date']:
            date_value = case_data.get(date_field)
            if date_value:
                if isinstance(date_value, str):
                    try:
                        # 嘗試解析各種日期格式
                        if len(date_value) == 10:  # YYYY-MM-DD
                            processed[date_field] = datetime.strptime(date_value, '%Y-%m-%d').date()
                        elif len(date_value) == 19:  # YYYY-MM-DD HH:MM:SS
                            processed[date_field] = datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S').date()
                        else:
                            processed[date_field] = None
                    except ValueError:
                        processed[date_field] = None
                elif isinstance(date_value, (date, datetime)):
                    processed[date_field] = date_value
                else:
                    processed[date_field] = None
            else:
                processed[date_field] = None

        # JSON 欄位處理
        for json_field in ['progress_stages', 'progress_notes', 'progress_times']:
            json_value = case_data.get(json_field)
            if json_value:
                if isinstance(json_value, dict):
                    processed[json_field] = Json(json_value)
                elif isinstance(json_value, str):
                    try:
                        processed[json_field] = Json(json.loads(json_value))
                    except json.JSONDecodeError:
                        processed[json_field] = Json({})
                else:
                    processed[json_field] = Json({})
            else:
                processed[json_field] = Json({})

        return processed

    def insert_cases(self, cases_data: List[Dict[str, Any]], mode: str = 'replace') -> int:
        """
        插入案件資料到資料庫

        Args:
            cases_data: 案件資料列表
            mode: 插入模式 ('replace', 'skip', 'update')
                - replace: 如果存在則替換
                - skip: 如果存在則跳過
                - update: 如果存在則更新

        Returns:
            成功插入的案件數量
        """
        success_count = 0
        error_count = 0

        try:
            with self.connection.cursor() as cursor:
                for i, case_data in enumerate(cases_data, 1):
                    try:
                        # 處理案件資料
                        processed_case = self._process_case_data(case_data)

                        # 檢查必填欄位
                        if not all([processed_case['case_id'], processed_case['client'],
                                  processed_case['case_type'], processed_case['progress']]):
                            print(f"⚠️ 跳過案件 {i}：缺少必填欄位")
                            error_count += 1
                            continue

                        if mode == 'replace':
                            # 使用 UPSERT (INSERT ... ON CONFLICT DO UPDATE)
                            cursor.execute("""
                                INSERT INTO cases (
                                    case_id, client, case_type, progress, lawyer, legal_affairs,
                                    case_reason, case_number, opposing_party, court, division,
                                    progress_date, progress_stages, progress_notes, progress_times,
                                    created_date, updated_date
                                ) VALUES (
                                    %(case_id)s, %(client)s, %(case_type)s, %(progress)s, %(lawyer)s, %(legal_affairs)s,
                                    %(case_reason)s, %(case_number)s, %(opposing_party)s, %(court)s, %(division)s,
                                    %(progress_date)s, %(progress_stages)s, %(progress_notes)s, %(progress_times)s,
                                    %(created_date)s, %(updated_date)s
                                )
                                ON CONFLICT (case_id) DO UPDATE SET
                                    client = EXCLUDED.client,
                                    case_type = EXCLUDED.case_type,
                                    progress = EXCLUDED.progress,
                                    lawyer = EXCLUDED.lawyer,
                                    legal_affairs = EXCLUDED.legal_affairs,
                                    case_reason = EXCLUDED.case_reason,
                                    case_number = EXCLUDED.case_number,
                                    opposing_party = EXCLUDED.opposing_party,
                                    court = EXCLUDED.court,
                                    division = EXCLUDED.division,
                                    progress_date = EXCLUDED.progress_date,
                                    progress_stages = EXCLUDED.progress_stages,
                                    progress_notes = EXCLUDED.progress_notes,
                                    progress_times = EXCLUDED.progress_times,
                                    updated_date = CURRENT_DATE
                            """, processed_case)

                        elif mode == 'skip':
                            # 只插入新案件，跳過已存在的
                            cursor.execute("""
                                INSERT INTO cases (
                                    case_id, client, case_type, progress, lawyer, legal_affairs,
                                    case_reason, case_number, opposing_party, court, division,
                                    progress_date, progress_stages, progress_notes, progress_times,
                                    created_date, updated_date
                                ) VALUES (
                                    %(case_id)s, %(client)s, %(case_type)s, %(progress)s, %(lawyer)s, %(legal_affairs)s,
                                    %(case_reason)s, %(case_number)s, %(opposing_party)s, %(court)s, %(division)s,
                                    %(progress_date)s, %(progress_stages)s, %(progress_notes)s, %(progress_times)s,
                                    %(created_date)s, %(updated_date)s
                                )
                                ON CONFLICT (case_id) DO NOTHING
                            """, processed_case)

                        success_count += 1
                        if i % 10 == 0:  # 每10筆顯示一次進度
                            print(f"⏳ 已處理 {i}/{len(cases_data)} 筆案件...")

                    except Exception as case_error:
                        print(f"❌ 插入案件 {case_data.get('case_id', 'unknown')} 失敗: {case_error}")
                        error_count += 1
                        continue

                # 提交所有變更
                self.connection.commit()
                print(f"✅ 資料插入完成: 成功 {success_count} 筆，錯誤 {error_count} 筆")

        except Exception as e:
            print(f"❌ 批次插入失敗: {e}")
            self.connection.rollback()
            raise

        return success_count

    def verify_data(self) -> Dict[str, Any]:
        """驗證資料完整性"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # 基本統計
                cursor.execute("SELECT COUNT(*) as total_cases FROM cases")
                total_cases = cursor.fetchone()['total_cases']

                # 按類型統計
                cursor.execute("""
                    SELECT case_type, COUNT(*) as count
                    FROM cases
                    GROUP BY case_type
                    ORDER BY count DESC
                """)
                case_types = cursor.fetchall()

                # 按進度統計
                cursor.execute("""
                    SELECT progress, COUNT(*) as count
                    FROM cases
                    GROUP BY progress
                    ORDER BY count DESC
                """)
                progress_stats = cursor.fetchall()

                # 按律師統計
                cursor.execute("""
                    SELECT lawyer, COUNT(*) as count
                    FROM cases
                    WHERE lawyer IS NOT NULL
                    GROUP BY lawyer
                    ORDER BY count DESC
                """)
                lawyer_stats = cursor.fetchall()

                # 最近更新的案件
                cursor.execute("""
                    SELECT case_id, client, progress, updated_date
                    FROM cases
                    ORDER BY updated_date DESC
                    LIMIT 5
                """)
                recent_cases = cursor.fetchall()

                verification_result = {
                    "total_cases": total_cases,
                    "case_types": [dict(row) for row in case_types],
                    "progress_stats": [dict(row) for row in progress_stats],
                    "lawyer_stats": [dict(row) for row in lawyer_stats],
                    "recent_cases": [dict(row) for row in recent_cases]
                }

                return verification_result

        except Exception as e:
            print(f"❌ 資料驗證失敗: {e}")
            return {}

    def close(self):
        """關閉資料庫連接"""
        if self.connection:
            self.connection.close()
            print("✅ 資料庫連接已關閉")

def main():
    """主程式"""
    print("=" * 60)
    print("🗄️ PostgreSQL 資料庫初始化腳本")
    print("將案件資料初始化到 PostgreSQL 資料庫")
    print("=" * 60)

    # 初始化資料庫
    db_init = DatabaseInitializer()

    try:
        # 建立資料表
        print("\n📋 建立資料表...")
        db_init.create_tables()

        # 載入案件資料
        print("\n📂 載入案件資料...")
        cases_data = []

        # 優先從檔案載入
        possible_files = [
            "exported_data/cases_complete.json",
            "cases_complete.json",
            "cases.json",
            "data/cases.json"
        ]

        for file_path in possible_files:
            if Path(file_path).exists():
                print(f"📁 從檔案載入: {file_path}")
                cases_data = db_init.load_cases_from_file(file_path)
                if cases_data:
                    break

        # 如果沒有檔案，從環境變數載入
        if not cases_data:
            print("📝 從環境變數載入...")
            cases_data = db_init.load_cases_from_env()

        if not cases_data:
            print("❌ 沒有找到任何案件資料")
            return

        print(f"✅ 載入了 {len(cases_data)} 筆案件資料")

        # 插入資料
        print("\n💾 插入資料到資料庫...")
        success_count = db_init.insert_cases(cases_data, mode='replace')

        if success_count > 0:
            # 驗證資料
            print("\n🔍 驗證資料完整性...")
            verification = db_init.verify_data()

            if verification:
                print("\n📊 資料庫統計:")
                print(f"總案件數: {verification['total_cases']}")

                print("\n案件類型分佈:")
                for case_type in verification['case_types']:
                    print(f"  • {case_type['case_type']}: {case_type['count']} 件")

                print("\n進度分佈:")
                for progress in verification['progress_stats']:
                    print(f"  • {progress['progress']}: {progress['count']} 件")

                if verification['lawyer_stats']:
                    print("\n律師案件分佈:")
                    for lawyer in verification['lawyer_stats'][:5]:  # 只顯示前5名
                        print(f"  • {lawyer['lawyer']}: {lawyer['count']} 件")

                print("\n最近更新的案件:")
                for case in verification['recent_cases']:
                    print(f"  • {case['case_id']} - {case['client']} ({case['progress']})")

            print("\n" + "=" * 60)
            print("✅ 資料庫初始化完成！")
            print("=" * 60)
            print(f"🎯 成功初始化 {success_count} 筆案件資料")
            print("🚀 您的 API 現在可以使用 PostgreSQL 資料庫了！")

        else:
            print("❌ 沒有成功插入任何資料")

    except Exception as e:
        print(f"❌ 初始化過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 關閉資料庫連接
        db_init.close()

if __name__ == "__main__":
    main()