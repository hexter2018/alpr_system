"""
Streaming Manager - RTSP Video Stream Processing with ByteTrack
Handles multiple camera streams with real ByteTrack tracking and trigger line logic
Production-ready implementation using Ultralytics built-in tracking module
"""

import cv2
import asyncio
import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
import logging
from datetime import datetime
from pathlib import Path
import threading
import time

from services.alpr_pipeline import ALPRPipeline
from services.validation_service import ValidationService
from database.connection import get_db_context
from database.models import PlateRecord, Camera, ProcessingModeEnum, RecordStatusEnum

logger = logging.getLogger(__name__)


# ==================== BYTETRACK CONFIGURATION ====================

class ByteTrackConfig:
    """Configuration for ByteTrack tracker"""
    
    # ByteTrack parameters
    TRACK_THRESH = 0.5      # Detection confidence threshold for tracking
    TRACK_BUFFER = 30       # Number of frames to keep lost tracks
    MATCH_THRESH = 0.8      # IoU threshold for matching
    
    # Frame processing
    MIN_BOX_AREA = 100      # Minimum bounding box area to process
    
    @staticmethod
    def get_tracker_config() -> str:
        """
        Get ByteTrack configuration file path
        
        Ultralytics supports:
        - bytetrack.yaml (default - recommended)
        - botsort.yaml (alternative)
        
        Returns:
            Path to tracker configuration file
        """
        return "bytetrack.yaml"


# ==================== STREAM PROCESSOR ====================

@dataclass
class StreamConfig:
    """Configuration for a camera stream"""
    camera_id: int
    rtsp_url: str
    trigger_config: Dict  # {"type": "line", "coords": [[x1,y1], [x2,y2]]}
    fps_processing: int = 5  # Process every Nth frame
    skip_frames: int = 3


class StreamProcessor:
    """
    Processes a single RTSP camera stream with ByteTrack tracking
    
    Key Features:
    - Real ByteTrack integration via Ultralytics
    - Trigger line detection with trajectory tracking
    - Automatic track ID management
    - Deduplication to prevent multiple detections per vehicle
    """
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.cap = None
        self.is_running = False
        self.alpr_pipeline = ALPRPipeline()
        self.validation_service = ValidationService()
        self.frame_count = 0
        
        # ByteTrack tracking state
        self.triggered_tracks: Set[int] = set()  # Tracks that crossed the trigger line
        self.track_trajectories: Dict[int, List[Tuple[float, float]]] = {}  # track_id -> [(x, y), ...]
        self.last_triggered_frame: Dict[int, int] = {}  # track_id -> frame_number
        
        # Statistics
        self.total_detections = 0
        self.total_triggers = 0
        
        logger.info(f"StreamProcessor initialized for camera {self.config.camera_id}")
    
    def start(self) -> bool:
        """Start processing stream with ByteTrack"""
        self.is_running = True
        
        # Open RTSP stream
        logger.info(f"📹 Connecting to camera {self.config.camera_id}: {self.config.rtsp_url}")
        
        # OpenCV VideoCapture with optimizations
        self.cap = cv2.VideoCapture(self.config.rtsp_url)
        
        # Set buffer size to reduce latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not self.cap.isOpened():
            logger.error(f"❌ Failed to open stream: {self.config.rtsp_url}")
            return False
        
        logger.info(f"✅ Stream connected: Camera {self.config.camera_id}")
        
        # Get stream properties
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Stream info: {width}x{height} @ {fps:.1f} FPS")
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.processing_thread.start()
        
        return True
    
    def stop(self):
        """Stop processing stream"""
        self.is_running = False
        if self.cap:
            self.cap.release()
        logger.info(f"🛑 Stream stopped: Camera {self.config.camera_id}")
    
    def _process_loop(self):
        """
        Main processing loop with ByteTrack tracking
        
        Flow:
        1. Read frame from RTSP stream
        2. Skip frames based on configuration
        3. Run YOLO with ByteTrack (model.track())
        4. Extract track IDs from results
        5. Update trajectories
        6. Check trigger line crossing
        7. Process triggered vehicles
        """
        while self.is_running:
            try:
                ret, frame = self.cap.read()
                
                if not ret:
                    logger.warning(f"⚠️  Failed to read frame from camera {self.config.camera_id}")
                    time.sleep(1)
                    
                    # Try to reconnect
                    if not self._reconnect():
                        break
                    continue
                
                self.frame_count += 1
                
                # Skip frames based on configuration
                if self.frame_count % self.config.skip_frames != 0:
                    continue
                
                # Process frame with ByteTrack
                self._process_frame(frame)
                
            except Exception as e:
                logger.error(f"❌ Error processing frame: {e}", exc_info=True)
                time.sleep(1)
    
    def _process_frame(self, frame: np.ndarray):
        """
        Process a single frame with ByteTrack tracking
        
        Args:
            frame: Video frame (numpy array)
        """
        try:
            # ==================== BYTETRACK TRACKING ====================
            # Use Ultralytics built-in tracking instead of manual detection
            # This automatically maintains track IDs across frames
            
            results = self.alpr_pipeline.yolo_model.track(
                source=frame,
                conf=ByteTrackConfig.TRACK_THRESH,
                persist=True,  # Maintain tracks across frames
                tracker=ByteTrackConfig.get_tracker_config(),  # Use ByteTrack
                verbose=False,
                stream=False
            )
            
            # Extract tracking information
            if not results or len(results) == 0:
                return
            
            result = results[0]  # First result (single frame)
            
            # Check if tracking data exists
            if result.boxes is None or len(result.boxes) == 0:
                return
            
            boxes = result.boxes
            
            # Get trigger line coordinates
            trigger_line = self._get_trigger_line()
            
            # Process each tracked detection
            for box in boxes:
                # Extract bounding box and track ID
                xyxy = box.xyxy[0].cpu().numpy()  # [x1, y1, x2, y2]
                conf = float(box.conf[0])
                
                # Check if track ID exists (ByteTrack assigns this)
                if box.id is None:
                    continue  # Skip detections without track ID
                
                track_id = int(box.id[0])
                
                # Calculate centroid for trajectory tracking
                x1, y1, x2, y2 = xyxy
                centroid_x = (x1 + x2) / 2
                centroid_y = (y1 + y2) / 2
                centroid = (centroid_x, centroid_y)
                
                # Update trajectory
                if track_id not in self.track_trajectories:
                    self.track_trajectories[track_id] = []
                
                self.track_trajectories[track_id].append(centroid)
                
                # Keep only last 30 positions (ByteTrack buffer)
                if len(self.track_trajectories[track_id]) > ByteTrackConfig.TRACK_BUFFER:
                    self.track_trajectories[track_id] = self.track_trajectories[track_id][-ByteTrackConfig.TRACK_BUFFER:]
                
                # ==================== TRIGGER LINE DETECTION ====================
                # Check if this track crossed the trigger line
                
                # Skip if already triggered recently
                if track_id in self.triggered_tracks:
                    # Allow re-trigger after 100 frames (avoid duplicate captures)
                    if self.frame_count - self.last_triggered_frame.get(track_id, 0) < 100:
                        continue
                
                # Need at least 2 positions to check crossing
                if len(self.track_trajectories[track_id]) < 2:
                    continue
                
                # Check if line was crossed
                if self._check_trigger_crossing(track_id, trigger_line):
                    logger.info(f"🎯 Trigger activated: Track {track_id}, Frame {self.frame_count}, Camera {self.config.camera_id}")
                    
                    # Mark as triggered
                    self.triggered_tracks.add(track_id)
                    self.last_triggered_frame[track_id] = self.frame_count
                    self.total_triggers += 1
                    
                    # Capture and process the plate
                    bbox_dict = {
                        "x1": int(x1),
                        "y1": int(y1),
                        "x2": int(x2),
                        "y2": int(y2)
                    }
                    
                    self._capture_and_process(
                        frame=frame,
                        bbox=bbox_dict,
                        track_id=track_id,
                        confidence=conf
                    )
            
            # Clean up old trajectories (tracks not seen for 50 frames)
            self._cleanup_old_tracks()
            
        except Exception as e:
            logger.error(f"❌ Error in _process_frame: {e}", exc_info=True)
    
    def _get_trigger_line(self) -> List[Tuple[float, float]]:
        """
        Get trigger line coordinates from configuration
        
        Returns:
            List of two points [(x1, y1), (x2, y2)] defining the line
        """
        trigger_config = self.config.trigger_config
        
        if trigger_config.get("type") == "line" and "coords" in trigger_config:
            coords = trigger_config["coords"]
            if len(coords) == 2 and len(coords[0]) == 2 and len(coords[1]) == 2:
                return [
                    (float(coords[0][0]), float(coords[0][1])),
                    (float(coords[1][0]), float(coords[1][1]))
                ]
        
        # Default horizontal line at middle of frame
        logger.warning(f"Invalid trigger config for camera {self.config.camera_id}, using default")
        return [(0, 360), (1280, 360)]
    
    def _check_trigger_crossing(
        self,
        track_id: int,
        trigger_line: List[Tuple[float, float]]
    ) -> bool:
        """
        Check if a track crossed the trigger line using trajectory
        
        Uses line segment intersection algorithm to detect crossing
        
        Args:
            track_id: ByteTrack track ID
            trigger_line: Two points defining the trigger line
        
        Returns:
            True if the track crossed the line
        """
        trajectory = self.track_trajectories.get(track_id, [])
        
        if len(trajectory) < 2:
            return False
        
        # Check last movement (previous position to current position)
        prev_pos = trajectory[-2]
        curr_pos = trajectory[-1]
        
        # Check if movement line intersects trigger line
        return self._line_intersection(
            trigger_line[0], trigger_line[1],
            prev_pos, curr_pos
        )
    
    def _line_intersection(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        p4: Tuple[float, float]
    ) -> bool:
        """
        Check if two line segments intersect using CCW algorithm
        
        Args:
            p1, p2: First line segment (trigger line)
            p3, p4: Second line segment (movement trajectory)
        
        Returns:
            True if lines intersect
        """
        def ccw(A, B, C):
            """Check if three points are in counter-clockwise order"""
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
        
        # Line segments intersect if endpoints are on opposite sides
        return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)
    
    def _capture_and_process(
        self,
        frame: np.ndarray,
        bbox: Dict,
        track_id: int,
        confidence: float
    ):
        """
        Capture plate region and process through ALPR pipeline
        
        Args:
            frame: Video frame
            bbox: Bounding box dictionary {x1, y1, x2, y2}
            track_id: ByteTrack track ID
            confidence: Detection confidence
        """
        try:
            # Extract bounding box coordinates
            x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
            
            # Add padding (10% on each side)
            padding_x = int((x2 - x1) * 0.1)
            padding_y = int((y2 - y1) * 0.1)
            
            # Apply padding with bounds checking
            x1 = max(0, x1 - padding_x)
            y1 = max(0, y1 - padding_y)
            x2 = min(frame.shape[1], x2 + padding_x)
            y2 = min(frame.shape[0], y2 + padding_y)
            
            # Check minimum size
            if (x2 - x1) < 50 or (y2 - y1) < 20:
                logger.warning(f"⚠️  Bounding box too small for track {track_id}, skipping")
                return
            
            # Crop the plate region
            cropped_plate = frame[y1:y2, x1:x2]
            
            # Save cropped plate
            crop_dir = Path("storage/cropped_plates")
            crop_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            crop_filename = f"stream_cam{self.config.camera_id}_track{track_id}_{timestamp}.jpg"
            crop_path = crop_dir / crop_filename
            
            cv2.imwrite(str(crop_path), cropped_plate)
            
            # Perform OCR
            logger.info(f"🔍 Running OCR on track {track_id}")
            ocr_result = self.alpr_pipeline.perform_ocr(str(crop_path))
            
            if not ocr_result.get("success"):
                logger.warning(f"⚠️  OCR failed for track {track_id}")
                return
            
            # Validate against master data
            with get_db_context() as db:
                validation_result = self.validation_service.validate_plate(
                    plate_number=ocr_result["plate_number"],
                    province_code=ocr_result.get("province_code"),
                    province_text=ocr_result.get("full_text"),  # Use full OCR text for better matching
                    db=db
                )
                
                # Save to database
                plate_record = PlateRecord(
                    processing_mode=ProcessingModeEnum.STREAM_RTSP,
                    record_status=RecordStatusEnum.ALPR,
                    
                    # OCR Results
                    ocr_plate_number=ocr_result["plate_number"],
                    ocr_province_code=ocr_result.get("province_code"),
                    ocr_full_text=ocr_result["full_text"],
                    ocr_confidence=ocr_result["confidence"],
                    
                    # Final data
                    final_plate_number=ocr_result["plate_number"],
                    final_province_code=validation_result.get("province_code") or ocr_result.get("province_code"),
                    province_id=validation_result.get("province_id"),
                    
                    # Validation
                    is_registered=validation_result["is_registered"],
                    registered_vehicle_id=validation_result.get("registered_vehicle_id"),
                    validation_score=validation_result.get("validation_score"),
                    
                    # Images
                    cropped_plate_path=str(crop_path),
                    
                    # Detection metadata
                    detection_bbox=bbox,
                    detection_confidence=confidence,
                    
                    # Streaming metadata
                    camera_id=self.config.camera_id,
                    frame_number=self.frame_count,
                    tracking_id=str(track_id),
                    trigger_line_position=self.config.trigger_config,
                    
                    # Timestamps
                    capture_timestamp=datetime.now(),
                    processing_timestamp=datetime.now(),
                )
                
                db.add(plate_record)
                db.commit()
                
                logger.info(
                    f"✅ Saved stream record: {ocr_result['plate_number']} "
                    f"(Track {track_id}, Confidence {ocr_result['confidence']:.2%})"
                )
                
        except Exception as e:
            logger.error(f"❌ Failed to process track {track_id}: {e}", exc_info=True)
    
    def _cleanup_old_tracks(self):
        """
        Clean up tracks that haven't been seen recently
        
        Prevents memory bloat from accumulating old trajectory data
        """
        current_frame = self.frame_count
        tracks_to_remove = []
        
        for track_id, last_frame in self.last_triggered_frame.items():
            # Remove tracks not seen for 50 frames
            if current_frame - last_frame > 50:
                tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            if track_id in self.track_trajectories:
                del self.track_trajectories[track_id]
            if track_id in self.last_triggered_frame:
                del self.last_triggered_frame[track_id]
            if track_id in self.triggered_tracks:
                self.triggered_tracks.remove(track_id)
    
    def _reconnect(self) -> bool:
        """
        Attempt to reconnect to RTSP stream
        
        Returns:
            True if reconnection successful
        """
        logger.info(f"🔄 Attempting to reconnect camera {self.config.camera_id}")
        
        if self.cap:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(self.config.rtsp_url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if self.cap.isOpened():
            logger.info(f"✅ Reconnected camera {self.config.camera_id}")
            return True
        else:
            logger.error(f"❌ Failed to reconnect camera {self.config.camera_id}")
            return False


# ==================== STREAMING MANAGER ====================

class StreamingManager:
    """
    Manages multiple camera streams with ByteTrack tracking
    
    Features:
    - Multi-camera concurrent processing
    - ByteTrack integration for reliable tracking
    - Automatic reconnection on failure
    - Statistics and monitoring
    """
    
    def __init__(self):
        self.stream_processors: Dict[int, StreamProcessor] = {}
        logger.info("✅ StreamingManager initialized with ByteTrack support")
    
    async def start_stream(self, camera_id: int) -> bool:
        """
        Start processing a camera stream with ByteTrack
        
        Args:
            camera_id: Database camera ID
        
        Returns:
            True if stream started successfully
        """
        # Get camera configuration from database
        with get_db_context() as db:
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            
            if not camera:
                logger.error(f"Camera {camera_id} not found")
                return False
            
            if not camera.is_active:
                logger.error(f"Camera {camera_id} is not active")
                return False
            
            # Create stream config
            config = StreamConfig(
                camera_id=camera.id,
                rtsp_url=camera.rtsp_url,
                trigger_config=camera.trigger_config or {"type": "line", "coords": [[0, 360], [1280, 360]]},
                fps_processing=camera.fps_processing or 5,
                skip_frames=camera.skip_frames or 3
            )
            
            # Create and start stream processor
            processor = StreamProcessor(config)
            if processor.start():
                self.stream_processors[camera_id] = processor
                
                # Update camera status
                camera.status = "online"
                camera.last_heartbeat = datetime.now()
                db.commit()
                
                logger.info(f"🎥 Stream started with ByteTrack: Camera {camera_id}")
                return True
            
            return False
    
    async def stop_stream(self, camera_id: int):
        """Stop processing a camera stream"""
        if camera_id in self.stream_processors:
            self.stream_processors[camera_id].stop()
            del self.stream_processors[camera_id]
            
            # Update camera status
            with get_db_context() as db:
                camera = db.query(Camera).filter(Camera.id == camera_id).first()
                if camera:
                    camera.status = "offline"
                    db.commit()
            
            logger.info(f"🛑 Stream stopped: Camera {camera_id}")
    
    async def stop_all_streams(self):
        """Stop all active streams"""
        for camera_id in list(self.stream_processors.keys()):
            await self.stop_stream(camera_id)
    
    def get_active_streams(self) -> List[int]:
        """Get list of active camera IDs"""
        return list(self.stream_processors.keys())
    
    def get_stream_status(self, camera_id: int) -> Optional[Dict]:
        """
        Get status of a specific stream
        
        Returns:
            Dict with stream statistics or None if not running
        """
        if camera_id in self.stream_processors:
            processor = self.stream_processors[camera_id]
            return {
                "camera_id": camera_id,
                "status": "online",
                "frame_count": processor.frame_count,
                "triggered_tracks": len(processor.triggered_tracks),
                "total_triggers": processor.total_triggers,
                "active_tracks": len(processor.track_trajectories)
            }
        return None