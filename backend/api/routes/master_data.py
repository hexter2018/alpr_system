"""
Master Data API Routes - Manage Provinces and Registered Vehicles
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from database.connection import get_db
from database.models import Province, RegisteredVehicle, PlateTypeEnum

router = APIRouter()

# Pydantic models
class ProvinceResponse(BaseModel):
    id: int
    code: str
    name_th: str
    name_en: str
    region: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True

class RegisteredVehicleResponse(BaseModel):
    id: int
    plate_number: str
    province_id: int
    plate_type: str
    vehicle_model: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True

# API Endpoints
@router.get("/provinces", response_model=List[ProvinceResponse])
async def get_provinces(
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """Get list of all Thai provinces"""
    query = db.query(Province)
    if is_active is not None:
        query = query.filter(Province.is_active == is_active)
    return query.all()

@router.get("/vehicles", response_model=List[RegisteredVehicleResponse])
async def get_registered_vehicles(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get list of registered vehicles"""
    vehicles = db.query(RegisteredVehicle).filter(
        RegisteredVehicle.is_active == True
    ).offset(offset).limit(limit).all()
    return vehicles

@router.get("/vehicles/search")
async def search_vehicles(
    plate_number: str,
    db: Session = Depends(get_db)
):
    """Search for a specific vehicle"""
    vehicle = db.query(RegisteredVehicle).filter(
        RegisteredVehicle.plate_number == plate_number,
        RegisteredVehicle.is_active == True
    ).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    return RegisteredVehicleResponse.from_orm(vehicle)
