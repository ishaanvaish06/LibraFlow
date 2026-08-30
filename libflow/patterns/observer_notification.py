"""
GoF Observer Pattern for Event-Driven Multi-Channel Notification System
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

from libflow.core.enums import NotificationChannel


class NotificationEvent:
    def __init__(self, event_type: str, recipient_id: str, message: str, payload: Optional[Dict[str, Any]] = None):
        self.event_type = event_type
        self.recipient_id = recipient_id
        self.message = message
        self.payload = payload or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "recipient_id": self.recipient_id,
            "message": self.message,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class NotificationObserver(ABC):
    """
    Abstract Observer in GoF Observer Pattern.
    """

    @abstractmethod
    def get_channel(self) -> NotificationChannel:
        pass

    @abstractmethod
    def on_notify(self, event: NotificationEvent) -> None:
        pass


class EmailNotificationService(NotificationObserver):
    def __init__(self):
        self.sent_emails: List[Dict[str, Any]] = []

    def get_channel(self) -> NotificationChannel:
        return NotificationChannel.EMAIL

    def on_notify(self, event: NotificationEvent) -> None:
        record = {
            "channel": "EMAIL",
            "to": event.recipient_id,
            "subject": f"[LibraFlow] {event.event_type.replace('_', ' ').title()}",
            "body": event.message,
            "timestamp": event.timestamp,
        }
        self.sent_emails.append(record)


class SmsNotificationService(NotificationObserver):
    def __init__(self):
        self.sent_sms: List[Dict[str, Any]] = []

    def get_channel(self) -> NotificationChannel:
        return NotificationChannel.SMS

    def on_notify(self, event: NotificationEvent) -> None:
        record = {
            "channel": "SMS",
            "phone": event.payload.get("phone", event.recipient_id),
            "text": event.message[:160],  # 160 char SMS limit
            "timestamp": event.timestamp,
        }
        self.sent_sms.append(record)


class InAppNotificationService(NotificationObserver):
    def __init__(self):
        # user_id -> list of alerts
        self.user_inbox: Dict[str, List[Dict[str, Any]]] = {}

    def get_channel(self) -> NotificationChannel:
        return NotificationChannel.IN_APP

    def on_notify(self, event: NotificationEvent) -> None:
        if event.recipient_id not in self.user_inbox:
            self.user_inbox[event.recipient_id] = []
        self.user_inbox[event.recipient_id].append(event.to_dict())

    def get_user_notifications(self, user_id: str) -> List[Dict[str, Any]]:
        return self.user_inbox.get(user_id, [])


class NotificationDispatcher:
    """
    Subject in GoF Observer Pattern.
    """

    def __init__(self):
        self._observers: List[NotificationObserver] = []

    def subscribe(self, observer: NotificationObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: NotificationObserver) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def dispatch(self, event: NotificationEvent) -> None:
        for observer in self._observers:
            observer.on_notify(event)
