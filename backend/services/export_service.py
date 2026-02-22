"""
Export Service - Generate Excel and PDF Reports
Supports various report types: daily summary, detailed records, analytics
"""

from typing import List, Optional
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from io import BytesIO

# PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from database.models import PlateRecord, Province, RecordStatusEnum

logger = logging.getLogger(__name__)


class ExportService:
    """Generate Excel and PDF reports"""
    
    def __init__(self):
        self.export_dir = Path("storage/exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_excel_report(
        self,
        db: Session,
        report_type: str = "detailed",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        status_filter: Optional[str] = None
    ) -> str:
        """
        Generate Excel report with multiple sheets
        
        Args:
            db: Database session
            report_type: "detailed", "summary", or "analytics"
            date_from: Start date filter
            date_to: End date filter
            status_filter: ALPR, MLPR, PENDING
        
        Returns:
            Path to generated Excel file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"alpr_report_{report_type}_{timestamp}.xlsx"
        filepath = self.export_dir / filename
        
        # Create Excel writer
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            
            if report_type == "detailed":
                self._write_detailed_sheet(writer, db, date_from, date_to, status_filter)
            
            elif report_type == "summary":
                self._write_summary_sheet(writer, db, date_from, date_to)
            
            elif report_type == "analytics":
                self._write_analytics_sheets(writer, db, date_from, date_to)
        
        logger.info(f"✅ Excel report generated: {filename}")
        return str(filepath)
    
    def _write_detailed_sheet(
        self,
        writer: pd.ExcelWriter,
        db: Session,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        status_filter: Optional[str]
    ):
        """Write detailed records sheet"""
        query = db.query(
            PlateRecord.id,
            PlateRecord.final_plate_number,
            PlateRecord.final_province_code,
            Province.name_th.label('province_name'),
            PlateRecord.ocr_confidence,
            PlateRecord.record_status,
            PlateRecord.is_registered,
            PlateRecord.processing_mode,
            PlateRecord.capture_timestamp,
            PlateRecord.cropped_plate_path
        ).outerjoin(Province, PlateRecord.province_id == Province.id)
        
        # Apply filters
        if date_from:
            query = query.filter(PlateRecord.capture_timestamp >= date_from)
        if date_to:
            query = query.filter(PlateRecord.capture_timestamp <= date_to)
        if status_filter:
            query = query.filter(PlateRecord.record_status == status_filter)
        
        # Execute and convert to DataFrame
        results = query.all()
        
        df = pd.DataFrame([
            {
                'ID': r.id,
                'License Plate': r.final_plate_number,
                'Province Code': r.final_province_code,
                'Province': r.province_name or 'Unknown',
                'Confidence (%)': round(r.ocr_confidence * 100, 2) if r.ocr_confidence else 0,
                'Status': r.record_status.value,
                'Registered': 'Yes' if r.is_registered else 'No',
                'Processing Mode': r.processing_mode.value,
                'Capture Time': r.capture_timestamp,
                'Image Path': r.cropped_plate_path
            }
            for r in results
        ])
        
        # Write to Excel
        df.to_excel(writer, sheet_name='Detailed Records', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Detailed Records']
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(col)
            ) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)
    
    def _write_summary_sheet(
        self,
        writer: pd.ExcelWriter,
        db: Session,
        date_from: Optional[datetime],
        date_to: Optional[datetime]
    ):
        """Write summary statistics sheet"""
        query = db.query(PlateRecord)
        
        if date_from:
            query = query.filter(PlateRecord.capture_timestamp >= date_from)
        if date_to:
            query = query.filter(PlateRecord.capture_timestamp <= date_to)
        
        # Overall statistics
        total = query.count()
        alpr = query.filter(PlateRecord.record_status == RecordStatusEnum.ALPR).count()
        mlpr = query.filter(PlateRecord.record_status == RecordStatusEnum.MLPR).count()
        pending = query.filter(PlateRecord.record_status == RecordStatusEnum.PENDING).count()
        registered = query.filter(PlateRecord.is_registered == True).count()
        
        avg_confidence = db.query(func.avg(PlateRecord.ocr_confidence)).filter(
            PlateRecord.capture_timestamp >= date_from if date_from else True,
            PlateRecord.capture_timestamp <= date_to if date_to else True
        ).scalar() or 0
        
        summary_data = {
            'Metric': [
                'Total Records',
                'ALPR (Automatic)',
                'MLPR (Manual Corrected)',
                'Pending',
                'Registered Vehicles',
                'Accuracy Rate',
                'Average Confidence'
            ],
            'Value': [
                total,
                alpr,
                mlpr,
                pending,
                registered,
                f"{(alpr / total * 100):.2f}%" if total > 0 else "0%",
                f"{(avg_confidence * 100):.2f}%" if avg_confidence else "0%"
            ]
        }
        
        df = pd.DataFrame(summary_data)
        df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Summary']
        worksheet.column_dimensions['A'].width = 30
        worksheet.column_dimensions['B'].width = 20
    
    def _write_analytics_sheets(
        self,
        writer: pd.ExcelWriter,
        db: Session,
        date_from: Optional[datetime],
        date_to: Optional[datetime]
    ):
        """Write multiple analytics sheets"""
        # Daily trend
        daily_data = db.query(
            func.date(PlateRecord.capture_timestamp).label('date'),
            func.count(PlateRecord.id).label('total'),
            func.count(PlateRecord.id).filter(PlateRecord.record_status == RecordStatusEnum.ALPR).label('alpr'),
            func.count(PlateRecord.id).filter(PlateRecord.record_status == RecordStatusEnum.MLPR).label('mlpr')
        ).filter(
            PlateRecord.capture_timestamp >= date_from if date_from else True,
            PlateRecord.capture_timestamp <= date_to if date_to else True
        ).group_by(func.date(PlateRecord.capture_timestamp)).all()
        
        df_daily = pd.DataFrame([
            {
                'Date': str(r.date),
                'Total': r.total,
                'ALPR': r.alpr,
                'MLPR': r.mlpr,
                'Accuracy': f"{(r.alpr / r.total * 100):.2f}%" if r.total > 0 else "0%"
            }
            for r in daily_data
        ])
        
        df_daily.to_excel(writer, sheet_name='Daily Trend', index=False)
        
        # Top provinces
        province_data = db.query(
            Province.name_th,
            Province.code,
            func.count(PlateRecord.id).label('count')
        ).join(PlateRecord, PlateRecord.province_id == Province.id).filter(
            PlateRecord.capture_timestamp >= date_from if date_from else True,
            PlateRecord.capture_timestamp <= date_to if date_to else True
        ).group_by(Province.id).order_by(func.count(PlateRecord.id).desc()).limit(20).all()
        
        df_provinces = pd.DataFrame([
            {
                'Province': r.name_th,
                'Code': r.code,
                'Count': r.count
            }
            for r in province_data
        ])
        
        df_provinces.to_excel(writer, sheet_name='Top Provinces', index=False)
    
    def generate_pdf_report(
        self,
        db: Session,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        include_images: bool = False
    ) -> str:
        """
        Generate PDF report with summary and optional images
        
        Args:
            db: Database session
            date_from: Start date
            date_to: End date
            include_images: Whether to include cropped plate images
        
        Returns:
            Path to generated PDF file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"alpr_report_{timestamp}.pdf"
        filepath = self.export_dir / filename
        
        # Create PDF
        doc = SimpleDocTemplate(str(filepath), pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1890ff'),
            spaceAfter=30
        )
        
        story.append(Paragraph("Thai ALPR System Report", title_style))
        story.append(Spacer(1, 12))
        
        # Date range
        date_range = f"Period: {date_from.strftime('%Y-%m-%d') if date_from else 'All'} to {date_to.strftime('%Y-%m-%d') if date_to else 'Now'}"
        story.append(Paragraph(date_range, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Summary statistics
        query = db.query(PlateRecord)
        if date_from:
            query = query.filter(PlateRecord.capture_timestamp >= date_from)
        if date_to:
            query = query.filter(PlateRecord.capture_timestamp <= date_to)
        
        total = query.count()
        alpr = query.filter(PlateRecord.record_status == RecordStatusEnum.ALPR).count()
        mlpr = query.filter(PlateRecord.record_status == RecordStatusEnum.MLPR).count()
        
        summary_data = [
            ['Metric', 'Value'],
            ['Total Records', str(total)],
            ['ALPR (Automatic)', str(alpr)],
            ['MLPR (Corrected)', str(mlpr)],
            ['Accuracy Rate', f"{(alpr / total * 100):.2f}%" if total > 0 else "0%"]
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Recent records (with images if requested)
        if include_images:
            story.append(Paragraph("Recent Detections", styles['Heading2']))
            story.append(Spacer(1, 12))
            
            recent = query.order_by(PlateRecord.capture_timestamp.desc()).limit(10).all()
            
            for record in recent:
                # Record info
                info_text = f"<b>Plate:</b> {record.final_plate_number} | <b>Confidence:</b> {record.ocr_confidence*100:.1f}% | <b>Status:</b> {record.record_status.value}"
                story.append(Paragraph(info_text, styles['Normal']))
                
                # Image if exists
                if record.cropped_plate_path and Path(record.cropped_plate_path).exists():
                    img = Image(record.cropped_plate_path, width=2*inch, height=1*inch)
                    story.append(img)
                
                story.append(Spacer(1, 12))
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"✅ PDF report generated: {filename}")
        return str(filepath)


# Convenience functions for API endpoints

def export_to_excel(
    db: Session,
    report_type: str = "detailed",
    **kwargs
) -> str:
    """Export data to Excel"""
    service = ExportService()
    return service.generate_excel_report(db, report_type, **kwargs)


def export_to_pdf(
    db: Session,
    include_images: bool = False,
    **kwargs
) -> str:
    """Export data to PDF"""
    service = ExportService()
    return service.generate_pdf_report(db, include_images=include_images, **kwargs)
