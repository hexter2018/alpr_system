"""
Streaming Manager - RTSP Video Stream Processing
Handles multiple camera streams with ByteTrack tracking and trigger line logic
"""

import cv2
import asyncio
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime
from pathlib import Path
import threading

from services.alpr_pipeline import ALPRPipeline
from services.validation_service import ValidationService
from database.connection import get_db_context
from database.models import PlateRecord, Camera, ProcessingModeEnum, RecordStatusEnum

logger = logging.getLogger(__name__)

# ==================== TRACKER WRAPPER ====================

class ObjectTracker:
    """
    Wrapper for ByteTrack/DeepSORT tracking
    Tracks vehicles across frames
    """
    
    def __init__(self, tracker_type: str = "bytetrack"):
        """
        Initialize tracker
        
        Args:
            tracker_type: "bytetrack" or "deepsort"
        """
        self.tracker_type = tracker_type
        self.tracks: Dict[int, Dict] = {}  # track_id -> track_info
        self.next_track_id = 1
        
        # For simplicity, using basic centroid tracking
        # In production, integrate actual ByteTrack
        logger.info(f"Initialized {tracker_type} tracker")
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """
        Update tracker with new detections
        
        Args:
            detections: List of detection dicts with bbox and confidence
        
        Returns:
            List of tracked objects with track_id
        """
        # Simple centroid-based tracking (replace with ByteTrack in production)
        tracked_objects = []
        
        for detection in detections:
            bbox = detection["bbox"]
            centroid_x = (bbox["x1"] + bbox["x2"]) / 2
            centroid_y = (bbox["y1"] + bbox["y2"]) / 2
            
            # Find closest existing track
            min_distance = float('inf')
            matched_track_id = None
            
            for track_id, track_info in self.tracks.items():
                prev_centroid = track_info["centroid"]
                distance = np.sqrt(
                    (centroid_x - prev_centroid[0])**2 + 
                    (centroid_y - prev_centroid[1])**2
                )
                
                if distance < min_distance and distance < 100:  # Max matching distance
                    min_distance = distance
                    matched_track_id = track_id
            
            # Update or create track
            if matched_track_id:
                track_id = matched_track_id
                self.tracks[track_id]["centroid"] = (centroid_x, centroid_y)
                self.tracks[track_id]["bbox"] = bbox
                self.tracks[track_id]["positions"].append((centroid_x, centroid_y))
            else:
                track_id = self.next_track_id
                self.next_track_id += 1
                self.tracks[track_id] = {
                    "centroid": (centroid_x, centroid_y),
                    "bbox": bbox,
                    "positions": [(centroid_x, centroid_y)],
                    "triggered": False
                }
            
            tracked_objects.append({
                "track_id": track_id,
                "bbox": bbox,
                "confidence": detection["confidence"],
                "centroid": (centroid_x, centroid_y),
                "positions": self.tracks[track_id]["positions"]
            })
        
        return tracked_objects


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
    """Processes a single RTSP camera stream"""
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.cap = None
        self.is_running = False
        self.alpr_pipeline = ALPRPipeline()
        self.validation_service = ValidationService()
        self.tracker = ObjectTracker(tracker_type="bytetrack")
        self.frame_count = 0
        self.triggered_tracks: set = set()  # Tracks that already triggered
    
    def start(self):
        """Start processing stream"""
        self.is_running = True
        
        # Open RTSP stream
        logger.info(f"📹 Connecting to camera {self.config.camera_id}: {self.config.rtsp_url}")
        self.cap = cv2.VideoCapture(self.config.rtsp_url)
        
        if not self.cap.isOpened():
            logger.error(f"❌ Failed to open stream: {self.config.rtsp_url}")
            return False
        
        logger.info(f"✅ Stream connected: Camera {self.config.camera_id}")
        
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
        """Main processing loop"""
        while self.is_running:
            try:
                ret, frame = self.cap.read()
                
                if not ret:
                    logger.warning(f"⚠️  Failed to read frame from camera {self.config.camera_id}")
                    time.sleep(1)
                    continue
                
                self.frame_count += 1
                
                # Skip frames based on configuration
                if self.frame_count % self.config.skip_frames != 0:
                    continue
                
                # Process frame
                self._process_frame(frame)
                
            except Exception as e:
                logger.error(f"❌ Error processing frame: {e}", exc_info=True)
                time.sleep(1)
    
    def _process_frame(self, frame: np.ndarray):
        """Process a single frame"""
        # Run YOLO detection
        results = self.alpr_pipeline.yolo_model.predict(
            source=frame,
            conf=0.4,
            verbose=False
        )
        
        # Extract detections
        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                detections.append({
                    "bbox": {
                        "x1": int(x1),
                        "y1": int(y1),
                        "x2": int(x2),
                        "y2": int(y2)
                    },
                    "confidence": float(box.conf[0])
                })
        
        # Update tracker
        tracked_objects = self.tracker.update(detections)
        
        # Check trigger line for each tracked object
        trigger_line = self._get_trigger_line()
        
        for obj in tracked_objects:
            track_id = obj["track_id"]
            
            # Skip if already triggered
            if track_id in self.triggered_tracks:
                continue
            
            # Check if crossed trigger line
            if self._check_trigger(obj, trigger_line):
                logger.info(f"🎯 Trigger activated: Track {track_id}, Camera {self.config.camera_id}")
                
                # Mark as triggered
                self.triggered_tracks.add(track_id)
                
                # Crop and process the plate
                self._capture_and_process(frame, obj)
    
    def _get_trigger_line(self) -> List[Tuple[int, int]]:
        """Get trigger line coordinates from config"""
        trigger_config = self.config.trigger_config
        
        if trigger_config["type"] == "line":
            coords = trigger_config["coords"]
            return [(coords[0][0], coords[0][1]), (coords[1][0], coords[1][1])]
        
        # Default horizontal line at middle of frame
        return [(0, 360), (1280, 360)]
    
    def _check_trigger(
        self,
        tracked_obj: Dict,
        trigger_line: List[Tuple[int, int]]
    ) -> bool:
        """Check if object crossed trigger line"""
        positions = tracked_obj["positions"]
        
        if len(positions) < 2:
            return False
        
        current_pos = positions[-1]
        previous_pos = positions[-2]
        
        # Check line intersection
        return self._line_intersection(
            trigger_line[0], trigger_line[1],
            previous_pos, current_pos
        )
    
    def _line_intersection(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        p4: Tuple[float, float]
    ) -> bool:
        """Check if two line segments intersect"""
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
        
        return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)
    
    def _capture_and_process(self, frame: np.ndarray, tracked_obj: Dict):
        """Capture plate and process through ALPR pipeline"""
        try:
            # Crop the plate region
            bbox = tracked_obj["bbox"]
            x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
            
            # Add padding
            padding_x = int((x2 - x1) * 0.1)
            padding_y = int((y2 - y1) * 0.1)
            x1 = max(0, x1 - padding_x)
            y1 = max(0, y1 - padding_y)
            x2 = min(frame.shape[1], x2 + padding_x)
            y2 = min(frame.shape[0], y2 + padding_y)
            
            cropped_plate = frame[y1:y2, x1:x2]
            
            # Save cropped plate
            crop_dir = Path("storage/cropped_plates")
            crop_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            track_id = tracked_obj["track_id"]
            crop_filename = f"stream_cam{self.config.camera_id}_track{track_id}_{timestamp}.jpg"
            crop_path = crop_dir / crop_filename
            
            cv2.imwrite(str(crop_path), cropped_plate)
            
            # Perform OCR
            ocr_result = self.alpr_pipeline.perform_ocr(str(crop_path))
            
            # Validate
            with get_db_context() as db:
                validation_result = self.validation_service.validate_plate(
                    plate_number=ocr_result["plate_number"],
                    province_code=ocr_result["province_code"],
                    db=db
                )
                
                # Save to database
                plate_record = PlateRecord(
                    processing_mode=ProcessingModeEnum.STREAM_RTSP,
                    record_status=RecordStatusEnum.ALPR,
                    
                    # OCR Results
                    ocr_plate_number=ocr_result["plate_number"],
                    ocr_province_code=ocr_result["province_code"],
                    ocr_full_text=ocr_result["full_text"],
                    ocr_confidence=ocr_result["confidence"],
                    
                    # Final data
                    final_plate_number=ocr_result["plate_number"],
                    final_province_code=ocr_result["province_code"],
                    province_id=validation_result.get("province_id"),
                    
                    # Validation
                    is_registered=validation_result["is_registered"],
                    registered_vehicle_id=validation_result.get("registered_vehicle_id"),
                    validation_score=validation_result.get("validation_score"),
                    
                    # Images
                    cropped_plate_path=str(crop_path),
                    
                    # Detection metadata
                    detection_bbox=bbox,
                    detection_confidence=tracked_obj["confidence"],
                    
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
                
                logger.info(f"✅ Saved stream record: {ocr_result['plate_number']} (Track {track_id})")
        
        except Exception as e:
            logger.error(f"❌ Failed to process captured plate: {e}", exc_info=True)


# ==================== STREAMING MANAGER ====================

class StreamingManager:
    """Manages multiple camera streams"""
    
    def __init__(self):
        self.stream_processors: Dict[int, StreamProcessor] = {}
        logger.info("Streaming Manager initialized")
    
    async def start_stream(self, camera_id: int) -> bool:
        """Start processing a camera stream"""
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
            
            logger.info(f"Stream stopped: Camera {camera_id}")
    
    async def stop_all_streams(self):
        """Stop all active streams"""
        for camera_id in list(self.stream_processors.keys()):
            await self.stop_stream(camera_id)
    
    def get_active_streams(self) -> List[int]:
        """Get list of active camera IDs"""
        return list(self.stream_processors.keys())
    
    def get_stream_status(self, camera_id: int) -> Optional[Dict]:
        """Get status of a specific stream"""
        if camera_id in self.stream_processors:
            processor = self.stream_processors[camera_id]
            return {
                "camera_id": camera_id,
                "status": "online",
                "frame_count": processor.frame_count,
                "triggered_tracks": len(processor.triggered_tracks)
            }
        return None
