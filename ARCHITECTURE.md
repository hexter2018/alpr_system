# Thai ALPR System - Architecture Documentation

## 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Browser    │  │  Mobile App  │  │   Desktop    │          │
│  │  (React UI)  │  │  (Optional)  │  │  (Optional)  │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                    │
│         └─────────────────┴─────────────────┘                    │
│                           │                                      │
└───────────────────────────┼──────────────────────────────────────┘
                            │ HTTPS/REST API
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                           │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              FastAPI Backend (Python)                   │    │
│  │                                                          │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │    │
│  │  │ API Routes   │  │ Services     │  │ Background   │ │    │
│  │  │              │  │              │  │ Tasks        │ │    │
│  │  │ • Upload     │  │ • ALPR       │  │              │ │    │
│  │  │ • Verify     │  │   Pipeline   │  │ • Stream     │ │    │
│  │  │ • Stream     │  │ • Validation │  │   Processor  │ │    │
│  │  │ • Analytics  │  │ • Tracking   │  │ • Batch      │ │    │
│  │  │ • Auth       │  │              │  │   Upload     │ │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────┬───────────────────────┬───────────────────────────┘
               │                       │
               │                       │
               ▼                       ▼
┌──────────────────────┐    ┌────────────────────────────────────┐
│   AI/CV LAYER        │    │      DATA LAYER                    │
│                      │    │                                    │
│  ┌────────────────┐  │    │  ┌──────────────────────────┐    │
│  │ YOLO Detection │  │    │  │   PostgreSQL Database     │    │
│  │   (best.pt)    │  │    │  │                           │    │
│  │                │  │    │  │  • plate_records          │    │
│  │ • Detect Plate │  │    │  │  • plate_corrections      │    │
│  │ • Crop Image   │  │    │  │  • provinces              │    │
│  └────────┬───────┘  │    │  │  • registered_vehicles    │    │
│           │          │    │  │  • cameras                │    │
│           ▼          │    │  │  • users                  │    │
│  ┌────────────────┐  │    │  └──────────────────────────┘    │
│  │ ByteTrack      │  │    │                                    │
│  │                │  │    │  ┌──────────────────────────┐    │
│  │ • Track IDs    │  │    │  │   File Storage            │    │
│  │ • Deduplication│  │    │  │                           │    │
│  └────────┬───────┘  │    │  │  • storage/uploads        │    │
│           │          │    │  │  • storage/cropped_plates │    │
│           ▼          │    │  │  • storage/original       │    │
│  ┌────────────────┐  │    │  └──────────────────────────┘    │
│  │ EasyOCR        │  │    │                                    │
│  │                │  │    └────────────────────────────────────┘
│  │ • Thai OCR     │  │
│  │ • Confidence   │  │
│  └────────┬───────┘  │
│           │          │
│           ▼          │
│  ┌────────────────┐  │
│  │ Master Data    │  │
│  │ Validation     │  │
│  │                │  │
│  │ • Province     │  │
│  │ • Vehicle DB   │  │
│  │ • Fuzzy Match  │  │
│  └────────────────┘  │
└──────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL INPUTS                               │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │ Static Images│    │ RTSP Cameras │    │ Batch Upload │     │
│  │              │    │              │    │              │     │
│  │ • JPG/PNG    │    │ • Live Stream│    │ • Multiple   │     │
│  │ • Single     │    │ • Trigger    │    │   Images     │     │
│  │              │    │   Line       │    │              │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Processing Flow

### Image Upload Flow

```
User Upload
    ↓
[FastAPI: /api/upload/single]
    ↓
Save to storage/uploads/
    ↓
[YOLO Detection]
    ↓
Crop Plate → storage/cropped_plates/
    ↓
[EasyOCR]
    ↓
Extract: plate_number, province_code, confidence
    ↓
[Validation Service]
    ↓
Check against:
  • Province master data
  • Registered vehicles
  • Fuzzy matching
    ↓
[Database: plate_records]
    ↓
Status = 'ALPR' (Automatic)
    ↓
Return Result to User
```

### RTSP Streaming Flow

```
RTSP Camera Stream
    ↓
[StreamingManager]
    ↓
YOLO Detection (every Nth frame)
    ↓
[ByteTrack Tracking]
    ↓
Assign Track ID
    ↓
Check Trigger Line
    ↓
[Crossed?] → No → Continue Tracking
    ↓
    Yes
    ↓
Capture Best Frame
    ↓
Crop Plate
    ↓
[EasyOCR]
    ↓
[Validation]
    ↓
[Database: plate_records]
    ↓
camera_id, tracking_id, trigger_line_position
```

### MLPR Correction Flow

```
Admin Views Verification Page
    ↓
[GET /api/verification/list]
    ↓
Display Table:
  • Cropped Image
  • OCR Result
  • Confidence
  • Status
    ↓
Admin Clicks "Edit"
    ↓
Modal Shows:
  • Current Image
  • Current OCR
  • Edit Fields
    ↓
Admin Enters Correct Values
    ↓
[POST /api/verification/{id}/correct]
    ↓
[Database Updates]
  • corrected_plate_number
  • corrected_province_code
  • correction_timestamp
  • record_status = 'MLPR'
    ↓
[plate_corrections Table]
  • Log correction
  • used_for_training = False
    ↓
Response: Success
    ↓
[Future: Continuous Learning]
    ↓
Collect corrections → Retrain OCR
```

---

## 📊 Database Schema ERD

```
┌─────────────────────┐
│   plate_records     │  ◄─── Main table
├─────────────────────┤
│ • id (PK)           │
│ • processing_mode   │
│ • record_status     │  ◄─── ALPR/MLPR
│ • ocr_plate_number  │
│ • ocr_province_code │
│ • corrected_*       │  ◄─── If MLPR
│ • final_*           │
│ • is_registered     │
│ • cropped_path      │
│ • camera_id (FK)    │
│ • province_id (FK)  │
│ • tracking_id       │
└─────────┬───────────┘
          │
          │ 1:N
          ▼
┌─────────────────────┐
│ plate_corrections   │  ◄─── Audit trail
├─────────────────────┤
│ • id (PK)           │
│ • plate_record_id   │
│ • before_*          │
│ • after_*           │
│ • corrected_by      │
│ • used_for_training │
└─────────────────────┘

┌─────────────────────┐
│     provinces       │  ◄─── Master data
├─────────────────────┤
│ • id (PK)           │
│ • code (กท, นว)    │
│ • name_th           │
│ • name_en           │
│ • region            │
└─────────────────────┘

┌─────────────────────┐
│ registered_vehicles │  ◄─── Master data
├─────────────────────┤
│ • id (PK)           │
│ • plate_number      │
│ • province_id (FK)  │
│ • plate_type        │
│ • owner_name        │
└─────────────────────┘

┌─────────────────────┐
│      cameras        │  ◄─── RTSP config
├─────────────────────┤
│ • id (PK)           │
│ • rtsp_url          │
│ • trigger_config    │
│ • is_active         │
│ • status            │
└─────────────────────┘
```

---

## 🎯 Key Design Decisions

### 1. **ALPR vs MLPR Status**
- **ALPR**: Fully automatic, no human intervention
- **MLPR**: Human-corrected, used for continuous learning
- Enables tracking accuracy and improvement over time

### 2. **Separate OCR and Corrected Fields**
- Preserves original OCR output for analysis
- Allows comparison of model performance
- Supports A/B testing of OCR engines

### 3. **Trigger Line for Streaming**
- Prevents processing every frame (resource-intensive)
- Ensures each vehicle is captured only once
- Configurable per camera (line or ROI)

### 4. **Master Data Validation**
- Province validation ensures data quality
- Registered vehicle check for security
- Fuzzy matching catches OCR errors

### 5. **Modular Service Architecture**
- ALPRPipeline: Handles CV/AI logic
- ValidationService: Business rules
- StreamingManager: RTSP orchestration
- Clean separation of concerns

---

## 🔒 Security Architecture

```
┌──────────────┐
│   Client     │
└──────┬───────┘
       │ HTTPS
       ▼
┌──────────────┐
│  JWT Token   │  ◄─── Login returns token
└──────┬───────┘
       │ Bearer Token
       ▼
┌──────────────┐
│  FastAPI     │
│  Middleware  │  ◄─── Validates token on each request
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Protected   │
│  Endpoints   │
└──────────────┘
```

---

## 📈 Scalability Strategy

### Horizontal Scaling

```
┌─────────────┐
│ Load        │
│ Balancer    │
│ (Nginx)     │
└──────┬──────┘
       │
       ├───────────┬───────────┬───────────┐
       ▼           ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │FastAPI │ │FastAPI │ │FastAPI │ │FastAPI │
   │Worker 1│ │Worker 2│ │Worker 3│ │Worker 4│
   └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
       │          │          │          │
       └──────────┴──────────┴──────────┘
                  │
                  ▼
           ┌────────────┐
           │ PostgreSQL │
           │  (Primary) │
           └──────┬─────┘
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │Replica │ │Replica │ │Replica │
   │   1    │ │   2    │ │   3    │
   └────────┘ └────────┘ └────────┘
```

### Performance Optimizations

1. **GPU Processing**
   - YOLO and OCR run on GPU
   - Batch inference for multiple images

2. **Database Indexing**
   - B-tree indexes on lookup columns
   - GIN indexes for fuzzy search
   - Partitioning by date for high volume

3. **Caching**
   - Redis for frequent queries
   - Province data cached in memory
   - Model inference results cached

4. **Async Processing**
   - Background tasks for batch uploads
   - Streaming runs in separate threads
   - Non-blocking I/O

---

## 🎓 Continuous Learning Pipeline

```
┌──────────────────────────────────────────────────────┐
│          Continuous Learning Workflow                 │
└──────────────────────────────────────────────────────┘

1. Admin Corrects OCR Error
       ↓
2. Save to plate_corrections (used_for_training=False)
       ↓
3. Collect Corrections API
   GET /api/verification/corrections/pending-training
       ↓
4. Export Training Dataset
   • Cropped images
   • Corrected labels (ground truth)
       ↓
5. Fine-tune OCR Model (Offline)
   • EasyOCR fine-tuning
   • Custom dataset
       ↓
6. Mark as Used
   POST /api/verification/corrections/mark-trained
       ↓
7. Deploy New Model
   • Replace OCR weights
   • A/B test performance
       ↓
8. Monitor Accuracy Improvement
```

---

**Architecture Status: Production-Ready**  
**Scalability: Horizontal**  
**Security: JWT + HTTPS**  
**Learning: Enabled**
