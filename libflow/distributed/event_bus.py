"""
Distributed In-Memory Event Bus / Message Broker
Decouples producers and consumers using Publish/Subscribe pattern.
"""
from typing import Dict, List, Callable, Any
from collections import defaultdict
import threading


class DistributedEventBus:
    """
    Thread-safe Pub/Sub message bus.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        self._lock = threading.Lock()
        self.published_events_history: List[Dict[str, Any]] = []

    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._subscribers[topic].append(handler)

    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            handlers = list(self._subscribers.get(topic, []))
            self.published_events_history.append({"topic": topic, "payload": payload})

        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                print(f"[EventBus Error] Error in handler for topic {topic}: {e}")
