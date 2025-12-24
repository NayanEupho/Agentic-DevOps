import sqlite3
import json
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
from ..settings import settings

# Database file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, settings.DATABASE_NAME)

class SessionRepository:
    """
    Handles all database interactions for Sessions and Messages.
    Uses SQLite but keeps SQL isolated to allow future migration.
    """
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        """Get a connection to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn

    def _init_db(self):
        """Initialize the database schema if it doesn't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Sessions Table
        # context_state: JSON string for storing active state (e.g. last pod, etc.)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT,
                last_activity TEXT,
                context_state TEXT
            )
        ''')

        # Messages Table
        # Stores every interaction (User query, Agent response, System output)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        ''')
        
        # Thoughts Table (Separate from messages for clean LLM context)
        # Stores the "thinking process" for each assistant message
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS thoughts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                type TEXT,
                content TEXT,
                sequence INTEGER,
                FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        
        # Performance Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_thoughts_message_id ON thoughts(message_id)')
        
        conn.commit()
        conn.close()

    def create_session(self, session_id: str, title: str) -> Dict[str, Any]:
        """Create a new session."""
        created_at = datetime.now().isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO sessions (id, title, created_at, last_activity, context_state) VALUES (?, ?, ?, ?, ?)",
            (session_id, title, created_at, created_at, "{}")
        )
        
        conn.commit()
        conn.close()
        
        return {
            "id": session_id,
            "title": title,
            "created_at": created_at,
            "messages": [],
            "last_activity": created_at,
            "context_state": {}
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session and its messages by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session_row = cursor.fetchone()
        
        if not session_row:
            conn.close()
            return None
            
        # Get messages for this session
        cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
        message_rows = cursor.fetchall()
        
        # Get all thoughts for this session's messages in one query (efficient)
        message_ids = [row["id"] for row in message_rows]
        thoughts_map = {}
        if message_ids:
            placeholders = ",".join("?" * len(message_ids))
            cursor.execute(
                f"SELECT * FROM thoughts WHERE message_id IN ({placeholders}) ORDER BY message_id, sequence",
                message_ids
            )
            for t_row in cursor.fetchall():
                mid = t_row["message_id"]
                if mid not in thoughts_map:
                    thoughts_map[mid] = []
                thoughts_map[mid].append({
                    "type": t_row["type"],
                    "content": t_row["content"]
                })
        
        conn.close()
        
        messages = []
        for row in message_rows:
            msg = {
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"]
            }
            # Attach thoughts if available (only for assistant messages)
            if row["id"] in thoughts_map:
                msg["thoughts"] = thoughts_map[row["id"]]
            messages.append(msg)
            
        return {
            "id": session_row["id"],
            "title": session_row["title"],
            "created_at": session_row["created_at"],
            "messages": messages,
            "last_activity": session_row["last_activity"],
            "context_state": json.loads(session_row["context_state"] or "{}")
        }

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions ordered by last activity."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Single query with message count (fixes N+1)
        cursor.execute("""
            SELECT s.*, COUNT(m.id) as msg_count 
            FROM sessions s 
            LEFT JOIN messages m ON s.id = m.session_id 
            GROUP BY s.id 
            ORDER BY s.last_activity DESC
        """)
        rows = cursor.fetchall()
        
        sessions = []
        for row in rows:
            sessions.append({
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "last_activity": row["last_activity"],
                "message_count": row["msg_count"]
            })
            
        conn.close()
        return sessions

    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to a session and update last_activity."""
        timestamp = datetime.now().isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        message_id = None
        
        try:
            cursor.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, timestamp)
            )
            message_id = cursor.lastrowid  # Get the inserted message ID
            
            # Update session last_activity
            cursor.execute(
                "UPDATE sessions SET last_activity = ? WHERE id = ?",
                (timestamp, session_id)
            )
            
            conn.commit()
        except Exception as e:
            print(f"⚠️  Database error adding message: {e}")
        finally:
            conn.close()
        
        return message_id  # Return ID for linking thoughts

    def add_thoughts(self, message_id: int, thoughts: List[Dict[str, Any]]):
        """Add thoughts for a message. Uses batch insert for performance."""
        if not thoughts or not message_id:
            return
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Batch insert with sequence for ordering
            data = [
                (message_id, t.get("type", "thought"), t.get("content", ""), idx)
                for idx, t in enumerate(thoughts)
            ]
            cursor.executemany(
                "INSERT INTO thoughts (message_id, type, content, sequence) VALUES (?, ?, ?, ?)",
                data
            )
            conn.commit()
        except Exception as e:
            print(f"⚠️  Database error adding thoughts: {e}")
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        return deleted

    def clear_all_sessions(self):
        """Delete all sessions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()

# Global instance
db = SessionRepository()
