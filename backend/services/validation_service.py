"""
Validation Service - Master Data Validation
Checks OCR results against registered vehicles and provinces
Implements fuzzy matching for improved accuracy
"""

from sqlalchemy.orm import Session
from typing import Dict, Optional
import logging
from fuzzywuzzy import fuzz
from database.models import Province, RegisteredVehicle, PlatePrefix

logger = logging.getLogger(__name__)

class ValidationService:
    """Validates OCR results against master data"""
    
    def __init__(self, fuzzy_threshold: int = 85):
        """
        Initialize validation service
        
        Args:
            fuzzy_threshold: Minimum similarity score for fuzzy matching (0-100)
        """
        self.fuzzy_threshold = fuzzy_threshold
    
    def validate_plate(
        self,
        plate_number: str,
        province_code: Optional[str],
        db: Session
    ) -> Dict:
        """
        Validate license plate against master data
        
        Steps:
        1. Validate province code exists
        2. Check if plate is in registered_vehicles (exact match)
        3. If not found, try fuzzy matching
        4. Validate plate prefix format
        
        Args:
            plate_number: License plate number (e.g., "กก1234")
            province_code: Province code (e.g., "กท")
            db: Database session
        
        Returns:
            Dict containing validation results
        """
        result = {
            "is_valid_format": False,
            "is_registered": False,
            "province_id": None,
            "province_name": None,
            "registered_vehicle_id": None,
            "validation_score": 0.0,
            "fuzzy_matches": []
        }
        
        # Step 1: Validate province code
        if province_code:
            province = db.query(Province).filter(
                Province.code == province_code,
                Province.is_active == True
            ).first()
            
            if province:
                result["province_id"] = province.id
                result["province_name"] = province.name_th
                logger.info(f"✅ Valid province: {province.name_th} ({province_code})")
            else:
                # Try fuzzy matching on province codes
                fuzzy_province = self._fuzzy_match_province(province_code, db)
                if fuzzy_province:
                    result["province_id"] = fuzzy_province.id
                    result["province_name"] = fuzzy_province.name_th
                    result["validation_score"] = 0.8  # Fuzzy match
                    logger.info(f"⚠️  Fuzzy matched province: {fuzzy_province.name_th}")
                else:
                    logger.warning(f"❌ Invalid province code: {province_code}")
        
        # Step 2: Check if plate exists in registered vehicles (exact match)
        registered = db.query(RegisteredVehicle).filter(
            RegisteredVehicle.plate_number == plate_number,
            RegisteredVehicle.is_active == True
        ).first()
        
        if registered:
            result["is_registered"] = True
            result["registered_vehicle_id"] = registered.id
            result["validation_score"] = 1.0  # Perfect match
            
            # Update province info from registered vehicle if not already set
            if not result["province_id"] and registered.province_id:
                province = db.query(Province).filter(Province.id == registered.province_id).first()
                if province:
                    result["province_id"] = province.id
                    result["province_name"] = province.name_th
            
            logger.info(f"✅ Plate registered: {plate_number}")
        else:
            # Step 3: Try fuzzy matching
            fuzzy_matches = self._fuzzy_match_plate(plate_number, db)
            if fuzzy_matches:
                result["fuzzy_matches"] = fuzzy_matches
                
                # If top match is above threshold, use it
                if fuzzy_matches[0]["score"] >= self.fuzzy_threshold:
                    best_match = fuzzy_matches[0]
                    result["is_registered"] = True
                    result["registered_vehicle_id"] = best_match["vehicle_id"]
                    result["validation_score"] = best_match["score"] / 100.0
                    logger.info(f"⚠️  Fuzzy matched plate: {plate_number} → {best_match['plate_number']}")
        
        # Step 4: Validate prefix format
        if len(plate_number) >= 2:
            prefix = plate_number[:2]
            prefix_valid = db.query(PlatePrefix).filter(
                PlatePrefix.prefix == prefix,
                PlatePrefix.is_active == True
            ).first()
            
            if prefix_valid:
                result["is_valid_format"] = True
                logger.info(f"✅ Valid plate prefix: {prefix}")
        
        return result
    
    def _fuzzy_match_province(
        self,
        province_code: str,
        db: Session,
        top_n: int = 3
    ) -> Optional[Province]:
        """
        Find closest matching province using fuzzy string matching
        
        Args:
            province_code: Province code to match
            db: Database session
            top_n: Number of top matches to consider
        
        Returns:
            Best matching Province or None
        """
        # Get all active provinces
        provinces = db.query(Province).filter(Province.is_active == True).all()
        
        matches = []
        for province in provinces:
            # Calculate similarity scores
            code_score = fuzz.ratio(province_code, province.code)
            name_score = fuzz.partial_ratio(province_code, province.name_th)
            
            # Use the best score
            best_score = max(code_score, name_score)
            
            if best_score >= self.fuzzy_threshold:
                matches.append({
                    "province": province,
                    "score": best_score
                })
        
        # Sort by score
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        # Return best match if any
        if matches:
            return matches[0]["province"]
        
        return None
    
    def _fuzzy_match_plate(
        self,
        plate_number: str,
        db: Session,
        top_n: int = 5
    ) -> list:
        """
        Find similar license plates using fuzzy matching
        
        Useful for catching OCR errors like:
        - กก1234 vs กค1234 (ก vs ค confusion)
        - กก1234 vs กก1Z34 (number vs letter confusion)
        
        Args:
            plate_number: Plate number to match
            db: Database session
            top_n: Return top N matches
        
        Returns:
            List of matching plates with scores
        """
        # Get all registered plates
        # In production, you might want to add LIMIT or use more efficient search
        registered_plates = db.query(RegisteredVehicle).filter(
            RegisteredVehicle.is_active == True
        ).limit(1000).all()  # Limit for performance
        
        matches = []
        for registered in registered_plates:
            # Calculate similarity
            score = fuzz.ratio(plate_number, registered.plate_number)
            
            if score >= 70:  # Lower threshold for fuzzy search
                matches.append({
                    "plate_number": registered.plate_number,
                    "vehicle_id": registered.id,
                    "score": score,
                    "province_id": registered.province_id
                })
        
        # Sort by score and return top N
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:top_n]
    
    def validate_thai_plate_format(self, plate_number: str) -> Dict:
        """
        Validate Thai license plate format without database
        
        Checks for common patterns:
        - Private: 2 Thai letters + 1-4 digits (e.g., กก1234)
        - Taxi: กท + 4 digits (e.g., กท1234)
        - Motorcycle: 1 digit + 2 Thai letters + 1-4 digits (e.g., 1กก123)
        - Government: Special prefixes
        
        Returns:
            Dict with validation result and detected type
        """
        import re
        
        result = {
            "is_valid": False,
            "plate_type": "UNKNOWN",
            "pattern_matched": None
        }
        
        thai_chars = "กขคฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"
        
        # Pattern 1: Standard private vehicle (e.g., กก1234)
        pattern1 = re.match(f"^[{thai_chars}]{{2}}[0-9]{{1,4}}$", plate_number)
        if pattern1:
            result["is_valid"] = True
            result["plate_type"] = "PRIVATE"
            result["pattern_matched"] = "2_thai_letters + digits"
            return result
        
        # Pattern 2: Motorcycle (e.g., 1กก123)
        pattern2 = re.match(f"^[0-9][{thai_chars}]{{2}}[0-9]{{1,4}}$", plate_number)
        if pattern2:
            result["is_valid"] = True
            result["plate_type"] = "MOTORCYCLE"
            result["pattern_matched"] = "digit + 2_thai_letters + digits"
            return result
        
        # Pattern 3: Taxi (กท prefix)
        if plate_number.startswith("กท") and len(plate_number) >= 6:
            result["is_valid"] = True
            result["plate_type"] = "TAXI"
            result["pattern_matched"] = "กท prefix (taxi)"
            return result
        
        return result
    
    def suggest_corrections(
        self,
        plate_number: str,
        db: Session
    ) -> list:
        """
        Suggest possible corrections for a plate number
        
        Useful for the verification UI to show admins potential corrections
        
        Returns:
            List of suggested corrections with confidence scores
        """
        suggestions = []
        
        # Get fuzzy matches
        fuzzy_matches = self._fuzzy_match_plate(plate_number, db, top_n=5)
        
        for match in fuzzy_matches:
            if match["score"] >= 75:  # Only suggest if reasonably similar
                suggestions.append({
                    "suggested_plate": match["plate_number"],
                    "confidence": match["score"] / 100.0,
                    "reason": "Similar registered vehicle found",
                    "vehicle_id": match["vehicle_id"]
                })
        
        # Check for common OCR errors
        common_errors = self._check_common_ocr_errors(plate_number)
        suggestions.extend(common_errors)
        
        # Remove duplicates and sort by confidence
        seen = set()
        unique_suggestions = []
        for sugg in suggestions:
            if sugg["suggested_plate"] not in seen:
                seen.add(sugg["suggested_plate"])
                unique_suggestions.append(sugg)
        
        unique_suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        
        return unique_suggestions[:5]  # Return top 5
    
    def _check_common_ocr_errors(self, plate_number: str) -> list:
        """
        Check for common OCR confusion patterns in Thai
        
        Common confusions:
        - ก (gor gai) vs ค (kor kwai)
        - จ (jor jan) vs ช (chor chang)
        - 0 (zero) vs O (letter O)
        - 1 (one) vs I (letter I)
        """
        suggestions = []
        
        # Define common character confusions
        confusions = {
            'ก': ['ค'],
            'ค': ['ก'],
            'จ': ['ช'],
            'ช': ['จ'],
            'บ': ['ป'],
            'ป': ['บ'],
            '0': ['O', 'o'],
            'O': ['0'],
            '1': ['I', 'l'],
            'I': ['1'],
        }
        
        # Generate variations
        for i, char in enumerate(plate_number):
            if char in confusions:
                for replacement in confusions[char]:
                    corrected = plate_number[:i] + replacement + plate_number[i+1:]
                    suggestions.append({
                        "suggested_plate": corrected,
                        "confidence": 0.7,
                        "reason": f"Common OCR confusion: {char} → {replacement}"
                    })
        
        return suggestions
