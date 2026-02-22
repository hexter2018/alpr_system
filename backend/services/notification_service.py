"""
Notification Service - Real-time Alerts via WebSocket
Sends notifications for: new detections, low confidence, MLPR corrections, system events
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
import asyncio
import logging
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications"""
    NEW_DETECTION = "new_detection"
    LOW_CONFIDENCE = "low_confidence"
    MLPR_CORRECTION = "mlpr_correction"
    STREAM_STARTED = "stream_started"
    STREAM_STOPPED = "stream_stopped"
    SYSTEM_ERROR = "system_error"
    BATCH_COMPLETE = "batch_complete"
    SUSPICIOUS_VEHICLE = "suspicious_vehicle"


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Notification:
    """Notification message structure"""
    
    def __init__(
        self,
        type: NotificationType,
        priority: NotificationPriority,
        title: str,
        message: str,
        data: dict = None
    ):
        self.type = type
        self.priority = priority
        self.title = title
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "type": self.type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp
        }


class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Store subscriptions (which users want which notification types)
        self.subscriptions: Dict[str, Set[NotificationType]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Connect a new WebSocket client"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
            self.subscriptions[user_id] = set(NotificationType)  # Subscribe to all by default
        
        self.active_connections[user_id].append(websocket)
        logger.info(f"✅ WebSocket connected: User {user_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Disconnect a WebSocket client"""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            
            # Clean up if no more connections
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                del self.subscriptions[user_id]
        
        logger.info(f"🔌 WebSocket disconnected: User {user_id}")
    
    async def send_personal_notification(
        self,
        user_id: str,
        notification: Notification
    ):
        """Send notification to a specific user"""
        if user_id not in self.active_connections:
            return
        
        # Check if user is subscribed to this notification type
        if notification.type not in self.subscriptions.get(user_id, set()):
            return
        
        message = json.dumps(notification.to_dict())
        
        # Send to all connections for this user
        disconnected = []
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Error sending to {user_id}: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn, user_id)
    
    async def broadcast(
        self,
        notification: Notification,
        exclude_users: List[str] = None
    ):
        """Broadcast notification to all connected users"""
        exclude_users = exclude_users or []
        
        for user_id in list(self.active_connections.keys()):
            if user_id not in exclude_users:
                await self.send_personal_notification(user_id, notification)
    
    def subscribe(self, user_id: str, notification_types: List[NotificationType]):
        """Subscribe user to specific notification types"""
        if user_id not in self.subscriptions:
            self.subscriptions[user_id] = set()
        
        self.subscriptions[user_id].update(notification_types)
    
    def unsubscribe(self, user_id: str, notification_types: List[NotificationType]):
        """Unsubscribe user from specific notification types"""
        if user_id in self.subscriptions:
            self.subscriptions[user_id] -= set(notification_types)


# Global connection manager instance
manager = ConnectionManager()


class NotificationService:
    """High-level notification service"""
    
    @staticmethod
    async def notify_new_detection(
        plate_number: str,
        confidence: float,
        is_registered: bool,
        user_id: str = None
    ):
        """Notify about new plate detection"""
        priority = NotificationPriority.HIGH if is_registered else NotificationPriority.MEDIUM
        
        notification = Notification(
            type=NotificationType.NEW_DETECTION,
            priority=priority,
            title="New License Plate Detected",
            message=f"Plate {plate_number} detected with {confidence*100:.1f}% confidence",
            data={
                "plate_number": plate_number,
                "confidence": confidence,
                "is_registered": is_registered
            }
        )
        
        if user_id:
            await manager.send_personal_notification(user_id, notification)
        else:
            await manager.broadcast(notification)
    
    @staticmethod
    async def notify_low_confidence(
        plate_number: str,
        confidence: float,
        record_id: int
    ):
        """Notify about low confidence detection requiring verification"""
        notification = Notification(
            type=NotificationType.LOW_CONFIDENCE,
            priority=NotificationPriority.HIGH,
            title="Low Confidence Detection",
            message=f"Plate {plate_number} detected with only {confidence*100:.1f}% confidence. Please verify.",
            data={
                "plate_number": plate_number,
                "confidence": confidence,
                "record_id": record_id
            }
        )
        
        await manager.broadcast(notification)
    
    @staticmethod
    async def notify_mlpr_correction(
        record_id: int,
        original_plate: str,
        corrected_plate: str,
        corrected_by: str
    ):
        """Notify about MLPR correction"""
        notification = Notification(
            type=NotificationType.MLPR_CORRECTION,
            priority=NotificationPriority.MEDIUM,
            title="Plate Corrected",
            message=f"{original_plate} → {corrected_plate} by {corrected_by}",
            data={
                "record_id": record_id,
                "original": original_plate,
                "corrected": corrected_plate,
                "corrected_by": corrected_by
            }
        )
        
        await manager.broadcast(notification)
    
    @staticmethod
    async def notify_stream_event(
        camera_id: int,
        camera_name: str,
        event: str,  # "started" or "stopped"
    ):
        """Notify about stream events"""
        notification_type = (
            NotificationType.STREAM_STARTED if event == "started" 
            else NotificationType.STREAM_STOPPED
        )
        
        notification = Notification(
            type=notification_type,
            priority=NotificationPriority.LOW,
            title=f"Stream {event.title()}",
            message=f"Camera '{camera_name}' stream has {event}",
            data={
                "camera_id": camera_id,
                "camera_name": camera_name
            }
        )
        
        await manager.broadcast(notification)
    
    @staticmethod
    async def notify_batch_complete(
        total: int,
        successful: int,
        failed: int,
        user_id: str
    ):
        """Notify about batch upload completion"""
        notification = Notification(
            type=NotificationType.BATCH_COMPLETE,
            priority=NotificationPriority.MEDIUM,
            title="Batch Upload Complete",
            message=f"Processed {total} images: {successful} successful, {failed} failed",
            data={
                "total": total,
                "successful": successful,
                "failed": failed
            }
        )
        
        await manager.send_personal_notification(user_id, notification)
    
    @staticmethod
    async def notify_suspicious_vehicle(
        plate_number: str,
        reason: str,
        record_id: int
    ):
        """Notify about suspicious vehicle detection"""
        notification = Notification(
            type=NotificationType.SUSPICIOUS_VEHICLE,
            priority=NotificationPriority.CRITICAL,
            title="🚨 Suspicious Vehicle Detected",
            message=f"Plate {plate_number}: {reason}",
            data={
                "plate_number": plate_number,
                "reason": reason,
                "record_id": record_id
            }
        )
        
        await manager.broadcast(notification)
    
    @staticmethod
    async def notify_system_error(
        error_type: str,
        message: str,
        details: dict = None
    ):
        """Notify about system errors"""
        notification = Notification(
            type=NotificationType.SYSTEM_ERROR,
            priority=NotificationPriority.CRITICAL,
            title=f"System Error: {error_type}",
            message=message,
            data=details or {}
        )
        
        await manager.broadcast(notification)


# Example usage in API routes:
"""
from services.notification_service import NotificationService

# In upload endpoint after successful detection:
await NotificationService.notify_new_detection(
    plate_number=result.plate_number,
    confidence=result.confidence,
    is_registered=result.is_registered
)

# In verification endpoint after correction:
await NotificationService.notify_mlpr_correction(
    record_id=record.id,
    original_plate=record.ocr_plate_number,
    corrected_plate=corrected_plate_number,
    corrected_by=current_user.username
)

# In streaming manager when stream starts:
await NotificationService.notify_stream_event(
    camera_id=camera.id,
    camera_name=camera.name,
    event="started"
)
"""
