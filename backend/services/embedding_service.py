"""
CNN Embedding extraction service.

Uses a pre-trained MobileNetV2 model (without final classifier) to extract
1280-dimensional feature vectors from images. These embeddings are used
for cosine similarity comparisons.

Features:
- Auto-detect GPU (CUDA) for accelerated inference, fallback to CPU
- L2 normalization to unit length vectors
- Singleton model loading (loaded once, reused)
- torch.no_grad() inference for memory efficiency
"""

import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy-loaded model, transforms, and device
_model = None
_transform = None
_device = None


def _get_device():
    """Auto-detect best available device (CUDA GPU > CPU)."""
    import torch

    if torch.cuda.is_available():
        device = torch.device('cuda')
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"GPU detected: {gpu_name} — using CUDA for inference")
    else:
        device = torch.device('cpu')
        logger.info("No GPU detected — using CPU for inference")

    return device


def _load_model():
    """Lazy-load the MobileNetV2 model and preprocessing transforms (singleton)."""
    global _model, _transform, _device

    if _model is not None:
        return

    try:
        import torch
        import torch.nn as nn
        import torchvision.models as models
        import torchvision.transforms as transforms

        logger.info("Loading MobileNetV2 model...")

        # Detect device
        _device = _get_device()

        # Load pre-trained MobileNetV2 (ImageNet weights)
        mobilenet = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)

        # Remove classifier — MobileNetV2's forward() already applies
        # AdaptiveAvgPool2d + Flatten before passing to classifier,
        # so classifier input is already 2D: [batch, 1280]
        mobilenet.classifier = nn.Identity()
        mobilenet.eval()

        # Move model to GPU if available
        _model = mobilenet.to(_device)

        # ImageNet preprocessing — resize directly to 224x224
        _transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        logger.info(
            f"MobileNetV2 loaded successfully on {_device} "
            f"(output: 1280-dim, L2-normalized)"
        )

    except ImportError:
        logger.error(
            "PyTorch/torchvision not installed. "
            "Install with: pip install torch torchvision"
        )
        raise
    except Exception as e:
        logger.error(f"Failed to load MobileNetV2: {e}")
        raise


def extract_embedding(image_path):
    """
    Extract a 1280-dimensional L2-normalized embedding vector from an image.

    Args:
        image_path: Path to the image file (string).

    Returns:
        list[float]: 1280-dimensional unit-length embedding vector.
    """
    import torch

    _load_model()

    try:
        # Load and preprocess image (force RGB)
        image = Image.open(image_path).convert('RGB')
        input_tensor = _transform(image).unsqueeze(0)  # Add batch dim

        # Move input to same device as model (GPU/CPU)
        input_tensor = input_tensor.to(_device)

        # Generate embedding (no gradient computation)
        with torch.no_grad():
            embedding = _model(input_tensor)

        # Move back to CPU for numpy conversion
        embedding_np = embedding.squeeze().cpu().numpy().astype(np.float32)

        # L2 normalization — normalize to unit length
        norm = np.linalg.norm(embedding_np)
        if norm > 0:
            embedding_np = embedding_np / norm

        embedding_list = embedding_np.tolist()

        logger.info(
            f"Embedding extracted for {image_path}: "
            f"{len(embedding_list)} dims, device={_device}, "
            f"L2-norm={np.linalg.norm(embedding_np):.4f}"
        )

        return embedding_list

    except FileNotFoundError:
        logger.error(f"Image file not found: {image_path}")
        raise
    except Exception as e:
        logger.error(f"Embedding extraction failed: {e}")
        raise


# Backward-compatible alias
generate_embedding = extract_embedding
