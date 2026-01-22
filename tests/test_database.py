import unittest
import os
import sqlite3
from src.services.database_service import DatabaseService

class TestDatabaseService(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_stats.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.db = DatabaseService(self.test_db)
        self.db.initialize()

    def tearDown(self):
        self.db.shutdown()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_create_session(self):
        session_id = self.db.create_session()
        self.assertGreater(session_id, 0)
        
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[3], "RUNNING") # Result is 4th column

    def test_log_event(self):
        sid = self.db.create_session()
        self.db.log_event(sid, "TEST_EVENT", "Payload")
        
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT * FROM events WHERE session_id = ?", (sid,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[3], "TEST_EVENT")

    def test_end_session(self):
        sid = self.db.create_session()
        self.db.end_session(sid, "VICTORY")
        
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT result, duration_seconds FROM sessions WHERE id = ?", (sid,))
        row = cursor.fetchone()
        self.assertEqual(row[0], "VICTORY")
        self.assertIsNotNone(row[1])

    def test_get_stats(self):
        sid1 = self.db.create_session()
        self.db.end_session(sid1, "VICTORY")
        
        sid2 = self.db.create_session()
        self.db.end_session(sid2, "DEFEAT")
        
        stats = self.db.get_stats()
        self.assertEqual(stats["total_runs"], 2)
        self.assertEqual(stats["victories"], 1)
        self.assertEqual(stats["win_rate"], "50.0%")

if __name__ == '__main__':
    unittest.main()
