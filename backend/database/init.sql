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
    code int(10) UNIQUE NOT NULL,
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
('10', 'กรุงเทพมหานคร', 'Bangkok', 'Central'),
('11', 'สมุทรปราการ', 'Samut Prakan', 'Central'),
('12', 'นนทบุรี', 'Nonthaburi', 'Central'),
('13', 'ปทุมธานี', 'Pathum Thani', 'Central'),
('74', 'สมุทรสาคร', 'Samut Sakhon', 'Central'),
('73', 'นครปฐม', 'Nakhon Pathom', 'Central'),

-- ภาคกลาง (Central)
('24', 'ฉะเชิงเทรา', 'Chachoengsao', 'Central'),
('20', 'ชลบุรี', 'Chonburi', 'Central'),
('21', 'ระยอง', 'Rayong', 'Central'),
('22', 'จันทบุรี', 'Chanthaburi', 'Central'),
('23', 'ตราด', 'Trat', 'Central'),
('25', 'ปราจีนบุรี', 'Prachinburi', 'Central'),
('27', 'สระแก้ว', 'Sa Kaeo', 'Central'),
('18', 'ชัยนาท', 'Chai Nat', 'Central'),
('16', 'ลพบุรี', 'Lopburi', 'Central'),
('17', 'สิงห์บุรี', 'Sing Buri', 'Central'),
('15', 'อ่างทอง', 'Ang Thong', 'Central'),
('14', 'พระนครศรีอยุธยา', 'Phra Nakhon Si Ayutthaya', 'Central'),
('19', 'สระบุรี', 'Saraburi', 'Central'),
('26', 'นครนายก', 'Nakhon Nayok', 'Central'),
('72', 'สุพรรณบุรี', 'Suphan Buri', 'Central'),
('71', 'กาญจนบุรี', 'Kanchanaburi', 'Central'),
('70', 'ราชบุรี', 'Ratchaburi', 'Central'),
('75', 'สมุทรสงคราม', 'Samut Songkhram', 'Central'),
('76', 'เพชรบุรี', 'Phetchaburi', 'Central'),
('77', 'ประจวบคีรีขันธ์', 'Prachuap Khiri Khan', 'Central'),

-- ภาคเหนือ (North)
('50', 'เชียงใหม่', 'Chiang Mai', 'North'),
('51', 'ลำพูน', 'Lamphun', 'North'),
('52', 'ลำปาง', 'Lampang', 'North'),
('53', 'อุตรดิตถ์', 'Uttaradit', 'North'),
('54', 'แพร่', 'Phrae', 'North'),
('55', 'น่าน', 'Nan', 'North'),
('56', 'พะเยา', 'Phayao', 'North'),
('57', 'เชียงราย', 'Chiang Rai', 'North'),
('58', 'แม่ฮ่องสอน', 'Mae Hong Son', 'North'),
('60', 'นครสวรรค์', 'Nakhon Sawan', 'North'),
('61', 'อุทัยธานี', 'Uthai Thani', 'North'),
('62', 'กำแพงเพชร', 'Kamphaeng Phet', 'North'),
('63', 'ตาก', 'Tak', 'North'),
('66', 'พิจิตร', 'Phichit', 'North'),
('65', 'พิษณุโลก', 'Phitsanulok', 'North'),
('64', 'สุโขทัย', 'Sukhothai', 'North'),
('67', 'เพชรบูรณ์', 'Phetchabun', 'North'),

-- ภาคตะวันออกเฉียงเหนือ (Northeast)
('30', 'นครราชสีมา', 'Nakhon Ratchasima', 'Northeast'),
('31', 'บุรีรัมย์', 'Buriram', 'Northeast'),
('32', 'สุรินทร์', 'Surin', 'Northeast'),
('33', 'ศรีสะเกษ', 'Si Sa Ket', 'Northeast'),
('34', 'อุบลราชธานี', 'Ubon Ratchathani', 'Northeast'),
('35', 'ยโสธร', 'Yasothon', 'Northeast'),
('36', 'ชัยภูมิ', 'Chaiyaphum', 'Northeast'),
('37', 'อำนาจเจริญ', 'Amnat Charoen', 'Northeast'),
('39', 'หนองบัวลำภู', 'Nong Bua Lam Phu', 'Northeast'),
('40', 'ขอนแก่น', 'Khon Kaen', 'Northeast'),
('41', 'อุดรธานี', 'Udon Thani', 'Northeast'),
('42', 'เลย', 'Loei', 'Northeast'),
('43', 'หนองคาย', 'Nong Khai', 'Northeast'),
('44', 'มหาสารคาม', 'Maha Sarakham', 'Northeast'),
('45', 'ร้อยเอ็ด', 'Roi Et', 'Northeast'),
('46', 'กาฬสินธุ์', 'Kalasin', 'Northeast'),
('47', 'สกลนคร', 'Sakon Nakhon', 'Northeast'),
('48', 'นครพนม', 'Nakhon Phanom', 'Northeast'),
('49', 'มุกดาหาร', 'Mukdahan', 'Northeast'),
('38', 'บึงกาฬ', 'Bueng Kan', 'Northeast'),

-- ภาคใต้ (South)
('80', 'นครศรีธรรมราช', 'Nakhon Si Thammarat', 'South'),
('81', 'กระบี่', 'Krabi', 'South'),
('82', 'พังงา', 'Phangnga', 'South'),
('83', 'ภูเก็ต', 'Phuket', 'South'),
('84', 'สุราษฎร์ธานี', 'Surat Thani', 'South'),
('85', 'ระนอง', 'Ranong', 'South'),
('86', 'ชุมพร', 'Chumphon', 'South'),
('90', 'สงขลา', 'Songkhla', 'South'),
('91', 'สตูล', 'Satun', 'South'),
('92', 'ตรัง', 'Trang', 'South'),
('93', 'พัทลุง', 'Phatthalung', 'South'),
('94', 'ปัตตานี', 'Pattani', 'South'),
('95', 'ยะลา', 'Yala', 'South'),
('96', 'นราธิวาส', 'Narathiwat', 'South'),
('97', 'เบตง', 'Betong', 'South');

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
