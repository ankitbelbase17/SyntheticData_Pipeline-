"""
Basic tests for core components in the SyntheticData_Pipeline codebase.
Run: python test_basic_utilities.py
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.keyword_sampler import sample_prompt_json
from utils.image_utils import check_aspect_ratio, check_min_resolution, resize_image
from PIL import Image
import io

def test_sampler_json():
    print("Testing keyword_sampler JSON output...")
    sample = sample_prompt_json()
    assert isinstance(sample, dict), "Sampler output is not a dict"
    assert "garment" in sample, "Missing 'garment' in output"
    print("✓ Sampler JSON output test passed.")

def test_utils_image():
    print("Testing utils image functions...")
    # Create a dummy image
    img = Image.new("RGB", (800, 1066))  # 3:4 aspect
    assert check_aspect_ratio(img), "Aspect ratio check failed"
    assert check_min_resolution(img), "Min resolution check failed"
    img2 = resize_image(img, (512, 512))
    assert img2.size == (512, 512), "Resize failed"
    print("✓ Utils image functions test passed.")

if __name__ == "__main__":
    try:
        test_sampler_json()
        test_utils_image()
        print("\n✓ All tests passed.")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
