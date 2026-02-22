"""
Export API Routes - Generate Excel and PDF Reports
Allows users to export data in various formats
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import logging

from database.connection import get_db
from services.export_service import ExportService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/excel")
async def export_excel(
    report_type: str = Query("detailed", regex="^(detailed|summary|analytics)$"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, regex="^(ALPR|MLPR|PENDING|REJECTED)$"),
    db: Session = Depends(get_db)
):
    """
    Export data to Excel file
    
    Parameters:
    - report_type: "detailed", "summary", or "analytics"
    - date_from: Start date (YYYY-MM-DD)
    - date_to: End date (YYYY-MM-DD)
    - status_filter: Filter by status (ALPR, MLPR, etc.)
    
    Returns:
    - Excel file download
    """
    try:
        # Parse dates
        date_from_dt = datetime.fromisoformat(date_from) if date_from else None
        date_to_dt = datetime.fromisoformat(date_to) if date_to else None
        
        # Generate report
        service = ExportService()
        filepath = service.generate_excel_report(
            db=db,
            report_type=report_type,
            date_from=date_from_dt,
            date_to=date_to_dt,
            status_filter=status_filter
        )
        
        # Return file
        filename = filepath.split('/')[-1]
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except Exception as e:
        logger.error(f"Error generating Excel report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf")
async def export_pdf(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    include_images: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Export data to PDF report
    
    Parameters:
    - date_from: Start date (YYYY-MM-DD)
    - date_to: End date (YYYY-MM-DD)
    - include_images: Whether to include cropped plate images
    
    Returns:
    - PDF file download
    """
    try:
        # Parse dates
        date_from_dt = datetime.fromisoformat(date_from) if date_from else None
        date_to_dt = datetime.fromisoformat(date_to) if date_to else None
        
        # Generate report
        service = ExportService()
        filepath = service.generate_pdf_report(
            db=db,
            date_from=date_from_dt,
            date_to=date_to_dt,
            include_images=include_images
        )
        
        # Return file
        filename = filepath.split('/')[-1]
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='application/pdf'
        )
    
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-summary-excel")
async def export_daily_summary(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Export daily summary for the last N days
    
    Quick export for daily reports
    """
    date_to = datetime.now()
    date_from = date_to - timedelta(days=days)
    
    service = ExportService()
    filepath = service.generate_excel_report(
        db=db,
        report_type="analytics",
        date_from=date_from,
        date_to=date_to
    )
    
    filename = filepath.split('/')[-1]
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@router.get("/formats")
async def get_available_formats():
    """Get list of available export formats and report types"""
    return {
        "formats": [
            {
                "type": "excel",
                "name": "Excel Spreadsheet",
                "extension": ".xlsx",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            },
            {
                "type": "pdf",
                "name": "PDF Report",
                "extension": ".pdf",
                "mime_type": "application/pdf"
            }
        ],
        "report_types": [
            {
                "id": "detailed",
                "name": "Detailed Records",
                "description": "All plate records with full details"
            },
            {
                "id": "summary",
                "name": "Summary Statistics",
                "description": "High-level statistics and metrics"
            },
            {
                "id": "analytics",
                "name": "Analytics Report",
                "description": "Daily trends and province statistics"
            }
        ]
    }
