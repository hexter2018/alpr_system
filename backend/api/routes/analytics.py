"""
Analytics API Routes - Dashboard Statistics and Reports
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Optional
import math

from database.connection import get_db
from database.models import PlateRecord, RecordStatusEnum, ProcessingModeEnum

router = APIRouter()


def _safe_float(value: Optional[float], default: float = 0.0) -> float:
    """Convert DB numeric values to finite floats safe for JSON serialization."""
    if value is None:
        return default

    numeric = float(value)
    return numeric if math.isfinite(numeric) else default

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    db: Session = Depends(get_db)
):
    """Get summary statistics for dashboard"""
    # Total records
    total = db.query(PlateRecord).count()
    
    # Status breakdown
    alpr = db.query(PlateRecord).filter(PlateRecord.record_status == RecordStatusEnum.ALPR).count()
    mlpr = db.query(PlateRecord).filter(PlateRecord.record_status == RecordStatusEnum.MLPR).count()
    pending = db.query(PlateRecord).filter(PlateRecord.record_status == RecordStatusEnum.PENDING).count()
    
    # Today's statistics
    today = datetime.now().date()
    today_records = db.query(PlateRecord).filter(
        func.date(PlateRecord.capture_timestamp) == today
    ).count()
    
    # Accuracy rate
    accuracy = (alpr / total * 100) if total > 0 else 0
    
    # Average confidence
    avg_confidence = _safe_float(
        db.query(func.avg(PlateRecord.ocr_confidence)).scalar(),
        default=0.0
    )
    
    return {
        "total_records": total,
        "today_records": today_records,
        "alpr_count": alpr,
        "mlpr_count": mlpr,
        "pending_count": pending,
        "accuracy_rate": round(accuracy, 2),
        "avg_confidence": round(avg_confidence, 2),
        "registered_rate": round(
            (db.query(PlateRecord).filter(PlateRecord.is_registered == True).count() / total * 100) 
            if total > 0 else 0, 2
        )
    }

@router.get("/dashboard/daily-trend")
async def get_daily_trend(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """Get daily processing trend"""
    start_date = datetime.now() - timedelta(days=days)
    
    # Query daily counts
    results = db.query(
        func.date(PlateRecord.capture_timestamp).label('date'),
        func.count(PlateRecord.id).label('total'),
        func.count(func.nullif(PlateRecord.record_status == RecordStatusEnum.ALPR, False)).label('alpr'),
        func.count(func.nullif(PlateRecord.record_status == RecordStatusEnum.MLPR, False)).label('mlpr')
    ).filter(
        PlateRecord.capture_timestamp >= start_date
    ).group_by(
        func.date(PlateRecord.capture_timestamp)
    ).all()
    
    return {
        "dates": [str(r.date) for r in results],
        "total": [r.total for r in results],
        "alpr": [r.alpr for r in results],
        "mlpr": [r.mlpr for r in results]
    }

@router.get("/dashboard/top-provinces")
async def get_top_provinces(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Get top provinces by plate count"""
    from database.models import Province
    
    results = db.query(
        Province.name_th,
        Province.code,
        func.count(PlateRecord.id).label('count')
    ).join(
        PlateRecord, PlateRecord.province_id == Province.id
    ).group_by(
        Province.id
    ).order_by(
        func.count(PlateRecord.id).desc()
    ).limit(limit).all()
    
    return [
        {"province": r.name_th, "code": r.code, "count": r.count}
        for r in results
    ]
