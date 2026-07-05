"""
Quick test script to verify Gemini API integration.
Usage: python test_gemini.py [image_path]
"""

import os
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from services.gemini_search_service import (
    is_gemini_available,
    gemini_describe_image,
    gemini_enhanced_keyword_search,
)


def main():
    print("=" * 60)
    print("  Gemini API Integration Test")
    print("=" * 60)

    # Check availability
    available = is_gemini_available()
    print(f"\n[1] Gemini API available: {'✅ YES' if available else '❌ NO'}")

    if not available:
        print("    → Set GEMINI_API_KEY in .env and try again.")
        return

    # Determine test image
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # Try to find any image in media/uploads
        media_dir = os.path.join(os.path.dirname(__file__), 'media', 'uploads')
        if os.path.isdir(media_dir):
            images = [
                f for f in os.listdir(media_dir)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
            ]
            if images:
                image_path = os.path.join(media_dir, images[0])
            else:
                print("\n    No test images found in media/uploads/")
                print("    Usage: python test_gemini.py <path_to_image>")
                return
        else:
            print("\n    No media/uploads directory found.")
            print("    Usage: python test_gemini.py <path_to_image>")
            return

    print(f"\n[2] Test image: {image_path}")

    if not os.path.isfile(image_path):
        print(f"    ❌ File not found: {image_path}")
        return

    # Test image description
    print(f"\n[3] Testing Gemini image analysis...")
    print("-" * 40)

    analysis = gemini_describe_image(image_path)

    print(f"    Description:   {analysis['description'][:100]}...")
    print(f"    Document Type: {analysis['document_type']}")
    print(f"    Keywords:      {analysis['keywords']}")
    print(f"    Sources:       {analysis['potential_sources']}")

    # Test enhanced keyword search
    print(f"\n[4] Testing enhanced keyword search...")
    print("-" * 40)

    query, _, _ = gemini_enhanced_keyword_search(image_path)
    print(f"    Search query:  {query}")

    print(f"\n{'=' * 60}")
    print("  ✅ Gemini integration working!")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
