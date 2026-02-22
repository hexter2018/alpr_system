-- ==========================================
-- Thai ALPR System - Database Initialization
-- PostgreSQL 14+
-- ==========================================

-- Create Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy text matching

-- ==========================================
-- ENUM TYPES
-- ==========================================

CREATE TYPE record_status_enum AS ENUM ('ALPR', 'MLPR', 'PENDING', 'REJECTED');
CREATE TYPE processing_mode_enum AS ENUM ('IMAGE_SINGLE', 'IMAGE_BATCH', 'STREAM_RTSP');
CREATE TYPE plate_type_enum AS ENUM (
    'PRIVATE', 'COMMERCIAL', 'TAXI', 'MOTORCYCLE', 
    'GOVERNMENT', 'TEMPORARY', 'DIPLOMATIC', 'UNKNOWN'
);

-- ==========================================
-- TABLES
-- ==========================================

BEGIN;

CREATE TABLE IF NOT EXISTS provinces (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    name_th VARCHAR(100) NOT NULL,
    name_en VARCHAR(100) NOT NULL,
    region VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS plate_prefixes (
    id SERIAL PRIMARY KEY,
    prefix VARCHAR(10) UNIQUE NOT NULL,
    plate_type plate_type_enum NOT NULL,
    description VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    hashed_password VARCHAR(500) NOT NULL,
    full_name VARCHAR(200),
    role VARCHAR(50) DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS registered_vehicles (
    id SERIAL PRIMARY KEY,
    plate_number VARCHAR(50) UNIQUE NOT NULL,
    province_id INTEGER NOT NULL REFERENCES provinces(id),
    plate_type plate_type_enum NOT NULL,
    owner_name VARCHAR(200),
    vehicle_model VARCHAR(100),
    vehicle_color VARCHAR(50),
    registration_date TIMESTAMPTZ,
    expiry_date TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS plate_records (
    id SERIAL PRIMARY KEY,
    image_path VARCHAR(500),
    camera_id INTEGER,
    processing_mode processing_mode_enum NOT NULL,
    record_status record_status_enum NOT NULL DEFAULT 'PENDING',
    ocr_plate_number VARCHAR(50) NOT NULL,
    ocr_province_code VARCHAR(10),
    ocr_full_text VARCHAR(100),
    ocr_confidence FLOAT,
    corrected_plate_number VARCHAR(50),
    corrected_province_code VARCHAR(10),
    correction_timestamp TIMESTAMPTZ,
    corrected_by_user_id INTEGER REFERENCES users(id),
    final_plate_number VARCHAR(50) NOT NULL,
    final_province_code VARCHAR(10),
    province_id INTEGER REFERENCES provinces(id),
    is_registered BOOLEAN DEFAULT FALSE,
    registered_vehicle_id INTEGER REFERENCES registered_vehicles(id),
    capture_timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- ==========================================
-- MASTER DATA: Thai Provinces (77 provinces)
-- ==========================================

INSERT INTO provinces (code, name_th, name_en, region) VALUES
-- กรุงเทพและปริมณฑล (Bangkok & Vicinity)
('กท', 'กรุงเทพมหานคร', 'Bangkok', 'Central'),
('สป', 'สมุทรปราการ', 'Samut Prakan', 'Central'),
('นป', 'นนทบุรี', 'Nonthaburi', 'Central'),
('ปท', 'ปทุมธานี', 'Pathum Thani', 'Central'),
('สบ', 'สมุทรสาคร', 'Samut Sakhon', 'Central'),
('นฐ', 'นครปฐม', 'Nakhon Pathom', 'Central'),

-- ภาคกลาง (Central)
('ฉช', 'ฉะเชิงเทรา', 'Chachoengsao', 'Central'),
('ชบ', 'ชลบุรี', 'Chonburi', 'Central'),
('รย', 'ระยอง', 'Rayong', 'Central'),
('จบ', 'จันทบุรี', 'Chanthaburi', 'Central'),
('ตร', 'ตราด', 'Trat', 'Central'),
('ปจ', 'ปราจีนบุรี', 'Prachinburi', 'Central'),
('สฎ', 'สระแก้ว', 'Sa Kaeo', 'Central'),
('ชน', 'ชัยนาท', 'Chai Nat', 'Central'),
('ลบ', 'ลพบุรี', 'Lopburi', 'Central'),
('สห', 'สิงห์บุรี', 'Sing Buri', 'Central'),
('อท', 'อ่างทอง', 'Ang Thong', 'Central'),
('พน', 'พระนครศรีอยุธยา', 'Phra Nakhon Si Ayutthaya', 'Central'),
('สพ', 'สระบุรี', 'Saraburi', 'Central'),
('นย', 'นครนายก', 'Nakhon Nayok', 'Central'),
('สข', 'สุพรรณบุรี', 'Suphan Buri', 'Central'),
('กจ', 'กาญจนบุรี', 'Kanchanaburi', 'Central'),
('รบ', 'ราชบุรี', 'Ratchaburi', 'Central'),
('สส', 'สมุทรสงคราม', 'Samut Songkhram', 'Central'),
('พท', 'เพชรบุรี', 'Phetchaburi', 'Central'),
('ปข', 'ประจวบคีรีขันธ์', 'Prachuap Khiri Khan', 'Central'),

-- ภาคเหนือ (North)
('นว', 'เชียงใหม่', 'Chiang Mai', 'North'),
('ลห', 'ลำพูน', 'Lamphun', 'North'),
('ลป', 'ลำปาง', 'Lampang', 'North'),
('อต', 'อุตรดิตถ์', 'Uttaradit', 'North'),
('พร', 'แพร่', 'Phrae', 'North'),
('นน', 'น่าน', 'Nan', 'North'),
('พย', 'พะเยา', 'Phayao', 'North'),
('ชร', 'เชียงราย', 'Chiang Rai', 'North'),
('มห', 'แม่ฮ่องสอน', 'Mae Hong Son', 'North'),
('นค', 'นครสวรรค์', 'Nakhon Sawan', 'North'),
('อน', 'อุทัยธานี', 'Uthai Thani', 'North'),
('กพ', 'กำแพงเพชร', 'Kamphaeng Phet', 'North'),
('ตก', 'ตาก', 'Tak', 'North'),
('พช', 'พิจิตร', 'Phichit', 'North'),
('พษ', 'พิษณุโลก', 'Phitsanulok', 'North'),
('สท', 'สุโขทัย', 'Sukhothai', 'North'),

-- ภาคตะวันออกเฉียงเหนือ (Northeast)
('นม', 'นครราชสีมา', 'Nakhon Ratchasima', 'Northeast'),
('บร', 'บุรีรัมย์', 'Buriram', 'Northeast'),
('สร', 'สุรินทร์', 'Surin', 'Northeast'),
('ศก', 'ศรีสะเกษ', 'Si Sa Ket', 'Northeast'),
('อบ', 'อุบลราชธานี', 'Ubon Ratchathani', 'Northeast'),
('ยส', 'ยโสธร', 'Yasothon', 'Northeast'),
('ชย', 'ชัยภูมิ', 'Chaiyaphum', 'Northeast'),
('อด', 'อำนาจเจริญ', 'Amnat Charoen', 'Northeast'),
('บก', 'หนองบัวลำภู', 'Nong Bua Lam Phu', 'Northeast'),
('ขก', 'ขอนแก่น', 'Khon Kaen', 'Northeast'),
('อุดร', 'อุดรธานี', 'Udon Thani', 'Northeast'),
('เลย', 'เลย', 'Loei', 'Northeast'),
('หนอ', 'หนองคาย', 'Nong Khai', 'Northeast'),
('มค', 'มหาสารคาม', 'Maha Sarakham', 'Northeast'),
('รอ', 'ร้อยเอ็ด', 'Roi Et', 'Northeast'),
('กส', 'กาฬสินธุ์', 'Kalasin', 'Northeast'),
('สน', 'สกลนคร', 'Sakon Nakhon', 'Northeast'),
('นพ', 'นครพนม', 'Nakhon Phanom', 'Northeast'),
('มส', 'มุกดาหาร', 'Mukdahan', 'Northeast'),
('บึง', 'บึงกาฬ', 'Bueng Kan', 'Northeast'),

-- ภาคใต้ (South)
('นศ', 'นครศรีธรรมราช', 'Nakhon Si Thammarat', 'South'),
('กบ', 'กระบี่', 'Krabi', 'South'),
('พง', 'พังงา', 'Phangnga', 'South'),
('ภก', 'ภูเก็ต', 'Phuket', 'South'),
('สท', 'สุราษฎร์ธานี', 'Surat Thani', 'South'),
('รน', 'ระนอง', 'Ranong', 'South'),
('ชม', 'ชุมพร', 'Chumphon', 'South'),
('สงขลา', 'สงขลา', 'Songkhla', 'South'),
('สตูล', 'สตูล', 'Satun', 'South'),
('ตรัง', 'ตรัง', 'Trang', 'South'),
('พทลง', 'พัทลุง', 'Phatthalung', 'South'),
('ปตนี', 'ปัตตานี', 'Pattani', 'South'),
('ยลา', 'ยะลา', 'Yala', 'South'),
('นธ', 'นราธิวาส', 'Narathiwat', 'South');

-- ==========================================
-- MASTER DATA: Common Thai License Plate Prefixes
-- ==========================================

INSERT INTO plate_prefixes (prefix, plate_type, description) VALUES
-- Private vehicles
('กก', 'PRIVATE', 'Private vehicle - Bangkok'),
('ขข', 'PRIVATE', 'Private vehicle'),
('กข', 'PRIVATE', 'Private vehicle'),
('นค', 'PRIVATE', 'Private vehicle - Chiang Mai'),

-- Taxis
('กท', 'TAXI', 'Taxi - Bangkok'),

-- Commercial
('บข', 'COMMERCIAL', 'Commercial truck'),
('กง', 'COMMERCIAL', 'Commercial truck'),

-- Motorcycles
('กฉ', 'MOTORCYCLE', 'Motorcycle'),
('1กก', 'MOTORCYCLE', 'Motorcycle'),

-- Government
('กม', 'GOVERNMENT', 'Government vehicle'),
('นย', 'GOVERNMENT', 'Government vehicle');

-- ==========================================
-- INDEXES FOR PERFORMANCE
-- ==========================================

-- Full-text search for plate numbers
CREATE INDEX idx_plate_records_plate_trgm ON plate_records USING gin (final_plate_number gin_trgm_ops);
CREATE INDEX idx_plate_records_ocr_trgm ON plate_records USING gin (ocr_plate_number gin_trgm_ops);

-- Composite indexes for common queries
CREATE INDEX idx_plate_records_status_time ON plate_records (record_status, capture_timestamp DESC);
CREATE INDEX idx_plate_records_camera_status ON plate_records (camera_id, record_status, capture_timestamp DESC);

-- ==========================================
-- FUNCTIONS & TRIGGERS
-- ==========================================

-- Auto-update final_plate_number based on correction
CREATE OR REPLACE FUNCTION update_final_plate()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.record_status = 'MLPR' THEN
        NEW.final_plate_number := COALESCE(NEW.corrected_plate_number, NEW.ocr_plate_number);
        NEW.final_province_code := COALESCE(NEW.corrected_province_code, NEW.ocr_province_code);
    ELSE
        NEW.final_plate_number := NEW.ocr_plate_number;
        NEW.final_province_code := NEW.ocr_province_code;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_final_plate
BEFORE INSERT OR UPDATE ON plate_records
FOR EACH ROW
EXECUTE FUNCTION update_final_plate();

-- Auto-update timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_timestamp
BEFORE UPDATE ON plate_records
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

-- ==========================================
-- VIEWS FOR ANALYTICS
-- ==========================================

-- Daily statistics view
CREATE OR REPLACE VIEW daily_statistics AS
SELECT 
    DATE(capture_timestamp) as date,
    processing_mode,
    record_status,
    COUNT(*) as total_records,
    AVG(ocr_confidence) as avg_confidence,
    COUNT(CASE WHEN is_registered = TRUE THEN 1 END) as registered_count
FROM plate_records
GROUP BY DATE(capture_timestamp), processing_mode, record_status;

-- Accuracy metrics view
CREATE OR REPLACE VIEW accuracy_metrics AS
SELECT 
    DATE(capture_timestamp) as date,
    COUNT(*) as total_plates,
    COUNT(CASE WHEN record_status = 'ALPR' THEN 1 END) as alpr_count,
    COUNT(CASE WHEN record_status = 'MLPR' THEN 1 END) as mlpr_count,
    ROUND(
        (COUNT(CASE WHEN record_status = 'ALPR' THEN 1 END)::NUMERIC / 
         NULLIF(COUNT(*), 0) * 100), 2
    ) as accuracy_percentage
FROM plate_records
WHERE record_status IN ('ALPR', 'MLPR')
GROUP BY DATE(capture_timestamp);

-- ==========================================
-- SAMPLE DATA FOR TESTING (Optional)
-- ==========================================

-- Sample registered vehicles
INSERT INTO registered_vehicles (plate_number, province_id, plate_type, vehicle_model, vehicle_color) VALUES
('กก1234', 1, 'PRIVATE', 'Toyota Camry', 'Black'),
('นว5678', 27, 'PRIVATE', 'Honda Civic', 'White'),
('กท9999', 1, 'TAXI', 'Toyota Corolla Altis', 'Yellow');

-- Sample admin user (password: admin123 - CHANGE IN PRODUCTION!)
-- Password hash generated with bcrypt
INSERT INTO users (username, email, hashed_password, full_name, role, is_superuser) VALUES
('admin', 'admin@alpr.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5yvAiNQG/cL7y', 'System Administrator', 'admin', TRUE);

COMMIT;
