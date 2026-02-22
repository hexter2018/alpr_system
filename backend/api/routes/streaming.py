"""
Streaming API Routes - Camera Stream Management
Start/stop RTSP streams, configure triggers, monitor status
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging

from database.connection import get_db
from database.models import Camera
from services.streaming_manager import StreamingManager
from main import streaming_manager  # Global instance

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== PYDANTIC MODELS ====================

class CameraCreate(BaseModel):
    """Request model for creating a camera"""
    name: str
    rtsp_url: str
    location: Optional[str] = None
    trigger_config: dict  # {"type": "line", "coords": [[x1,y1], [x2,y2]]}
    fps_processing: int = 5
    skip_frames: int = 3


class CameraUpdate(BaseModel):
    """Request model for updating a camera"""
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    trigger_config: Optional[dict] = None
    fps_processing: Optional[int] = None
    skip_frames: Optional[int] = None
    is_active: Optional[bool] = None


class CameraResponse(BaseModel):
    """Response model for camera info"""
    id: int
    name: str
    rtsp_url: str
    location: Optional[str]
    trigger_config: dict
    fps_processing: int
    skip_frames: int
    is_active: bool
    status: str
    last_heartbeat: Optional[str]
    
    class Config:
        from_attributes = True


class StreamStatus(BaseModel):
    """Stream status response"""
    camera_id: int
    camera_name: str
    status: str
    frame_count: Optional[int]
    triggered_tracks: Optional[int]


# ==================== API ENDPOINTS ====================

@router.get("/cameras", response_model=List[CameraResponse])
async def list_cameras(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get list of all cameras"""
    query = db.query(Camera)
    
    if is_active is not None:
        query = query.filter(Camera.is_active == is_active)
    
    cameras = query.all()
    
    return [
        CameraResponse(
            id=cam.id,
            name=cam.name,
            rtsp_url=cam.rtsp_url,
            location=cam.location,
            trigger_config=cam.trigger_config or {},
            fps_processing=cam.fps_processing or 5,
            skip_frames=cam.skip_frames or 3,
            is_active=cam.is_active,
            status=cam.status or "offline",
            last_heartbeat=cam.last_heartbeat.isoformat() if cam.last_heartbeat else None
        )
        for cam in cameras
    ]


@router.post("/cameras", response_model=CameraResponse)
async def create_camera(
    camera: CameraCreate,
    db: Session = Depends(get_db)
):
    """Create a new camera configuration"""
    new_camera = Camera(
        name=camera.name,
        rtsp_url=camera.rtsp_url,
        location=camera.location,
        trigger_config=camera.trigger_config,
        fps_processing=camera.fps_processing,
        skip_frames=camera.skip_frames,
        is_active=True,
        status="offline"
    )
    
    db.add(new_camera)
    db.commit()
    db.refresh(new_camera)
    
    logger.info(f"✅ Camera created: {new_camera.name} (ID: {new_camera.id})")
    
    return CameraResponse(
        id=new_camera.id,
        name=new_camera.name,
        rtsp_url=new_camera.rtsp_url,
        location=new_camera.location,
        trigger_config=new_camera.trigger_config,
        fps_processing=new_camera.fps_processing,
        skip_frames=new_camera.skip_frames,
        is_active=new_camera.is_active,
        status=new_camera.status,
        last_heartbeat=None
    )


@router.put("/cameras/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: int,
    camera_update: CameraUpdate,
    db: Session = Depends(get_db)
):
    """Update camera configuration"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Update fields if provided
    if camera_update.name is not None:
        camera.name = camera_update.name
    if camera_update.rtsp_url is not None:
        camera.rtsp_url = camera_update.rtsp_url
    if camera_update.location is not None:
        camera.location = camera_update.location
    if camera_update.trigger_config is not None:
        camera.trigger_config = camera_update.trigger_config
    if camera_update.fps_processing is not None:
        camera.fps_processing = camera_update.fps_processing
    if camera_update.skip_frames is not None:
        camera.skip_frames = camera_update.skip_frames
    if camera_update.is_active is not None:
        camera.is_active = camera_update.is_active
    
    db.commit()
    db.refresh(camera)
    
    logger.info(f"✅ Camera updated: {camera.name} (ID: {camera_id})")
    
    return CameraResponse(
        id=camera.id,
        name=camera.name,
        rtsp_url=camera.rtsp_url,
        location=camera.location,
        trigger_config=camera.trigger_config,
        fps_processing=camera.fps_processing,
        skip_frames=camera.skip_frames,
        is_active=camera.is_active,
        status=camera.status,
        last_heartbeat=camera.last_heartbeat.isoformat() if camera.last_heartbeat else None
    )


@router.delete("/cameras/{camera_id}")
async def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db)
):
    """Delete a camera (soft delete - set inactive)"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Stop stream if running
    if streaming_manager and camera_id in streaming_manager.stream_processors:
        await streaming_manager.stop_stream(camera_id)
    
    # Soft delete
    camera.is_active = False
    camera.status = "deleted"
    db.commit()
    
    logger.info(f"🗑️  Camera deleted: {camera.name} (ID: {camera_id})")
    
    return {"success": True, "message": "Camera deleted successfully"}


@router.post("/cameras/{camera_id}/start")
async def start_camera_stream(
    camera_id: int,
    db: Session = Depends(get_db)
):
    """Start processing a camera stream"""
    if not streaming_manager:
        raise HTTPException(status_code=500, detail="Streaming manager not initialized")
    
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    if not camera.is_active:
        raise HTTPException(status_code=400, detail="Camera is not active")
    
    # Check if already running
    if camera_id in streaming_manager.stream_processors:
        return {
            "success": False,
            "message": "Stream is already running",
            "camera_id": camera_id
        }
    
    # Start stream
    success = await streaming_manager.start_stream(camera_id)
    
    if success:
        logger.info(f"🎥 Stream started: {camera.name} (ID: {camera_id})")
        return {
            "success": True,
            "message": "Stream started successfully",
            "camera_id": camera_id
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to start stream")


@router.post("/cameras/{camera_id}/stop")
async def stop_camera_stream(
    camera_id: int
):
    """Stop processing a camera stream"""
    if not streaming_manager:
        raise HTTPException(status_code=500, detail="Streaming manager not initialized")
    
    if camera_id not in streaming_manager.stream_processors:
        return {
            "success": False,
            "message": "Stream is not running",
            "camera_id": camera_id
        }
    
    await streaming_manager.stop_stream(camera_id)
    
    logger.info(f"🛑 Stream stopped: Camera ID {camera_id}")
    
    return {
        "success": True,
        "message": "Stream stopped successfully",
        "camera_id": camera_id
    }


@router.get("/streams/active", response_model=List[StreamStatus])
async def get_active_streams(
    db: Session = Depends(get_db)
):
    """Get list of currently active streams"""
    if not streaming_manager:
        return []
    
    active_camera_ids = streaming_manager.get_active_streams()
    
    streams = []
    for camera_id in active_camera_ids:
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        status = streaming_manager.get_stream_status(camera_id)
        
        if camera and status:
            streams.append(StreamStatus(
                camera_id=camera_id,
                camera_name=camera.name,
                status=status["status"],
                frame_count=status.get("frame_count"),
                triggered_tracks=status.get("triggered_tracks")
            ))
    
    return streams


@router.get("/cameras/{camera_id}/status")
async def get_camera_stream_status(
    camera_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed status of a specific camera stream"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Check if stream is active
    is_streaming = streaming_manager and camera_id in streaming_manager.stream_processors
    
    stream_info = None
    if is_streaming:
        stream_info = streaming_manager.get_stream_status(camera_id)
    
    return {
        "camera_id": camera_id,
        "camera_name": camera.name,
        "is_active": camera.is_active,
        "db_status": camera.status,
        "is_streaming": is_streaming,
        "last_heartbeat": camera.last_heartbeat.isoformat() if camera.last_heartbeat else None,
        "stream_info": stream_info
    }
