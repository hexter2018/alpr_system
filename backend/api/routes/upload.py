"""
Upload API Routes - Handle Image Upload & Processing
Supports single image, batch upload, and processing orchestration
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid
import shutil
from pathlib import Path
import logging
import math

from database.connection import get_db
from database.models import PlateRecord, ProcessingModeEnum, RecordStatusEnum
from services.alpr_pipeline import ALPRPipeline
from services.validation_service import ValidationService

logger = logging.getLogger(__name__)
router = APIRouter()


def _safe_float(value: Optional[float], default: float = 0.0) -> float:
    """Convert values to finite float to avoid JSON serialization errors."""
    if value is None:
        return default

    numeric = float(value)
    return numeric if math.isfinite(numeric) else default

# Initialize services
alpr_pipeline = ALPRPipeline()
validation_service = ValidationService()

# ==================== PYDANTIC MODELS ====================

class ProcessingResult(BaseModel):
    """Response model for processing results"""
    record_id: int
    plate_number: str
    province_code: Optional[str]
    province_name: Optional[str]
    confidence: float
    is_registered: bool
    status: str
    cropped_image_url: str
    original_image_url: str
    processing_time_ms: int


class BatchProcessingResponse(BaseModel):
    """Response for batch processing"""
    total_images: int
    successful: int
    failed: int
    results: List[ProcessingResult]


# ==================== HELPER FUNCTIONS ====================

async def save_uploaded_file(upload_file: UploadFile, folder: str) -> Path:
    """Save uploaded file to storage"""
    # Generate unique filename
    file_extension = Path(upload_file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = Path(folder) / unique_filename
    
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save file
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    
    return file_path


async def process_single_image(
    image_path: Path,
    db: Session,
    processing_mode: ProcessingModeEnum,
    original_filename: str
) -> ProcessingResult:
    """Process a single image through ALPR pipeline"""
    start_time = datetime.now()
    
    try:
        # Step 1: YOLO Detection & Crop
        logger.info(f"Processing image: {image_path}")
        detection_result = alpr_pipeline.detect_and_crop(str(image_path))
        
        if not detection_result or not detection_result.get("cropped_plates"):
            raise HTTPException(
                status_code=422,
                detail="No license plate detected in image"
            )
        
        # Get the best detection (highest confidence)
        best_plate = max(
            detection_result["cropped_plates"],
            key=lambda x: x["confidence"]
        )
        
        cropped_path = Path(best_plate["cropped_path"])
        
        # Step 2: OCR
        ocr_result = alpr_pipeline.perform_ocr(str(cropped_path))
        
        # Step 3: Validate against Master Data
        validation_result = validation_service.validate_plate(
            plate_number=ocr_result["plate_number"],
            province_code=ocr_result["province_code"],
            province_text=ocr_result.get("full_text"),
            db=db
        )

        resolved_province_code = validation_result.get("province_code")
        
        # Step 4: Save to Database
        plate_record = PlateRecord(
            processing_mode=processing_mode,
            record_status=RecordStatusEnum.ALPR,  # Initially ALPR
            
            # OCR Results
            ocr_plate_number=ocr_result["plate_number"],
            ocr_province_code=ocr_result["province_code"],
            ocr_full_text=ocr_result["full_text"],
            ocr_confidence=ocr_result["confidence"],
            
            # Final data (same as OCR initially)
            final_plate_number=ocr_result["plate_number"],
            final_province_code=resolved_province_code,
            province_id=validation_result.get("province_id"),
            
            # Validation
            is_registered=validation_result["is_registered"],
            registered_vehicle_id=validation_result.get("registered_vehicle_id"),
            validation_score=validation_result.get("validation_score"),
            
            # Images
            original_image_path=str(image_path),
            cropped_plate_path=str(cropped_path),
            
            # Detection metadata
            detection_bbox=best_plate["bbox"],
            detection_confidence=best_plate["confidence"],
            
            # Timestamp
            capture_timestamp=datetime.now(),
            processing_timestamp=datetime.now(),
        )
        
        db.add(plate_record)
        db.commit()
        db.refresh(plate_record)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Build response
        result = ProcessingResult(
            record_id=plate_record.id,
            plate_number=plate_record.final_plate_number,
            province_code=plate_record.final_province_code,
            province_name=validation_result.get("province_name"),
            confidence=_safe_float(plate_record.ocr_confidence),
            is_registered=plate_record.is_registered,
            status=plate_record.record_status.value,
            cropped_image_url=f"/storage/cropped_plates/{cropped_path.name}",
            original_image_url=f"/storage/uploads/{image_path.name}",
            processing_time_ms=int(processing_time)
        )
        
        logger.info(f"✅ Successfully processed: {plate_record.final_plate_number}")
        return result
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"❌ Error processing image: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== API ENDPOINTS ====================

@router.post("/single", response_model=ProcessingResult)
async def upload_single_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and process a single image
    
    - Accepts: JPG, PNG, JPEG formats
    - Returns: OCR results, cropped plate image, validation status
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/jpg", "image/png"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {allowed_types}"
        )
    
    # Save uploaded file
    image_path = await save_uploaded_file(file, "storage/uploads")
    
    # Process image
    result = await process_single_image(
        image_path=image_path,
        db=db,
        processing_mode=ProcessingModeEnum.IMAGE_SINGLE,
        original_filename=file.filename
    )
    
    return result


@router.post("/batch", response_model=BatchProcessingResponse)
async def upload_batch_images(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Upload and process multiple images in batch
    
    - Accepts: Multiple JPG, PNG, JPEG files
    - Maximum: 50 images per batch
    - Returns: Array of processing results
    """
    # Validate batch size
    if len(files) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 images per batch"
        )
    
    results = []
    successful = 0
    failed = 0
    
    for file in files:
        try:
            # Validate file type
            allowed_types = {"image/jpeg", "image/jpg", "image/png"}
            if file.content_type not in allowed_types:
                logger.warning(f"Skipping invalid file type: {file.filename}")
                failed += 1
                continue
            
            # Save and process
            image_path = await save_uploaded_file(file, "storage/uploads")
            result = await process_single_image(
                image_path=image_path,
                db=db,
                processing_mode=ProcessingModeEnum.IMAGE_BATCH,
                original_filename=file.filename
            )
            
            results.append(result)
            successful += 1
            
        except Exception as e:
            logger.error(f"Failed to process {file.filename}: {e}")
            failed += 1
    
    return BatchProcessingResponse(
        total_images=len(files),
        successful=successful,
        failed=failed,
        results=results
    )


@router.get("/status/{record_id}")
async def get_processing_status(
    record_id: int,
    db: Session = Depends(get_db)
):
    """Get processing status of a specific record"""
    record = db.query(PlateRecord).filter(PlateRecord.id == record_id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    return {
        "record_id": record.id,
        "status": record.record_status.value,
        "plate_number": record.final_plate_number,
        "confidence": record.ocr_confidence,
        "processing_timestamp": record.processing_timestamp.isoformat()
    }


@router.delete("/{record_id}")
async def delete_record(
    record_id: int,
    db: Session = Depends(get_db)
):
    """Delete a processing record and associated images"""
    record = db.query(PlateRecord).filter(PlateRecord.id == record_id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    # Delete image files
    try:
        if record.original_image_path:
            Path(record.original_image_path).unlink(missing_ok=True)
        if record.cropped_plate_path:
            Path(record.cropped_plate_path).unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Failed to delete image files: {e}")
    
    # Delete database record
    db.delete(record)
    db.commit()
    
    return {"success": True, "message": "Record deleted successfully"}
