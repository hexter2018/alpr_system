"""
Verification API Routes - Handle MLPR Corrections
Admin verification interface for correcting OCR mistakes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from database.connection import get_db
from database.models import (
    PlateRecord, PlateCorrection, RecordStatusEnum,
    ProcessingModeEnum, Province, User
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== PYDANTIC MODELS ====================

class PlateRecordResponse(BaseModel):
    """Response model for plate records"""
    id: int
    plate_number: str
    province_code: Optional[str]
    province_name: Optional[str]
    confidence: float
    status: str
    is_registered: bool
    cropped_image_url: str
    original_image_url: str
    capture_timestamp: datetime
    processing_mode: str
    
    # Show if corrected
    was_corrected: bool
    corrected_plate_number: Optional[str] = None
    corrected_province_code: Optional[str] = None
    correction_timestamp: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CorrectionRequest(BaseModel):
    """Request model for correcting a plate"""
    corrected_plate_number: str
    corrected_province_code: Optional[str] = None
    correction_reason: Optional[str] = None
    user_id: int  # In production, get from JWT token


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = 1
    page_size: int = 20


class FilterParams(BaseModel):
    """Filter parameters for verification list"""
    status: Optional[str] = None  # ALPR, MLPR, PENDING
    processing_mode: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    plate_number: Optional[str] = None
    province_code: Optional[str] = None
    is_registered: Optional[bool] = None
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None


class VerificationListResponse(BaseModel):
    """Response for verification list"""
    total: int
    page: int
    page_size: int
    total_pages: int
    records: List[PlateRecordResponse]


# ==================== HELPER FUNCTIONS ====================

def build_record_response(record: PlateRecord, db: Session) -> PlateRecordResponse:
    """Convert database record to response model"""
    # Get province name
    province_name = None
    if record.province_id:
        province = db.query(Province).filter(Province.id == record.province_id).first()
        province_name = province.name_th if province else None
    
    # Check if was corrected
    was_corrected = record.record_status == RecordStatusEnum.MLPR
    
    return PlateRecordResponse(
        id=record.id,
        plate_number=record.final_plate_number,
        province_code=record.final_province_code,
        province_name=province_name,
        confidence=record.ocr_confidence or 0.0,
        status=record.record_status.value,
        is_registered=record.is_registered or False,
        cropped_image_url=f"/storage/cropped_plates/{Path(record.cropped_plate_path).name}",
        original_image_url=f"/storage/uploads/{Path(record.original_image_path).name}" if record.original_image_path else "",
        capture_timestamp=record.capture_timestamp,
        processing_mode=record.processing_mode.value,
        was_corrected=was_corrected,
        corrected_plate_number=record.corrected_plate_number if was_corrected else None,
        corrected_province_code=record.corrected_province_code if was_corrected else None,
        correction_timestamp=record.correction_timestamp if was_corrected else None
    )


# ==================== API ENDPOINTS ====================

@router.get("/list", response_model=VerificationListResponse)
async def get_verification_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    processing_mode: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    plate_number: Optional[str] = Query(None),
    province_code: Optional[str] = Query(None),
    is_registered: Optional[bool] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of plate records for verification
    
    Supports filtering by:
    - Status (ALPR, MLPR, PENDING)
    - Processing mode
    - Date range
    - Plate number (partial match)
    - Province
    - Registration status
    - Confidence range
    """
    # Build query
    query = db.query(PlateRecord)
    
    # Apply filters
    if status:
        try:
            status_enum = RecordStatusEnum(status)
            query = query.filter(PlateRecord.record_status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    if processing_mode:
        try:
            mode_enum = ProcessingModeEnum(processing_mode)
            query = query.filter(PlateRecord.processing_mode == mode_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid processing mode: {processing_mode}")
    
    if date_from:
        query = query.filter(PlateRecord.capture_timestamp >= date_from)
    
    if date_to:
        query = query.filter(PlateRecord.capture_timestamp <= date_to)
    
    if plate_number:
        # Partial match on plate number
        query = query.filter(
            or_(
                PlateRecord.final_plate_number.ilike(f"%{plate_number}%"),
                PlateRecord.ocr_plate_number.ilike(f"%{plate_number}%")
            )
        )
    
    if province_code:
        query = query.filter(PlateRecord.final_province_code == province_code)
    
    if is_registered is not None:
        query = query.filter(PlateRecord.is_registered == is_registered)
    
    if min_confidence is not None:
        query = query.filter(PlateRecord.ocr_confidence >= min_confidence)
    
    if max_confidence is not None:
        query = query.filter(PlateRecord.ocr_confidence <= max_confidence)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    records = query.order_by(desc(PlateRecord.capture_timestamp)).offset(offset).limit(page_size).all()
    
    # Build response
    from pathlib import Path
    record_responses = [build_record_response(record, db) for record in records]
    
    total_pages = (total + page_size - 1) // page_size
    
    return VerificationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        records=record_responses
    )


@router.get("/{record_id}", response_model=PlateRecordResponse)
async def get_record_detail(
    record_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific record"""
    record = db.query(PlateRecord).filter(PlateRecord.id == record_id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    from pathlib import Path
    return build_record_response(record, db)


@router.post("/{record_id}/correct")
async def correct_plate(
    record_id: int,
    correction: CorrectionRequest,
    db: Session = Depends(get_db)
):
    """
    Correct OCR result - Changes status to MLPR
    
    This endpoint is called when an admin edits the plate number/province.
    The correction is logged for continuous learning.
    """
    # Get record
    record = db.query(PlateRecord).filter(PlateRecord.id == record_id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    # Store original values for audit trail
    original_plate = record.final_plate_number
    original_province = record.final_province_code
    
    # Create correction log entry
    correction_log = PlateCorrection(
        plate_record_id=record_id,
        before_plate_number=original_plate,
        before_province_code=original_province,
        after_plate_number=correction.corrected_plate_number,
        after_province_code=correction.corrected_province_code,
        correction_type="both" if correction.corrected_province_code else "plate_number",
        corrected_by_user_id=correction.user_id,
        correction_timestamp=datetime.now(),
        correction_reason=correction.correction_reason,
        used_for_training=False  # Will be flagged later for retraining
    )
    
    # Update record
    record.corrected_plate_number = correction.corrected_plate_number
    record.corrected_province_code = correction.corrected_province_code
    record.correction_timestamp = datetime.now()
    record.corrected_by_user_id = correction.user_id
    record.record_status = RecordStatusEnum.MLPR  # Change to Manual
    
    # Update final values (trigger will handle this, but set explicitly)
    record.final_plate_number = correction.corrected_plate_number
    record.final_province_code = correction.corrected_province_code
    
    # Re-validate against master data with corrected values
    from services.validation_service import ValidationService
    validation_service = ValidationService()
    validation_result = validation_service.validate_plate(
        plate_number=correction.corrected_plate_number,
        province_code=correction.corrected_province_code,
        db=db
    )
    
    record.is_registered = validation_result["is_registered"]
    record.registered_vehicle_id = validation_result.get("registered_vehicle_id")
    record.province_id = validation_result.get("province_id")
    
    # Save both records
    db.add(correction_log)
    db.commit()
    db.refresh(record)
    
    logger.info(f"✅ Record {record_id} corrected: {original_plate} → {correction.corrected_plate_number}")
    
    from pathlib import Path
    return {
        "success": True,
        "message": "Correction saved successfully",
        "record": build_record_response(record, db)
    }


@router.get("/corrections/pending-training")
async def get_corrections_for_training(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get corrections that haven't been used for training yet
    
    This endpoint is used by the continuous learning pipeline
    to fetch corrected data for model retraining.
    """
    corrections = (
        db.query(PlateCorrection)
        .filter(PlateCorrection.used_for_training == False)
        .order_by(PlateCorrection.correction_timestamp)
        .limit(limit)
        .all()
    )
    
    result = []
    for correction in corrections:
        # Get the associated plate record for image paths
        record = db.query(PlateRecord).filter(PlateRecord.id == correction.plate_record_id).first()
        
        result.append({
            "correction_id": correction.id,
            "plate_record_id": correction.plate_record_id,
            "before": {
                "plate_number": correction.before_plate_number,
                "province_code": correction.before_province_code
            },
            "after": {
                "plate_number": correction.after_plate_number,
                "province_code": correction.after_province_code
            },
            "cropped_image_path": record.cropped_plate_path if record else None,
            "correction_timestamp": correction.correction_timestamp.isoformat()
        })
    
    return {
        "total": len(result),
        "corrections": result
    }


@router.post("/corrections/mark-trained")
async def mark_corrections_as_trained(
    correction_ids: List[int],
    training_batch_id: str,
    db: Session = Depends(get_db)
):
    """
    Mark corrections as used for training
    
    Called after a training batch is completed to prevent
    using the same corrections multiple times.
    """
    updated = (
        db.query(PlateCorrection)
        .filter(PlateCorrection.id.in_(correction_ids))
        .update(
            {
                "used_for_training": True,
                "training_batch_id": training_batch_id
            },
            synchronize_session=False
        )
    )
    
    db.commit()
    
    logger.info(f"✅ Marked {updated} corrections as trained (batch: {training_batch_id})")
    
    return {
        "success": True,
        "updated_count": updated,
        "training_batch_id": training_batch_id
    }


@router.get("/stats/summary")
async def get_verification_stats(
    db: Session = Depends(get_db)
):
    """Get summary statistics for the verification dashboard"""
    total_records = db.query(PlateRecord).count()
    alpr_count = db.query(PlateRecord).filter(PlateRecord.record_status == RecordStatusEnum.ALPR).count()
    mlpr_count = db.query(PlateRecord).filter(PlateRecord.record_status == RecordStatusEnum.MLPR).count()
    pending_count = db.query(PlateRecord).filter(PlateRecord.record_status == RecordStatusEnum.PENDING).count()
    
    accuracy_rate = (alpr_count / total_records * 100) if total_records > 0 else 0
    
    return {
        "total_records": total_records,
        "alpr_count": alpr_count,
        "mlpr_count": mlpr_count,
        "pending_count": pending_count,
        "accuracy_rate": round(accuracy_rate, 2),
        "correction_rate": round((mlpr_count / total_records * 100) if total_records > 0 else 0, 2)
    }
