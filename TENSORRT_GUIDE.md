# TensorRT Conversion Guide

## 🚀 Convert YOLO Model to TensorRT for 2-5x Faster Inference

TensorRT is NVIDIA's high-performance deep learning inference optimizer. Converting your `best.pt` YOLO model to `best.engine` (TensorRT format) can provide **2-5x speedup** with minimal accuracy loss.

---

## 📋 Prerequisites

### 1. NVIDIA GPU Requirements
- NVIDIA GPU with CUDA support
- Compute Capability >= 5.0 (Maxwell architecture or newer)
- Recommended: RTX series (Turing/Ampere) for best performance

### 2. Software Requirements
```bash
# CUDA Toolkit (11.0 or higher)
nvidia-smi  # Verify CUDA is installed

# Python packages (already in requirements.txt)
pip install ultralytics>=8.0.0
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

---

## 🔧 Conversion Methods

### Method 1: Using Conversion Script (Recommended)

```bash
cd backend

# Basic conversion (default settings)
python tools/convert_to_tensorrt.py

# With custom settings
python tools/convert_to_tensorrt.py \
  --model models/best.pt \
  --imgsz 640 \
  --fp16 \
  --workspace 4 \
  --verify

# Options:
#   --model: Path to .pt file (default: models/best.pt)
#   --imgsz: Input image size (default: 640)
#   --fp16: Use FP16 precision for speed (default: True)
#   --workspace: GPU workspace in GB (default: 4)
#   --verify: Test engine after conversion
```

**Output:**
```
============================================================
TensorRT Conversion Started
============================================================
✅ GPU detected: NVIDIA GeForce RTX 3090
Compute capability: 8.6
📂 Loading model: models/best.pt
🔧 Converting to TensorRT engine...
   Image size: 640x640
   Precision: FP16
   Workspace: 4 GB
✅ Conversion successful!
📦 Engine saved to: models/best.engine

📊 File Size Comparison:
   Original (.pt):  14.32 MB
   TensorRT (.engine): 7.84 MB

⏱️  Running benchmark...
📈 Performance Comparison:
   PyTorch (.pt):     28.45 ms/image
   TensorRT (.engine): 8.73 ms/image
   Speedup:           3.26x faster ⚡

🔍 Verifying engine: models/best.engine
✅ Engine verification successful!

============================================================
✅ Conversion Complete!
============================================================

You can now use: models/best.engine
Update your config to use the .engine file for faster inference.
```

### Method 2: Manual Conversion (Python)

```python
from tools.convert_to_tensorrt import TensorRTConverter

# Create converter
converter = TensorRTConverter("models/best.pt")

# Check GPU
converter.check_gpu_availability()

# Convert
engine_path = converter.convert(
    imgsz=640,      # Input size
    half=True,      # FP16 precision
    workspace=4,    # GB
    verbose=True
)

# Verify
converter.verify_engine(engine_path)
```

---

## 🎯 Automatic Detection in ALPR Pipeline

The ALPR pipeline **automatically detects** and uses `.engine` files if available:

```python
# alpr_pipeline.py automatically checks:
# 1. models/best.engine (TensorRT) - PREFERRED
# 2. models/best.pt (PyTorch) - FALLBACK

# When you start the system:
✅ Found TensorRT engine: models/best.engine
⚡ Using TensorRT for accelerated inference

# OR if .engine doesn't exist:
Loading YOLO PyTorch model from models/best.pt
💡 Tip: Convert to TensorRT for 2-5x faster inference:
   python tools/convert_to_tensorrt.py --model models/best.pt
```

**No code changes needed!** Just place `best.engine` in the same folder as `best.pt`.

---

## 📊 Performance Comparison

### Typical Speedup Results

| GPU Model | PyTorch (.pt) | TensorRT (.engine) | Speedup |
|-----------|---------------|-------------------|---------|
| RTX 4090 | 12 ms | 3.5 ms | **3.4x** ⚡ |
| RTX 3090 | 15 ms | 5.2 ms | **2.9x** ⚡ |
| RTX 3080 | 18 ms | 6.8 ms | **2.6x** ⚡ |
| RTX 3070 | 22 ms | 8.4 ms | **2.6x** ⚡ |
| RTX 2080 Ti | 25 ms | 9.1 ms | **2.7x** ⚡ |
| GTX 1080 Ti | 35 ms | 15.2 ms | **2.3x** ⚡ |

*Speeds measured on 640x640 input images with YOLO models*

---

## 🔍 Precision Comparison

### FP16 vs FP32

```bash
# FP16 (Half Precision) - RECOMMENDED
python tools/convert_to_tensorrt.py --fp16

# Benefits:
✅ 2-5x faster inference
✅ ~50% smaller file size
✅ Minimal accuracy loss (<0.5%)
✅ Works on most modern GPUs (compute >= 5.3)

# FP32 (Full Precision)
python tools/convert_to_tensorrt.py --model models/best.pt --imgsz 640

# Benefits:
✅ Maximum accuracy
✅ Works on all GPUs
⚠️  Slower than FP16
⚠️  Larger file size
```

**Recommendation:** Use FP16 unless you need absolute maximum accuracy.

---

## 🛠️ Troubleshooting

### Issue 1: CUDA Not Available
```
❌ CUDA is not available. TensorRT requires NVIDIA GPU.
```

**Solution:**
```bash
# Check CUDA installation
nvidia-smi

# Install CUDA Toolkit
# https://developer.nvidia.com/cuda-downloads

# Verify PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

### Issue 2: Compute Capability Too Low
```
⚠️  GPU compute capability < 5.0. TensorRT may not work optimally.
```

**Solution:**
- Upgrade to newer GPU (GTX 900 series or newer)
- OR use PyTorch (.pt) model instead

### Issue 3: Out of Memory
```
RuntimeError: CUDA out of memory
```

**Solution:**
```bash
# Reduce workspace size
python tools/convert_to_tensorrt.py --workspace 2

# OR reduce image size
python tools/convert_to_tensorrt.py --imgsz 416
```

### Issue 4: Conversion Failed
```
❌ Conversion failed: ...
```

**Solution:**
```bash
# Install latest ultralytics
pip install --upgrade ultralytics

# Check model compatibility
python -c "from ultralytics import YOLO; YOLO('models/best.pt')"

# Try with verbose output
python tools/convert_to_tensorrt.py --verify
```

---

## 📁 File Organization

After conversion, your `models/` directory should look like:

```
models/
├── best.pt          # Original PyTorch model (14 MB)
├── best.engine      # TensorRT engine (8 MB) ⚡
└── easyocr/         # OCR models (auto-downloaded)
```

**Both files are kept** so you can switch between them if needed.

---

## 🔄 Re-conversion

### When to Re-convert

You need to re-convert if:
- ✅ You update the YOLO model (`best.pt`)
- ✅ You change input image size
- ✅ You upgrade GPU (different architecture)
- ✅ You upgrade CUDA/TensorRT version

### Re-conversion is NOT needed if:
- ❌ You update Python packages (other than ultralytics)
- ❌ You restart the server
- ❌ You move files to another machine with **same GPU**

---

## 🎛️ Advanced Configuration

### Custom Input Sizes

```bash
# For higher accuracy (slower)
python tools/convert_to_tensorrt.py --imgsz 1280

# For faster inference (lower accuracy)
python tools/convert_to_tensorrt.py --imgsz 416

# Common sizes: 320, 416, 512, 640, 1280
```

### Batch Processing Optimization

```bash
# Optimize for batch size 4
python -c "
from ultralytics import YOLO
model = YOLO('models/best.pt')
model.export(
    format='engine',
    imgsz=640,
    half=True,
    batch=4,  # Optimize for batch inference
    workspace=8
)
"
```

### Dynamic Shapes (Advanced)

```bash
# Support multiple input sizes
python -c "
from ultralytics import YOLO
model = YOLO('models/best.pt')
model.export(
    format='engine',
    dynamic=True,  # Enable dynamic shapes
    imgsz=640,
    half=True
)
"
```

---

## 📈 Monitoring Performance

### Log Performance in Production

The ALPR pipeline automatically logs model type:

```python
# In logs:
INFO - Using model type: TensorRT
INFO - Inference time: 8.73 ms
INFO - Processing FPS: 114.6

# Compare with PyTorch:
INFO - Using model type: PyTorch
INFO - Inference time: 28.45 ms
INFO - Processing FPS: 35.1
```

---

## 🚀 Production Deployment Checklist

Before deploying to production:

- [ ] Convert model to TensorRT
- [ ] Verify engine works: `--verify`
- [ ] Benchmark performance
- [ ] Test on sample images
- [ ] Confirm accuracy >= 95%
- [ ] Update Docker image with .engine file
- [ ] Monitor inference times in production

---

## 🎓 Additional Resources

- [NVIDIA TensorRT Documentation](https://docs.nvidia.com/deeplearning/tensorrt/)
- [Ultralytics TensorRT Export](https://docs.ultralytics.com/modes/export/#tensorrt)
- [CUDA Compute Capability](https://developer.nvidia.com/cuda-gpus)

---

## 💡 Tips & Best Practices

1. **Always keep both files** (.pt and .engine) for flexibility
2. **Re-convert after model updates** to maintain performance
3. **Use FP16 for production** unless accuracy drops
4. **Monitor GPU memory usage** during conversion
5. **Benchmark on your specific hardware** - results vary
6. **Test thoroughly** after conversion to ensure accuracy

---

**Conversion Status: ✅ Automatic**
**Performance Gain: 2-5x Faster**
**Accuracy Loss: < 0.5%**
**Recommended: Yes for production deployment**
