import sqlite3
import datetime
import os
from typing import Dict, Any, Optional
from src.services.base_service import IDatabaseService

class DatabaseService(IDatabaseService):
    def __init__(self, db_path: str = "data/stats.db"):
        self.db_path = db_path
        self.connection = None
        
    def initialize(self) -> bool:
        try:
            self.connection = sqlite3.connect(
                self.db_path, 
                check_same_thread=False
            )
            self._create_tables()
            print(f"DatabaseService: Connected to {self.db_path}")
            return True
        except Exception as e:
            print(f"DatabaseService: Failed to initialize: {e}")
            return False

    def shutdown(self) -> None:
        if self.connection:
            self.connection.close()

    def _create_tables(self):
        cursor = self.connection.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                result TEXT, -- VICTORY, DEFEAT, ABANDONED
                duration_seconds REAL
            )
        """)
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL, -- BOSS_ENCOUNTER, DEATH, etc.
                payload TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
        """)
        
        self.connection.commit()

    def create_session(self) -> int:
        if not self.connection: return -1
        try:
            cursor = self.connection.cursor()
            now = datetime.datetime.now().isoformat()
            cursor.execute("INSERT INTO sessions (start_time, result) VALUES (?, ?)", (now, "RUNNING"))
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"DatabaseService: Error creating session: {e}")
            return -1

    def end_session(self, session_id: int, result: str) -> None:
        if not self.connection or session_id < 0: return
        try:
            cursor = self.connection.cursor()
            
            # Get start time to calculate duration
            cursor.execute("SELECT start_time FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row: return
            
            start_time = datetime.datetime.fromisoformat(row[0])
            now_dt = datetime.datetime.now()
            duration = (now_dt - start_time).total_seconds()
            
            cursor.execute("""
                UPDATE sessions 
                SET end_time = ?, result = ?, duration_seconds = ? 
                WHERE id = ?
            """, (now_dt.isoformat(), result, duration, session_id))
            self.connection.commit()
        except Exception as e:
            print(f"DatabaseService: Error ending session: {e}")

    def log_event(self, session_id: int, event_type: str, payload: str = None) -> None:
        if not self.connection or session_id < 0: return
        try:
            cursor = self.connection.cursor()
            now = datetime.datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO events (session_id, timestamp, type, payload) 
                VALUES (?, ?, ?, ?)
            """, (session_id, now, event_type, payload))
            self.connection.commit()
        except Exception as e:
            print(f"DatabaseService: Error logging event: {e}")

    def get_stats(self) -> Dict[str, Any]:
        if not self.connection: return {}
        try:
            cursor = self.connection.cursor()
            
            stats = {}
            
            # Total Runs
            cursor.execute("SELECT COUNT(*) FROM sessions WHERE result IN ('VICTORY', 'DEFEAT')")
            stats["total_runs"] = cursor.fetchone()[0]
            
            # Victories
            cursor.execute("SELECT COUNT(*) FROM sessions WHERE result = 'VICTORY'")
            stats["victories"] = cursor.fetchone()[0]
            
            # Win Rate
            if stats["total_runs"] > 0:
                stats["win_rate"] = f"{(stats['victories'] / stats['total_runs']) * 100:.1f}%"
            else:
                stats["win_rate"] = "0%"
                
            # Avg Duration (only for completed runs)
            cursor.execute("SELECT AVG(duration_seconds) FROM sessions WHERE result IN ('VICTORY', 'DEFEAT')")
            avg = cursor.fetchone()[0]
            if avg:
                mins = int(avg // 60)
                secs = int(avg % 60)
                stats["avg_duration"] = f"{mins}m {secs}s"
            else:
                stats["avg_duration"] = "0m 0s"
                
            return stats
            
        except Exception as e:
            print(f"DatabaseService: Error getting stats: {e}")
            return {}
