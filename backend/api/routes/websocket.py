"""
WebSocket API Routes - Real-time Notifications
Handles WebSocket connections for push notifications
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
import json
import logging

from services.notification_service import manager, NotificationType

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    user_id: str = Query(...),
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time notifications
    
    Usage from frontend:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/ws/notifications?user_id=1&token=...');
    
    ws.onmessage = (event) => {
        const notification = JSON.parse(event.data);
        console.log('Received:', notification);
        // Display notification in UI
    };
    ```
    """
    # TODO: Validate token for authentication
    # if not validate_token(token):
    #     await websocket.close(code=1008, reason="Unauthorized")
    #     return
    
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive messages from client (for subscription management)
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Handle subscription requests
                if message.get("action") == "subscribe":
                    notification_types = [
                        NotificationType(t) for t in message.get("types", [])
                    ]
                    manager.subscribe(user_id, notification_types)
                    
                    await websocket.send_json({
                        "status": "success",
                        "message": "Subscriptions updated"
                    })
                
                elif message.get("action") == "unsubscribe":
                    notification_types = [
                        NotificationType(t) for t in message.get("types", [])
                    ]
                    manager.unsubscribe(user_id, notification_types)
                    
                    await websocket.send_json({
                        "status": "success",
                        "message": "Unsubscribed from notifications"
                    })
                
                elif message.get("action") == "ping":
                    # Heartbeat
                    await websocket.send_json({"status": "pong"})
            
            except json.JSONDecodeError:
                logger.error("Invalid JSON received from client")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"Client {user_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)


@router.get("/notifications/test")
async def test_notification(
    user_id: str = Query("1"),
    notification_type: str = Query("new_detection")
):
    """
    Test endpoint to send a sample notification
    Useful for testing the WebSocket connection
    """
    from services.notification_service import NotificationService
    
    if notification_type == "new_detection":
        await NotificationService.notify_new_detection(
            plate_number="กก1234",
            confidence=0.95,
            is_registered=True,
            user_id=user_id
        )
    elif notification_type == "low_confidence":
        await NotificationService.notify_low_confidence(
            plate_number="ขค5678",
            confidence=0.65,
            record_id=123
        )
    
    return {"status": "notification sent", "user_id": user_id}
