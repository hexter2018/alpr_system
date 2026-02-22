"""
SQLAlchemy Database Models for Thai ALPR System
Enterprise-grade schema with audit trails, versioning, and master data support
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, 
    Text, Enum, ForeignKey, Index, JSON, DECIMAL
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime

Base = declarative_base()


# ==================== ENUMS ====================
class RecordStatusEnum(str, enum.Enum):
    """Status of plate reading"""
    ALPR = "ALPR"  # Automatic License Plate Recognition (unmodified)
    MLPR = "MLPR"  # Manual License Plate Recognition (human-corrected)
    PENDING = "PENDING"  # Awaiting verification
    REJECTED = "REJECTED"  # Invalid/rejected record


class ProcessingModeEnum(str, enum.Enum):
    """How the plate was captured"""
    IMAGE_SINGLE = "IMAGE_SINGLE"
    IMAGE_BATCH = "IMAGE_BATCH"
    STREAM_RTSP = "STREAM_RTSP"


class PlateTypeEnum(str, enum.Enum):
    """Thai license plate types"""
    PRIVATE = "PRIVATE"  # รถยนต์ส่วนบุคคล (ขาว-ดำ)
    COMMERCIAL = "COMMERCIAL"  # รถบรรทุก (ขาว-ดำ)
    TAXI = "TAXI"  # แท็กซี่ (เหลือง-ดำ)
    MOTORCYCLE = "MOTORCYCLE"  # รถจักรยานยนต์ (ขาว-ดำ)
    GOVERNMENT = "GOVERNMENT"  # ราชการ (ขาว-แดง)
    TEMPORARY = "TEMPORARY"  # ชั่วคราว (แดง-ขาว)
    DIPLOMATIC = "DIPLOMATIC"  # ทูต (ขาว-น้ำเงิน)
    UNKNOWN = "UNKNOWN"


# ==================== MASTER DATA TABLES ====================

class Province(Base):
    """Thai provinces master data - จังหวัดทั้งหมดในประเทศไทย"""
    __tablename__ = "provinces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), unique=True, nullable=False, index=True)  # e.g., "กท", "ชม"
    name_th = Column(String(100), nullable=False)  # กรุงเทพมหานคร
    name_en = Column(String(100), nullable=False)  # Bangkok
    region = Column(String(50))  # Central, North, Northeast, South
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    plates = relationship("PlateRecord", back_populates="province")

    __table_args__ = (
        Index('idx_province_code', 'code'),
        Index('idx_province_name_th', 'name_th'),
    )


class PlatePrefix(Base):
    """Thai license plate prefix patterns - หมวดอักษร"""
    __tablename__ = "plate_prefixes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prefix = Column(String(10), unique=True, nullable=False, index=True)  # กก, นค, etc.
    plate_type = Column(Enum(PlateTypeEnum), nullable=False)
    description = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_prefix_type', 'prefix', 'plate_type'),
    )


class RegisteredVehicle(Base):
    """Master data of registered vehicles for validation"""
    __tablename__ = "registered_vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate_number = Column(String(50), unique=True, nullable=False, index=True)
    province_id = Column(Integer, ForeignKey('provinces.id'), nullable=False)
    plate_type = Column(Enum(PlateTypeEnum), nullable=False)
    owner_name = Column(String(200))  # Encrypted in production
    vehicle_model = Column(String(100))
    vehicle_color = Column(String(50))
    registration_date = Column(DateTime(timezone=True))
    expiry_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    extra_data = Column("metadata", JSON)  # Additional flexible data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    province = relationship("Province")

    __table_args__ = (
        Index('idx_vehicle_plate', 'plate_number'),
        Index('idx_vehicle_active', 'is_active', 'plate_number'),
    )


# ==================== CORE ALPR TABLES ====================

class PlateRecord(Base):
    """Main table storing all license plate detection records"""
    __tablename__ = "plate_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Processing metadata
    processing_mode = Column(Enum(ProcessingModeEnum), nullable=False)
    record_status = Column(Enum(RecordStatusEnum), default=RecordStatusEnum.PENDING, nullable=False, index=True)
    
    # OCR Results (Original - before any editing)
    ocr_plate_number = Column(String(50), nullable=False, index=True)  # e.g., "กก1234"
    ocr_province_code = Column(String(10), index=True)  # e.g., "กท"
    ocr_full_text = Column(String(100))  # Complete raw OCR output
    ocr_confidence = Column(Float)  # 0.0 to 1.0
    
    # Human-Corrected Results (if status = MLPR)
    corrected_plate_number = Column(String(50), index=True)
    corrected_province_code = Column(String(10))
    correction_timestamp = Column(DateTime(timezone=True))
    corrected_by_user_id = Column(Integer, ForeignKey('users.id'))
    
    # Final validated data
    final_plate_number = Column(String(50), nullable=False, index=True)  # Used for queries
    final_province_code = Column(String(10))
    province_id = Column(Integer, ForeignKey('provinces.id'))
    plate_type = Column(Enum(PlateTypeEnum), default=PlateTypeEnum.UNKNOWN)
    
    # Master data validation
    is_registered = Column(Boolean, default=False, index=True)  # Exists in registered_vehicles
    registered_vehicle_id = Column(Integer, ForeignKey('registered_vehicles.id'))
    validation_score = Column(Float)  # Fuzzy matching score if used
    
    # Image paths
    original_image_path = Column(String(500))  # Full frame/uploaded image
    cropped_plate_path = Column(String(500), nullable=False)  # Cropped license plate
    
    # Detection metadata
    detection_bbox = Column(JSON)  # {"x": 100, "y": 200, "width": 300, "height": 100}
    detection_confidence = Column(Float)  # YOLO confidence
    
    # Streaming-specific fields
    camera_id = Column(Integer, ForeignKey('cameras.id'))
    frame_number = Column(Integer)  # Frame index in stream
    trigger_line_position = Column(JSON)  # Where the trigger happened
    tracking_id = Column(String(50))  # ByteTrack/DeepSORT ID
    
    # Timestamps
    capture_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    processing_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Audit & metadata
    extra_data = Column("metadata", JSON)  # Flexible field for additional data
    notes = Column(Text)  # Human notes
    
    # Relationships
    province = relationship("Province", back_populates="plates")
    registered_vehicle = relationship("RegisteredVehicle")
    corrected_by = relationship("User", foreign_keys=[corrected_by_user_id])
    camera = relationship("Camera")
    corrections = relationship("PlateCorrection", back_populates="plate_record")

    __table_args__ = (
        Index('idx_record_status', 'record_status'),
        Index('idx_final_plate', 'final_plate_number'),
        Index('idx_capture_time', 'capture_timestamp'),
        Index('idx_camera_time', 'camera_id', 'capture_timestamp'),
        Index('idx_registered', 'is_registered'),
        Index('idx_processing_mode', 'processing_mode'),
    )


class PlateCorrection(Base):
    """Audit trail for all corrections - for continuous learning"""
    __tablename__ = "plate_corrections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate_record_id = Column(Integer, ForeignKey('plate_records.id'), nullable=False, index=True)
    
    # Before correction
    before_plate_number = Column(String(50))
    before_province_code = Column(String(10))
    
    # After correction
    after_plate_number = Column(String(50))
    after_province_code = Column(String(10))
    
    # Correction metadata
    correction_type = Column(String(50))  # "plate_number", "province", "both"
    corrected_by_user_id = Column(Integer, ForeignKey('users.id'))
    correction_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    correction_reason = Column(Text)  # Why was it corrected?
    
    # Used for retraining flag
    used_for_training = Column(Boolean, default=False, index=True)
    training_batch_id = Column(String(100))  # Reference to training job
    
    # Relationships
    plate_record = relationship("PlateRecord", back_populates="corrections")
    corrected_by = relationship("User")

    __table_args__ = (
        Index('idx_correction_record', 'plate_record_id'),
        Index('idx_training_flag', 'used_for_training'),
    )


# ==================== STREAMING & CAMERA MANAGEMENT ====================

class Camera(Base):
    """RTSP camera configuration"""
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    rtsp_url = Column(String(500), nullable=False)
    location = Column(String(200))  # Physical location
    
    # Trigger line/ROI configuration
    trigger_config = Column(JSON)  # {"type": "line", "coords": [[x1,y1], [x2,y2]]} or {"type": "roi", "polygon": [...]}
    
    # Processing settings
    is_active = Column(Boolean, default=True, index=True)
    fps_processing = Column(Integer, default=5)  # Process every Nth frame
    skip_frames = Column(Integer, default=3)  # Skip N frames between processing
    
    # Status
    last_heartbeat = Column(DateTime(timezone=True))
    status = Column(String(50), default="offline")  # online, offline, error
    
    # Metadata
    extra_data = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    plate_records = relationship("PlateRecord", back_populates="camera")

    __table_args__ = (
        Index('idx_camera_active', 'is_active'),
    )


# ==================== USER & AUTH ====================

class User(Base):
    """System users for authentication and audit"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    hashed_password = Column(String(500), nullable=False)
    full_name = Column(String(200))
    
    # Role-based access
    role = Column(String(50), default="viewer")  # admin, operator, viewer
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # Timestamps
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_user_active', 'is_active', 'username'),
    )


# ==================== SYSTEM LOGS & ANALYTICS ====================

class ProcessingLog(Base):
    """System processing logs for debugging and analytics"""
    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate_record_id = Column(Integer, ForeignKey('plate_records.id'), index=True)
    
    # Processing steps timing
    step_name = Column(String(100), nullable=False)  # "yolo_detection", "ocr", "validation"
    execution_time_ms = Column(Integer)  # Milliseconds
    status = Column(String(50))  # success, error, warning
    
    # Error tracking
    error_message = Column(Text)
    stack_trace = Column(Text)
    
    # Metadata
    extra_data = Column("metadata", JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index('idx_log_timestamp', 'timestamp'),
        Index('idx_log_status', 'status', 'step_name'),
    )


class SystemMetrics(Base):
    """System performance metrics - aggregated hourly/daily"""
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    time_bucket = Column(String(20), nullable=False)  # "hourly", "daily"
    
    # Plate processing metrics
    total_plates_processed = Column(Integer, default=0)
    total_alpr = Column(Integer, default=0)
    total_mlpr = Column(Integer, default=0)
    total_pending = Column(Integer, default=0)
    
    # Accuracy metrics
    avg_ocr_confidence = Column(Float)
    avg_detection_confidence = Column(Float)
    accuracy_rate = Column(Float)  # ALPR / Total
    
    # Performance metrics
    avg_processing_time_ms = Column(Integer)
    total_errors = Column(Integer, default=0)
    
    # Camera-specific (if aggregated by camera)
    camera_id = Column(Integer, ForeignKey('cameras.id'))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_metrics_time', 'metric_timestamp', 'time_bucket'),
        Index('idx_metrics_camera', 'camera_id', 'metric_timestamp'),
    )
