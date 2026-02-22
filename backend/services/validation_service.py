"""
Validation Service - Master Data Validation with Enhanced Thai Province Matching
Validates OCR results against registered vehicles and provinces
Implements robust fuzzy matching for Thai province names with OCR error tolerance
"""

from sqlalchemy.orm import Session
from typing import Dict, Optional, List, Tuple
import logging
import re

# Use rapidfuzz for better performance (fallback to fuzzywuzzy if not available)
try:
    from rapidfuzz import fuzz, process
    USING_RAPIDFUZZ = True
    logger_lib = "rapidfuzz"
except ImportError:
    from fuzzywuzzy import fuzz, process
    USING_RAPIDFUZZ = False
    logger_lib = "fuzzywuzzy"

from database.models import Province, RegisteredVehicle, PlatePrefix

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"✅ Using {logger_lib} for fuzzy matching")


class ValidationService:
    """
    Validates OCR results against master data
    
    Enhanced Features:
    - Full Thai province name matching (กรุงเทพมหานคร, not just กท)
    - Robust fuzzy matching with OCR error tolerance
    - Multi-strategy matching (code, name_th, name_en)
    - Optimized for Thai character recognition errors
    """
    
    # Fuzzy matching thresholds
    PROVINCE_CODE_THRESHOLD = 85      # For 2-letter codes (strict)
    PROVINCE_NAME_THRESHOLD = 80      # For full province names (tolerant of OCR errors)
    PROVINCE_ENGLISH_THRESHOLD = 85   # For English names
    VEHICLE_PLATE_THRESHOLD = 85      # For vehicle plate matching
    
    def __init__(self):
        """Initialize validation service"""
        logger.info("ValidationService initialized with enhanced Thai province matching")
    
    def validate_plate(
        self,
        plate_number: str,
        province_code: Optional[str] = None,
        province_text: Optional[str] = None,
        db: Session = None
    ) -> Dict:
        """
        Validate license plate against master data with enhanced province matching
        
        Args:
            plate_number: License plate number (e.g., "กก1234")
            province_code: 2-letter province code (e.g., "กท") - OPTIONAL
            province_text: Full OCR text that may contain province name (e.g., "กรุงเทพมหานคร")
            db: Database session
        
        Returns:
            Dict containing validation results with matched province information
        
        Examples:
            # Case 1: Only province code provided
            validate_plate("กก1234", province_code="กท", db=db)
            
            # Case 2: Full OCR text with province name
            validate_plate("กก1234", province_text="กรุงเทพมหานคร", db=db)
            
            # Case 3: Misspelled province name (OCR error)
            validate_plate("กก1234", province_text="กรุงเทพมหานคธ", db=db)  # ร→ธ error
            
            # Case 4: Both provided (prioritizes full text)
            validate_plate("กก1234", province_code="กท", province_text="กรุงเทพมหานคร", db=db)
        """
        result = {
            "is_valid_format": False,
            "is_registered": False,
            "province_id": None,
            "province_name": None,
            "province_code": None,
            "registered_vehicle_id": None,
            "validation_score": 0.0,
            "fuzzy_matches": [],
            "match_method": None  # Track how province was matched
        }
        
        # ==================== PROVINCE VALIDATION ====================
        # Priority: province_text > province_code
        # Reason: Full text provides more information and context
        
        province_match = None
        
        if province_text:
            # Strategy 1: Match against full province name (PRIMARY)
            province_match = self._fuzzy_match_province_by_name(province_text, db)
            
            if province_match:
                result["match_method"] = "province_name_fuzzy"
                result["validation_score"] = province_match["score"] / 100.0
                logger.info(
                    f"✅ Matched province by name: '{province_text}' → {province_match['province'].name_th} "
                    f"(score: {province_match['score']:.1f}%)"
                )
        
        # Fallback to province code if name matching failed or not provided
        if not province_match and province_code:
            province_match = self._fuzzy_match_province_by_code(province_code, db)
            
            if province_match:
                result["match_method"] = "province_code_fuzzy"
                result["validation_score"] = province_match["score"] / 100.0
                logger.info(
                    f"✅ Matched province by code: '{province_code}' → {province_match['province'].code} "
                    f"(score: {province_match['score']:.1f}%)"
                )
        
        # Extract province from full text if no explicit match yet
        if not province_match and province_text:
            # Try to extract province name from text
            extracted_province = self._extract_province_from_text(province_text, db)
            
            if extracted_province:
                province_match = {
                    "province": extracted_province,
                    "score": 100.0  # Exact extraction
                }
                result["match_method"] = "province_name_extracted"
                result["validation_score"] = 1.0
                logger.info(f"✅ Extracted province from text: {extracted_province.name_th}")
        
        # Populate province information if matched
        if province_match:
            province = province_match["province"]
            result["province_id"] = province.id
            result["province_name"] = province.name_th
            result["province_code"] = province.code
            logger.info(f"📍 Province: {province.name_th} ({province.code})")
        else:
            logger.warning(f"⚠️  Could not match province: code='{province_code}', text='{province_text}'")
        
        # ==================== VEHICLE REGISTRATION CHECK ====================
        # Check if plate exists in registered vehicles (exact match)
        
        registered = db.query(RegisteredVehicle).filter(
            RegisteredVehicle.plate_number == plate_number,
            RegisteredVehicle.is_active == True
        ).first()
        
        if registered:
            result["is_registered"] = True
            result["registered_vehicle_id"] = registered.id
            
            # Update province info from registered vehicle if not already set
            if not result["province_id"] and registered.province_id:
                province = db.query(Province).filter(Province.id == registered.province_id).first()
                if province:
                    result["province_id"] = province.id
                    result["province_name"] = province.name_th
                    result["province_code"] = province.code
                    result["match_method"] = "registered_vehicle"
            
            # If exact match, set perfect score
            if result["validation_score"] < 1.0:
                result["validation_score"] = 1.0
            
            logger.info(f"✅ Plate registered: {plate_number}")
        else:
            # Try fuzzy matching on vehicle plates
            fuzzy_matches = self._fuzzy_match_plate(plate_number, db)
            
            if fuzzy_matches:
                result["fuzzy_matches"] = fuzzy_matches
                
                # If top match is above threshold, use it
                if fuzzy_matches[0]["score"] >= self.VEHICLE_PLATE_THRESHOLD:
                    best_match = fuzzy_matches[0]
                    result["is_registered"] = True
                    result["registered_vehicle_id"] = best_match["vehicle_id"]
                    
                    # Use fuzzy score if it's better than province score
                    fuzzy_score = best_match["score"] / 100.0
                    if fuzzy_score > result["validation_score"]:
                        result["validation_score"] = fuzzy_score
                    
                    logger.info(
                        f"⚠️  Fuzzy matched plate: {plate_number} → {best_match['plate_number']} "
                        f"(score: {best_match['score']:.1f}%)"
                    )
        
        # ==================== PLATE FORMAT VALIDATION ====================
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
    
    def _fuzzy_match_province_by_name(
        self,
        province_text: str,
        db: Session,
        top_n: int = 3
    ) -> Optional[Dict]:
        """
        Find closest matching province using full Thai name
        
        This is the PRIMARY matching strategy for provinces as OCR often
        reads the full province name from the license plate.
        
        Args:
            province_text: Full or partial province name from OCR (e.g., "กรุงเทพมหานคร")
            db: Database session
            top_n: Number of top matches to consider
        
        Returns:
            Best matching province with score, or None
        
        Examples:
            Input: "กรุงเทพมหานคร" → Match: กรุงเทพมหานคร (100%)
            Input: "กรุงเทพมหานคธ" → Match: กรุงเทพมหานคร (95%) [OCR error: ร→ธ]
            Input: "เชียงใหม" → Match: เชียงใหม่ (90%) [Missing tone mark]
            Input: "ขอนแก่น" → Match: ขอนแก่น (100%)
        """
        if not province_text or len(province_text) < 2:
            return None
        
        # Clean input text
        province_text = province_text.strip()
        
        # Get all active provinces
        provinces = db.query(Province).filter(Province.is_active == True).all()
        
        if not provinces:
            return None
        
        # Build list of choices for fuzzy matching
        # Include both Thai and English names for better matching
        choices = []
        for province in provinces:
            choices.append({
                "text": province.name_th,
                "province": province,
                "type": "name_th"
            })
            # Also match against English name (some OCR might output English)
            if province.name_en:
                choices.append({
                    "text": province.name_en,
                    "province": province,
                    "type": "name_en"
                })
        
        # Perform fuzzy matching
        matches = []
        
        for choice in choices:
            # Calculate similarity scores using multiple algorithms
            # This provides better matching for Thai text with OCR errors
            
            ratio_score = fuzz.ratio(province_text, choice["text"])
            partial_score = fuzz.partial_ratio(province_text, choice["text"])
            token_sort_score = fuzz.token_sort_ratio(province_text, choice["text"])
            
            # Use the best score from all algorithms
            best_score = max(ratio_score, partial_score, token_sort_score)
            
            # Apply threshold based on text type
            threshold = (
                self.PROVINCE_NAME_THRESHOLD if choice["type"] == "name_th"
                else self.PROVINCE_ENGLISH_THRESHOLD
            )
            
            if best_score >= threshold:
                matches.append({
                    "province": choice["province"],
                    "score": best_score,
                    "match_type": choice["type"],
                    "matched_text": choice["text"]
                })
        
        if not matches:
            return None
        
        # Sort by score (highest first)
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        # Return best match
        best_match = matches[0]
        
        logger.debug(
            f"Province name match: '{province_text}' → '{best_match['matched_text']}' "
            f"({best_match['match_type']}, score: {best_match['score']:.1f}%)"
        )
        
        return best_match
    
    def _fuzzy_match_province_by_code(
        self,
        province_code: str,
        db: Session
    ) -> Optional[Dict]:
        """
        Find closest matching province using province code-like input

        This is the FALLBACK strategy when full province text is not available.
        Supports multiple input forms from OCR/UI:
        - Province table code (e.g., "10", "50")
        - Zero-padded numeric values (e.g., "01")
        - Province id accidentally sent as code (e.g., id=1)
        - Legacy Thai short text (e.g., "กท")
        """
        if not province_code or len(province_code) < 1:
            return None

        normalized_code = province_code.strip()

        # Get all active provinces
        provinces = db.query(Province).filter(Province.is_active == True).all()
        if not provinces:
            return None

        # 1) Exact code match first
        for province in provinces:
            if normalized_code == province.code:
                return {"province": province, "score": 100}

        # 2) Numeric normalization / province-id fallback
        if normalized_code.isdigit():
            numeric_value = int(normalized_code)

            for province in provinces:
                if province.code and province.code.isdigit() and int(province.code) == numeric_value:
                    return {"province": province, "score": 100}

            for province in provinces:
                if province.id == numeric_value:
                    logger.info(
                        f"ℹ️ Interpreting province code '{normalized_code}' as province id={numeric_value}"
                    )
                    return {"province": province, "score": 95}

        # 3) Fuzzy fallback (legacy short codes / OCR mistakes)
        fuzzy_input = normalized_code[:2]
        matches = []

        for province in provinces:
            score = fuzz.ratio(fuzzy_input, province.code)
            if score >= self.PROVINCE_CODE_THRESHOLD:
                matches.append({"province": province, "score": score})

        if not matches:
            return None

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[0]
    
    def _extract_province_from_text(
        self,
        text: str,
        db: Session
    ) -> Optional[Province]:
        """
        Extract province name from OCR text using substring matching
        
        OCR often returns text like "กก1234กรุงเทพมหานคร" where the province
        name is concatenated with the plate number.
        
        Args:
            text: Full OCR text
            db: Database session
        
        Returns:
            Matched Province object or None
        
        Examples:
            Input: "กก1234กรุงเทพมหานคร" → กรุงเทพมหานคร
            Input: "นว5678เชียงใหม่" → เชียงใหม่
        """
        if not text or len(text) < 4:
            return None
        
        # Get all active provinces
        provinces = db.query(Province).filter(Province.is_active == True).all()
        
        # Try to find province name as substring in text
        for province in provinces:
            # Check Thai name
            if province.name_th in text:
                logger.debug(f"Extracted province: {province.name_th} from '{text}'")
                return province
            
            # Check English name
            if province.name_en and province.name_en.lower() in text.lower():
                logger.debug(f"Extracted province: {province.name_en} from '{text}'")
                return province
        
        return None
    
    def _fuzzy_match_plate(
        self,
        plate_number: str,
        db: Session,
        top_n: int = 5
    ) -> List[Dict]:
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
        # Get registered plates (limit for performance)
        registered_plates = db.query(RegisteredVehicle).filter(
            RegisteredVehicle.is_active == True
        ).limit(1000).all()
        
        if not registered_plates:
            return []
        
        matches = []
        for registered in registered_plates:
            # Calculate similarity
            score = fuzz.ratio(plate_number, registered.plate_number)
            
            # Lower threshold for plate matching (more tolerant)
            if score >= 70:
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
        province_text: Optional[str] = None,
        db: Session = None
    ) -> List[Dict]:
        """
        Suggest possible corrections for plate and province
        
        Useful for the verification UI to show admins potential corrections
        
        Args:
            plate_number: Plate number from OCR
            province_text: Province text from OCR (optional)
            db: Database session
        
        Returns:
            List of suggested corrections with confidence scores
        """
        suggestions = []
        
        # Get fuzzy matches for plate
        fuzzy_matches = self._fuzzy_match_plate(plate_number, db, top_n=5)
        
        for match in fuzzy_matches:
            if match["score"] >= 75:
                suggestions.append({
                    "type": "plate_number",
                    "suggested_value": match["plate_number"],
                    "confidence": match["score"] / 100.0,
                    "reason": "Similar registered vehicle found",
                    "vehicle_id": match["vehicle_id"]
                })
        
        # Get province suggestions if text provided
        if province_text:
            province_match = self._fuzzy_match_province_by_name(province_text, db, top_n=3)
            
            if province_match:
                suggestions.append({
                    "type": "province",
                    "suggested_value": province_match["province"].name_th,
                    "province_code": province_match["province"].code,
                    "confidence": province_match["score"] / 100.0,
                    "reason": f"Matched province name (score: {province_match['score']:.1f}%)"
                })
        
        # Check for common OCR errors
        common_errors = self._check_common_ocr_errors(plate_number)
        suggestions.extend(common_errors)
        
        # Remove duplicates and sort by confidence
        seen = set()
        unique_suggestions = []
        for sugg in suggestions:
            key = f"{sugg['type']}:{sugg['suggested_value']}"
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(sugg)
        
        unique_suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        
        return unique_suggestions[:10]  # Return top 10
    
    def _check_common_ocr_errors(self, plate_number: str) -> List[Dict]:
        """
        Check for common OCR confusion patterns in Thai
        
        Common confusions:
        - ก (gor gai) vs ค (kor kwai)
        - จ (jor jan) vs ช (chor chang)
        - ร (ror rua) vs ธ (thor thong)
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
            'ร': ['ธ'],
            'ธ': ['ร'],
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
                        "type": "plate_number",
                        "suggested_value": corrected,
                        "confidence": 0.7,
                        "reason": f"Common OCR confusion: {char} → {replacement}"
                    })
        
        return suggestions