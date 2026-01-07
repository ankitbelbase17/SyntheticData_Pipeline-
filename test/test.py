# test.py
"""
Basic tests for core components in the SyntheticData_Pipeline codebase.
Run: python test/test.py
"""
import sys
sys.path.append("..")

from keyword_sampler import sample_prompt_json
from utils import check_aspect_ratio, check_min_resolution, resize_image
from PIL import Image
import io

def test_sampler_json():
    print("Testing keyword_sampler JSON output...")
    sample = sample_prompt_json()
    assert isinstance(sample, dict), "Sampler output is not a dict"
    assert "garment" in sample, "Missing 'garment' in output"
    print("Sampler JSON output test passed.")

def test_utils_image():
    print("Testing utils image functions...")
    # Create a dummy image
    img = Image.new("RGB", (800, 1066))  # 3:4 aspect
    assert check_aspect_ratio(img), "Aspect ratio check failed"
    assert check_min_resolution(img), "Min resolution check failed"
    img2 = resize_image(img, (512, 512))
    assert img2.size == (512, 512), "Resize failed"
    print("Utils image functions test passed.")

if __name__ == "__main__":
    test_sampler_json()
    test_utils_image()
    print("All tests passed.")
