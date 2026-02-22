"""
ALPR Pipeline - Core Computer Vision Processing
Integrates YOLO detection, cropping, and OCR for Thai license plates
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from ultralytics import YOLO
import easyocr
import torch
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class ALPRPipeline:
    """Main ALPR processing pipeline"""
    
    def __init__(self, model_path: str = "models/best.pt"):
        """
        Initialize ALPR pipeline
        
        Args:
            model_path: Path to custom YOLO model for Thai license plates
                       Supports both .pt (PyTorch) and .engine (TensorRT) formats
        """
        self.model_path = model_path
        self.yolo_model = None
        self.ocr_reader = None
        self._load_models()
    
    def _load_models(self):
        """Load YOLO and OCR models"""
        try:
            # Auto-detect TensorRT engine if available
            model_path = Path(self.model_path)
            engine_path = model_path.with_suffix('.engine')
            
            # Prefer TensorRT engine for faster inference
            if engine_path.exists():
                logger.info(f"⚡ Found TensorRT engine: {engine_path}")
                logger.info("Using TensorRT for accelerated inference")
                self.yolo_model = YOLO(str(engine_path))
                self.model_type = "TensorRT"
            elif model_path.exists():
                logger.info(f"Loading YOLO PyTorch model from {model_path}")
                logger.info("💡 Tip: Convert to TensorRT for 2-5x faster inference:")
                logger.info("   python tools/convert_to_tensorrt.py --model models/best.pt")
                self.yolo_model = YOLO(str(model_path))
                self.model_type = "PyTorch"
            else:
                raise FileNotFoundError(
                    f"Model not found: {model_path}\n"
                    f"Also checked: {engine_path}\n"
                    f"Please ensure your YOLO model exists at the specified path."
                )
            
            # Set device (GPU if available)
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            logger.info(f"Using device: {device}")
            
            # Load EasyOCR (best for Thai)
            logger.info("Loading EasyOCR for Thai language...")
            self.ocr_reader = easyocr.Reader(
                ['th', 'en'],  # Thai and English
                gpu=torch.cuda.is_available(),
                model_storage_directory='models/easyocr',
                download_enabled=True
            )
            
            logger.info("✅ Models loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to load models: {e}")
            raise
    
    def detect_and_crop(
        self,
        image_path: str,
        confidence_threshold: float = 0.25,
        save_crops: bool = True
    ) -> Dict:
        """
        Detect license plates using YOLO and crop them
        
        Args:
            image_path: Path to input image
            confidence_threshold: Minimum confidence for detection
            save_crops: Whether to save cropped plates
        
        Returns:
            Dict containing detection results and cropped plate paths
        """
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Failed to read image: {image_path}")
            
            # Run YOLO detection
            results = self.yolo_model.predict(
                source=image,
                conf=confidence_threshold,
                verbose=False
            )
            
            cropped_plates = []
            
            # Process detections
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    # Get bounding box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0])
                    
                    # Convert to integers
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    
                    # Add padding to crop (10% on each side)
                    padding_x = int((x2 - x1) * 0.1)
                    padding_y = int((y2 - y1) * 0.1)
                    
                    # Apply padding with bounds checking
                    x1 = max(0, x1 - padding_x)
                    y1 = max(0, y1 - padding_y)
                    x2 = min(image.shape[1], x2 + padding_x)
                    y2 = min(image.shape[0], y2 + padding_y)
                    
                    # Crop the plate
                    cropped_plate = image[y1:y2, x1:x2]
                    
                    # Save cropped plate
                    crop_path = None
                    if save_crops:
                        crop_dir = Path("storage/cropped_plates")
                        crop_dir.mkdir(parents=True, exist_ok=True)
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        crop_filename = f"plate_{timestamp}.jpg"
                        crop_path = crop_dir / crop_filename
                        
                        cv2.imwrite(str(crop_path), cropped_plate)
                    
                    cropped_plates.append({
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                        "confidence": confidence,
                        "cropped_path": str(crop_path) if crop_path else None,
                        "width": x2 - x1,
                        "height": y2 - y1
                    })
            
            return {
                "success": True,
                "num_detections": len(cropped_plates),
                "cropped_plates": cropped_plates,
                "original_image_shape": image.shape
            }
            
        except Exception as e:
            logger.error(f"❌ Detection failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "cropped_plates": []
            }
    
    def perform_ocr(
        self,
        cropped_plate_path: str,
        preprocess: bool = True
    ) -> Dict:
        """
        Perform OCR on cropped license plate image
        
        Args:
            cropped_plate_path: Path to cropped plate image
            preprocess: Whether to preprocess image before OCR
        
        Returns:
            Dict containing OCR results (plate number, province, confidence)
        """
        try:
            # Read image
            image = cv2.imread(cropped_plate_path)
            if image is None:
                raise ValueError(f"Failed to read image: {cropped_plate_path}")
            
            # Preprocess if requested
            if preprocess:
                image = self._preprocess_plate_image(image)
            
            # Perform OCR
            ocr_results = self.ocr_reader.readtext(image)
            
            # Combine all detected text
            full_text = " ".join([text[1] for text in ocr_results])
            
            # Calculate average confidence
            avg_confidence = np.mean([text[2] for text in ocr_results]) if ocr_results else 0.0
            
            # Parse Thai license plate format
            parsed = self._parse_thai_plate(full_text)
            
            return {
                "success": True,
                "full_text": full_text,
                "plate_number": parsed["plate_number"],
                "province_code": parsed["province_code"],
                "confidence": float(avg_confidence),
                "raw_ocr_results": ocr_results
            }
            
        except Exception as e:
            logger.error(f"❌ OCR failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "full_text": "",
                "plate_number": "",
                "province_code": None,
                "confidence": 0.0
            }
    
    def _preprocess_plate_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess license plate image for better OCR accuracy
        
        Applies:
        - Grayscale conversion
        - Gaussian blur
        - Adaptive thresholding
        - Morphological operations
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while preserving edges
        denoised = cv2.bilateralFilter(gray, 11, 17, 17)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )
        
        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Convert back to BGR for EasyOCR
        processed = cv2.cvtColor(morph, cv2.COLOR_GRAY2BGR)
        
        return processed
    
    def _parse_thai_plate(self, text: str) -> Dict:
        """
        Parse Thai license plate text into components
        
        Thai plate formats:
        - Private: [กก-กฮ][0-9]{1,4} + จังหวัด (e.g., "กก1234 กรุงเทพมหานคร")
        - Taxi: [กท][0-9]{4} (yellow plates)
        - Motorcycle: [1-9][กก-กฮ][0-9]{1,4}
        
        Args:
            text: Raw OCR text
        
        Returns:
            Dict with plate_number and province_code
        """
        # Clean text
        text = text.strip().replace(" ", "")
        
        # Common Thai characters in plates
        thai_chars = "กขคฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"
        
        # Try to extract plate number pattern
        plate_number = ""
        province_code = None
        
        # Pattern 1: Two Thai chars + digits (e.g., กก1234)
        pattern1 = re.search(f"([{thai_chars}]{{2}})([0-9]{{1,4}})", text)
        if pattern1:
            plate_number = pattern1.group(1) + pattern1.group(2)
        
        # Pattern 2: Motorcycle format (digit + Thai chars + digits)
        pattern2 = re.search(f"([0-9])([{thai_chars}]{{2}})([0-9]{{1,4}})", text)
        if pattern2 and not plate_number:
            plate_number = pattern2.group(1) + pattern2.group(2) + pattern2.group(3)
        
        # Try to extract province name if present
        provinces_map = {
            "กรุงเทพมหานคร": "10",
            "กรุงเทพ": "10",
            "เชียงใหม่": "50",
            "ขอนแก่น": "40",
            "นครราชสีมา": "30",
            "สงขลา": "90",
            # Keep this small and rely on ValidationService fuzzy name matching as primary
        }
        
        for province_name, code in provinces_map.items():
            if province_name in text:
                province_code = code
                break
        
        return {
            "plate_number": plate_number or text,  # Fallback to full text
            "province_code": province_code
        }
    
    def process_with_trigger_line(
        self,
        frame: np.ndarray,
        trigger_line: List[Tuple[int, int]],
        tracking_id: str,
        previous_positions: List[Tuple[int, int]]
    ) -> Optional[Dict]:
        """
        Process frame with virtual trigger line for streaming mode
        
        Only captures when vehicle crosses the trigger line
        
        Args:
            frame: Video frame (numpy array)
            trigger_line: List of two points [(x1,y1), (x2,y2)] defining the line
            tracking_id: Vehicle tracking ID from ByteTrack/DeepSORT
            previous_positions: Previous centroid positions of this vehicle
        
        Returns:
            Detection result if trigger crossed, None otherwise
        """
        # Run detection on frame
        results = self.yolo_model.predict(
            source=frame,
            conf=0.4,
            verbose=False
        )
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                # Get centroid
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                centroid_x = int((x1 + x2) / 2)
                centroid_y = int((y1 + y2) / 2)
                
                # Check if crossed trigger line
                if self._check_line_crossing(
                    trigger_line,
                    previous_positions,
                    (centroid_x, centroid_y)
                ):
                    # Vehicle crossed the line - capture this frame
                    logger.info(f"✅ Trigger activated for tracking ID: {tracking_id}")
                    
                    # Crop the plate
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    cropped_plate = frame[y1:y2, x1:x2]
                    
                    # Save crop
                    crop_dir = Path("storage/cropped_plates")
                    crop_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    crop_path = crop_dir / f"stream_{tracking_id}_{timestamp}.jpg"
                    cv2.imwrite(str(crop_path), cropped_plate)
                    
                    return {
                        "triggered": True,
                        "cropped_path": str(crop_path),
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                        "confidence": float(box.conf[0]),
                        "centroid": (centroid_x, centroid_y)
                    }
        
        return None
    
    def _check_line_crossing(
        self,
        line: List[Tuple[int, int]],
        previous_positions: List[Tuple[int, int]],
        current_position: Tuple[int, int]
    ) -> bool:
        """
        Check if object crossed the trigger line
        
        Uses line intersection algorithm
        """
        if not previous_positions:
            return False
        
        prev_pos = previous_positions[-1]
        
        # Check if movement line intersects trigger line
        return self._line_intersection(
            line[0], line[1],
            prev_pos, current_position
        )
    
    def _line_intersection(
        self,
        p1: Tuple[int, int],
        p2: Tuple[int, int],
        p3: Tuple[int, int],
        p4: Tuple[int, int]
    ) -> bool:
        """Check if two line segments intersect"""
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
        
        return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)