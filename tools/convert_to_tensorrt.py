"""
TensorRT Conversion Utility
Converts YOLO .pt model to TensorRT .engine for faster inference
Optimized for NVIDIA GPUs with FP16 precision
"""

import os
import sys
import logging
from pathlib import Path
import torch
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TensorRTConverter:
    """Convert YOLO PyTorch model to TensorRT engine"""
    
    def __init__(self, model_path: str = "models/best.pt"):
        """
        Initialize converter
        
        Args:
            model_path: Path to YOLO .pt model file
        """
        self.model_path = Path(model_path)
        self.engine_path = self.model_path.with_suffix('.engine')
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
    
    def check_gpu_availability(self) -> bool:
        """Check if CUDA-capable GPU is available"""
        if not torch.cuda.is_available():
            logger.error("❌ CUDA is not available. TensorRT requires NVIDIA GPU.")
            return False
        
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"✅ GPU detected: {gpu_name}")
        
        # Check compute capability (TensorRT requires >= 5.0)
        compute_capability = torch.cuda.get_device_capability(0)
        logger.info(f"Compute capability: {compute_capability[0]}.{compute_capability[1]}")
        
        if compute_capability[0] < 5:
            logger.warning("⚠️  GPU compute capability < 5.0. TensorRT may not work optimally.")
        
        return True
    
    def convert(
        self,
        imgsz: int = 640,
        half: bool = True,
        workspace: int = 4,
        verbose: bool = True
    ) -> str:
        """
        Convert YOLO model to TensorRT engine
        
        Args:
            imgsz: Input image size (default: 640)
            half: Use FP16 precision for faster inference (default: True)
            workspace: Workspace size in GB (default: 4)
            verbose: Enable verbose logging (default: True)
        
        Returns:
            Path to generated .engine file
        """
        logger.info("=" * 60)
        logger.info("TensorRT Conversion Started")
        logger.info("=" * 60)
        
        # Check GPU
        if not self.check_gpu_availability():
            logger.error("Cannot proceed without CUDA-capable GPU")
            sys.exit(1)
        
        # Load YOLO model
        logger.info(f"📂 Loading model: {self.model_path}")
        try:
            model = YOLO(str(self.model_path))
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise
        
        # Export to TensorRT
        logger.info(f"🔧 Converting to TensorRT engine...")
        logger.info(f"   Image size: {imgsz}x{imgsz}")
        logger.info(f"   Precision: {'FP16' if half else 'FP32'}")
        logger.info(f"   Workspace: {workspace} GB")
        
        try:
            # Export using ultralytics built-in TensorRT export
            engine_path = model.export(
                format='engine',
                imgsz=imgsz,
                half=half,
                workspace=workspace,
                verbose=verbose,
                device=0  # Use first GPU
            )
            
            logger.info(f"✅ Conversion successful!")
            logger.info(f"📦 Engine saved to: {engine_path}")
            
            # Get file sizes for comparison
            pt_size = self.model_path.stat().st_size / (1024 * 1024)  # MB
            engine_size = Path(engine_path).stat().st_size / (1024 * 1024)  # MB
            
            logger.info(f"\n📊 File Size Comparison:")
            logger.info(f"   Original (.pt):  {pt_size:.2f} MB")
            logger.info(f"   TensorRT (.engine): {engine_size:.2f} MB")
            
            # Benchmark (optional)
            self._benchmark_models(model, engine_path)
            
            return engine_path
            
        except Exception as e:
            logger.error(f"❌ Conversion failed: {e}")
            raise
    
    def _benchmark_models(self, pt_model, engine_path: str):
        """
        Benchmark PT vs TensorRT performance
        
        Args:
            pt_model: PyTorch YOLO model
            engine_path: Path to TensorRT engine
        """
        logger.info("\n⏱️  Running benchmark...")
        
        try:
            import time
            import numpy as np
            
            # Create dummy input
            dummy_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            
            # Warmup
            for _ in range(5):
                _ = pt_model.predict(dummy_image, verbose=False)
            
            # Benchmark PyTorch
            pt_times = []
            for _ in range(20):
                start = time.time()
                _ = pt_model.predict(dummy_image, verbose=False)
                pt_times.append(time.time() - start)
            
            pt_avg = np.mean(pt_times) * 1000  # Convert to ms
            
            # Benchmark TensorRT
            trt_model = YOLO(engine_path)
            
            # Warmup
            for _ in range(5):
                _ = trt_model.predict(dummy_image, verbose=False)
            
            trt_times = []
            for _ in range(20):
                start = time.time()
                _ = trt_model.predict(dummy_image, verbose=False)
                trt_times.append(time.time() - start)
            
            trt_avg = np.mean(trt_times) * 1000  # Convert to ms
            
            speedup = pt_avg / trt_avg
            
            logger.info(f"\n📈 Performance Comparison:")
            logger.info(f"   PyTorch (.pt):     {pt_avg:.2f} ms/image")
            logger.info(f"   TensorRT (.engine): {trt_avg:.2f} ms/image")
            logger.info(f"   Speedup:           {speedup:.2f}x faster ⚡")
            
        except Exception as e:
            logger.warning(f"⚠️  Benchmark failed: {e}")
    
    def verify_engine(self, engine_path: str = None) -> bool:
        """
        Verify that the TensorRT engine works correctly
        
        Args:
            engine_path: Path to engine file (optional)
        
        Returns:
            True if engine is valid and working
        """
        if engine_path is None:
            engine_path = str(self.engine_path)
        
        logger.info(f"\n🔍 Verifying engine: {engine_path}")
        
        try:
            # Load engine
            model = YOLO(engine_path)
            
            # Test inference on dummy image
            import numpy as np
            dummy_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            
            results = model.predict(dummy_image, verbose=False)
            
            logger.info("✅ Engine verification successful!")
            logger.info(f"   Model loaded: {engine_path}")
            logger.info(f"   Inference working: Yes")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Engine verification failed: {e}")
            return False


def main():
    """Main conversion script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert YOLO .pt to TensorRT .engine')
    parser.add_argument(
        '--model',
        type=str,
        default='models/best.pt',
        help='Path to YOLO .pt model (default: models/best.pt)'
    )
    parser.add_argument(
        '--imgsz',
        type=int,
        default=640,
        help='Input image size (default: 640)'
    )
    parser.add_argument(
        '--fp16',
        action='store_true',
        default=True,
        help='Use FP16 precision (default: True)'
    )
    parser.add_argument(
        '--workspace',
        type=int,
        default=4,
        help='Workspace size in GB (default: 4)'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify engine after conversion'
    )
    
    args = parser.parse_args()
    
    # Create converter
    converter = TensorRTConverter(args.model)
    
    # Convert
    try:
        engine_path = converter.convert(
            imgsz=args.imgsz,
            half=args.fp16,
            workspace=args.workspace,
            verbose=True
        )
        
        # Verify if requested
        if args.verify:
            converter.verify_engine(engine_path)
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Conversion Complete!")
        logger.info("=" * 60)
        logger.info(f"\nYou can now use: {engine_path}")
        logger.info("\nUpdate your config to use the .engine file for faster inference.")
        
    except Exception as e:
        logger.error(f"\n❌ Conversion failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
