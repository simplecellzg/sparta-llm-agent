import queue
import json
import time
from typing import Dict, Set
from threading import Lock

class SSEManager:
    """Manages Server-Sent Events connections for real-time updates"""

    def __init__(self):
        self.clients: Dict[str, Set[queue.Queue]] = {}
        self.lock = Lock()

    def add_client(self, session_id: str, client_queue: queue.Queue):
        """Register a new SSE client for a session"""
        with self.lock:
            if session_id not in self.clients:
                self.clients[session_id] = set()
            self.clients[session_id].add(client_queue)

    def remove_client(self, session_id: str, client_queue: queue.Queue):
        """Remove an SSE client"""
        with self.lock:
            if session_id in self.clients:
                self.clients[session_id].discard(client_queue)
                if not self.clients[session_id]:
                    del self.clients[session_id]

    def send_event(self, session_id: str, event_type: str, data: dict):
        """Send an event to all clients subscribed to a session"""
        with self.lock:
            if session_id not in self.clients:
                return

            message = {
                'type': event_type,
                'timestamp': time.time(),
                'data': data
            }

            dead_clients = []
            for client_queue in self.clients[session_id]:
                try:
                    client_queue.put_nowait(message)
                except queue.Full:
                    dead_clients.append(client_queue)

            # Remove dead clients
            for dead in dead_clients:
                self.clients[session_id].discard(dead)

    def get_client_count(self, session_id: str) -> int:
        """Get number of connected clients for a session"""
        with self.lock:
            return len(self.clients.get(session_id, set()))

# Global instance
sse_manager = SSEManager()
