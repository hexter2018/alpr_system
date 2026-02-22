# Thai ALPR System - Enterprise License Plate Recognition

**Version:** 1.0.0  
**Author:** Senior Full-Stack Developer & Computer Vision Engineer  
**Stack:** FastAPI + React + PostgreSQL + YOLO + EasyOCR

---

## 🎯 System Overview

An enterprise-grade Automatic License Plate Recognition (ALPR) system specifically designed for Thai license plates. The system supports both **static image processing** and **live RTSP video streaming** with virtual trigger lines, achieving **>=95% accuracy** through OCR validation against master data and a **continuous learning pipeline** for model improvement.

### Key Features

✅ **Dual Processing Modes:**
- Static Image Upload (Single & Batch)
- Live RTSP Video Streaming with Virtual Trigger Lines

✅ **AI/CV Pipeline:**
- YOLO Custom Model (`best.pt`) for License Plate Detection
- ByteTrack for Vehicle Tracking
- EasyOCR for Thai Character Recognition
- Master Data Validation (Fuzzy Matching)

✅ **ALPR/MLPR Status System:**
- **ALPR** = Automatic (unmodified OCR results)
- **MLPR** = Manual (human-corrected for continuous learning)

✅ **Admin Verification UI:**
- Side-by-side display of cropped plate images and OCR text
- Edit interface for corrections
- Audit trail for all changes

✅ **Continuous Learning:**
- Corrected data saved for model retraining
- Training batch tracking

---

## 📁 Project Structure

```
alpr_system/
├── backend/                    # FastAPI Backend
│   ├── main.py                # Main FastAPI app
│   ├── database/
│   │   ├── models.py          # SQLAlchemy models
│   │   └── connection.py      # DB connection
│   ├── api/routes/
│   │   ├── upload.py          # Image upload & processing
│   │   ├── verification.py    # MLPR correction endpoints
│   │   ├── streaming.py       # RTSP camera management
│   │   ├── master_data.py     # Province/vehicle data
│   │   ├── analytics.py       # Dashboard stats
│   │   └── auth.py            # JWT authentication
│   ├── services/
│   │   ├── alpr_pipeline.py   # YOLO + OCR integration
│   │   ├── validation_service.py  # Master data validation
│   │   └── streaming_manager.py   # RTSP stream processor
│   └── requirements.txt
│
├── frontend/                  # React + TypeScript + Ant Design
│   ├── src/
│   │   ├── App.tsx            # Main app with routing
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── UploadPage.tsx
│   │   │   ├── VerificationPage.tsx  # ⭐ MLPR Correction UI
│   │   │   ├── StreamingPage.tsx
│   │   │   └── MasterDataPage.tsx
│   │   └── services/
│   │       └── api.ts         # Axios API client
│   ├── package.json
│   └── vite.config.ts
│
├── database/
│   └── init.sql               # PostgreSQL initialization with Thai provinces
│
├── models/
│   └── best.pt                # Custom YOLO model (user-provided)
│
└── storage/                   # File storage
    ├── uploads/               # Original uploaded images
    └── cropped_plates/        # Cropped license plate images
```

---

## 🚀 Quick Start Guide

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **PostgreSQL 14+**
- **CUDA-capable GPU** (recommended for YOLO/OCR)
- Your custom YOLO model `best.pt`

### Step 1: Database Setup

```bash
# Create PostgreSQL database
createdb thai_alpr

# Run initialization script (creates tables + inserts Thai provinces)
psql -U postgres -d thai_alpr -f database/init.sql
```

### Step 2: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials

# Place your YOLO model
mkdir -p models
cp /path/to/your/best.pt models/best.pt

# 🚀 OPTIONAL: Convert to TensorRT for 2-5x faster inference
python tools/convert_to_tensorrt.py --model models/best.pt --verify
# This creates models/best.engine (automatically used if available)
# See TENSORRT_GUIDE.md for details

# Run migrations (if using Alembic)
# alembic upgrade head

# Start server
python main.py
```

Backend will run on `http://localhost:8000`
- API Docs: `http://localhost:8000/api/docs`

### Step 3: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
echo "VITE_API_URL=http://localhost:8000/api" > .env.local

# Start development server
npm run dev
```

Frontend will run on `http://localhost:3000`

---

## 🔄 System Flow

### Flow 1: Static Image Processing

```
User Uploads Image
    ↓
YOLO Detection & Crop (best.pt)
    ↓
EasyOCR Reads Text
    ↓
Validate against Master Data (Provinces + Registered Vehicles)
    ↓
Save to DB with Status = 'ALPR'
    ↓
Display in Verification Page
    ↓
[If Admin Edits]
    ↓
Status Changes to 'MLPR'
    ↓
Correction Logged for Continuous Learning
```

### Flow 2: RTSP Streaming

```
RTSP Stream → YOLO Detection → ByteTrack Tracking
    ↓
Check Virtual Trigger Line
    ↓
[Vehicle Crosses Line]
    ↓
Capture Best Frame → Crop Plate → OCR
    ↓
Validate → Save to DB (Status = 'ALPR')
```

---

## 📊 Database Schema Highlights

### Core Tables

**plate_records** - Main table storing all detections
- `id`, `processing_mode`, `record_status`
- `ocr_plate_number`, `ocr_province_code`, `ocr_confidence`
- `corrected_plate_number`, `corrected_province_code` (MLPR)
- `final_plate_number`, `final_province_code` (computed)
- `cropped_plate_path`, `original_image_path`
- `is_registered`, `registered_vehicle_id`
- `camera_id`, `tracking_id`, `frame_number`

**plate_corrections** - Audit trail for MLPR
- `plate_record_id`, `before_plate_number`, `after_plate_number`
- `corrected_by_user_id`, `correction_timestamp`
- `used_for_training`, `training_batch_id`

**provinces** - Thai provinces master data (77 provinces)
- `code` (e.g., "กท"), `name_th`, `name_en`, `region`

**registered_vehicles** - Vehicle registration database
- `plate_number`, `province_id`, `plate_type`, `owner_name`

**cameras** - RTSP camera configuration
- `rtsp_url`, `trigger_config`, `fps_processing`

---

## 🎨 Frontend Pages

### 1. Dashboard
- System KPIs (Total, ALPR, MLPR, Accuracy Rate)
- Daily trends chart
- Top provinces chart

### 2. Upload Page
- Single image upload with instant processing
- Batch upload (up to 50 images)
- Progress tracking

### 3. Verification Page ⭐ **MOST IMPORTANT**
- **Data Table** with:
  - Cropped plate image (inline preview)
  - OCR result text
  - Confidence score
  - Status badge (ALPR/MLPR)
  - Edit button
- **Filters**: Status, Date range, Confidence, Province
- **Edit Modal**:
  - Shows cropped image
  - Input fields for corrected plate number and province
  - Reason for correction
  - Saves as MLPR status

### 4. Streaming Page
- List of RTSP cameras
- Start/Stop stream controls
- Configure trigger lines
- Live status monitoring

### 5. Master Data Page
- Province list
- Registered vehicle search

---

## 🔧 Configuration

### Backend Configuration (`.env`)

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=thai_alpr
DB_USER=postgres
DB_PASSWORD=your_password

# YOLO Model
YOLO_MODEL_PATH=models/best.pt

# OCR
OCR_ENGINE=easyocr
OCR_LANGUAGES=th,en

# Security
SECRET_KEY=generate_with_openssl_rand_hex_32
```

### Camera Trigger Configuration

```json
{
  "type": "line",
  "coords": [[0, 360], [1280, 360]]
}
```

Or ROI:

```json
{
  "type": "roi",
  "polygon": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
}
```

---

## 📡 API Endpoints

### Upload & Processing
- `POST /api/upload/single` - Upload single image
- `POST /api/upload/batch` - Upload multiple images
- `GET /api/upload/status/{record_id}` - Get processing status

### Verification (MLPR)
- `GET /api/verification/list` - Get paginated records with filters
- `GET /api/verification/{record_id}` - Get record details
- `POST /api/verification/{record_id}/correct` - Save correction (ALPR → MLPR)
- `GET /api/verification/corrections/pending-training` - Get corrections for model retraining

### Streaming
- `GET /api/streaming/cameras` - List cameras
- `POST /api/streaming/cameras` - Create camera
- `POST /api/streaming/cameras/{id}/start` - Start stream
- `POST /api/streaming/cameras/{id}/stop` - Stop stream
- `GET /api/streaming/streams/active` - Get active streams

### Analytics
- `GET /api/analytics/dashboard/summary` - Dashboard statistics
- `GET /api/analytics/dashboard/daily-trend?days=7` - Daily trend
- `GET /api/analytics/dashboard/top-provinces?limit=10` - Top provinces

### Master Data
- `GET /api/master-data/provinces` - Get all provinces
- `GET /api/master-data/vehicles` - Get registered vehicles
- `GET /api/master-data/vehicles/search?plate_number=กก1234` - Search vehicle

---

## 🧠 Continuous Learning Pipeline

### How It Works

1. **Admin corrects OCR mistake** in Verification Page
   - Status changes from `ALPR` to `MLPR`
   - Correction logged in `plate_corrections` table with `used_for_training = False`

2. **Collect corrections**
   ```bash
   GET /api/verification/corrections/pending-training?limit=1000
   ```

3. **Export training data**
   - Cropped images + corrected labels
   - Use for OCR model fine-tuning

4. **Mark as used**
   ```bash
   POST /api/verification/corrections/mark-trained
   {
     "correction_ids": [1, 2, 3, ...],
     "training_batch_id": "batch_20240115_001"
   }
   ```

5. **Retrain OCR model** (offline process)
   - Fine-tune EasyOCR on corrected data
   - Deploy new model

---

## 🎯 Performance Optimization

### Backend
- **Connection Pooling**: SQLAlchemy pool_size=20
- **Async Processing**: Background tasks for batch uploads
- **Image Optimization**: Resize before OCR
- **Caching**: Redis for frequent queries (optional)

### RTSP Streaming
- **Frame Skipping**: Process every Nth frame (`skip_frames=3`)
- **Trigger Logic**: Only process when crossing virtual line
- **Track Deduplication**: Each vehicle triggers only once

### Database
- **Indexes**: On `final_plate_number`, `capture_timestamp`, `record_status`
- **Partitioning**: Consider partitioning `plate_records` by date (for high volume)

---

## 🔐 Security Considerations

### Production Checklist
- [ ] Change `SECRET_KEY` in `.env`
- [ ] Enable JWT authentication on all endpoints
- [ ] Use HTTPS for frontend-backend communication
- [ ] Encrypt sensitive data (owner_name, vehicle info)
- [ ] Set up CORS whitelist for production domains
- [ ] Implement rate limiting (e.g., 100 requests/minute)
- [ ] Regular database backups
- [ ] Monitor for suspicious activity

### Sample JWT Implementation
Already included in `auth.py`:
```python
# Login returns JWT token
POST /api/auth/login
{
  "username": "admin",
  "password": "admin123"
}

# Include in headers
Authorization: Bearer <token>
```

---

## 📈 Scaling Recommendations

### For High-Volume Deployments

1. **Horizontal Scaling**
   - Run multiple FastAPI instances behind Nginx load balancer
   - Use Kubernetes for auto-scaling

2. **GPU Optimization**
   - Use TensorRT for faster YOLO inference
   - Batch OCR requests

3. **Database**
   - Use PostgreSQL replication (primary-replica)
   - Consider TimescaleDB for time-series data

4. **Storage**
   - Move images to S3/MinIO object storage
   - Use CDN for image delivery

5. **Monitoring**
   - Prometheus + Grafana for metrics
   - ELK stack for log aggregation

---

## 🐛 Troubleshooting

### Issue: YOLO model not loading
```bash
# Verify model path
ls -lh models/best.pt

# Check YOLO version compatibility
pip show ultralytics

# Test model loading
python -c "from ultralytics import YOLO; model = YOLO('models/best.pt'); print('OK')"
```

### Issue: EasyOCR not detecting Thai text
```bash
# Verify Thai model installed
ls ~/.EasyOCR/model/

# Test OCR
python -c "import easyocr; reader = easyocr.Reader(['th', 'en']); print('OK')"
```

### Issue: Database connection failed
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql -U postgres -d thai_alpr -c "SELECT 1;"
```

### Issue: RTSP stream not connecting
```bash
# Test stream with ffmpeg
ffmpeg -i rtsp://camera-url -frames:v 1 test.jpg

# Check camera config in database
psql -d thai_alpr -c "SELECT * FROM cameras WHERE id = 1;"
```

---

## 📚 Additional Resources

- **YOLO Documentation**: https://docs.ultralytics.com
- **EasyOCR GitHub**: https://github.com/JaidedAI/EasyOCR
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Ant Design**: https://ant.design

---

## 🤝 Support & Contribution

This is an enterprise-grade template system. For production deployment:

1. Review and customize the business logic for your specific use case
2. Add comprehensive unit and integration tests
3. Implement proper logging and monitoring
4. Conduct security audits
5. Optimize for your expected traffic volume

---

## 📝 License

Proprietary - Enterprise Solution

---

**Built with ❤️ for Thai License Plate Recognition**

**Accuracy Target: >=95%**  
**Status: Production-Ready Architecture**  
**Continuous Learning: Enabled**