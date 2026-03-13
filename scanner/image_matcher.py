"""
Image Matcher for Card Verification
Compares user's photo against reference card image to verify ownership.
"""

import requests
from PIL import Image
from io import BytesIO
import math


class ImageMatcher:
    """Custom image matching for card verification."""

    def __init__(self, similarity_threshold: float = 0.65):
        """
        Initialize the matcher.

        Args:
            similarity_threshold: Minimum similarity score (0-1) to consider a match.
                                  0.65 = 65% similar required
        """
        self.similarity_threshold = similarity_threshold

    def load_image_from_url(self, url: str) -> Image.Image:
        """Download and load image from URL."""
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert('RGB')
        except Exception as e:
            print(f"Failed to load image from URL: {e}")
            return None

    def load_image_from_bytes(self, image_bytes: bytes) -> Image.Image:
        """Load image from bytes."""
        try:
            return Image.open(BytesIO(image_bytes)).convert('RGB')
        except Exception as e:
            print(f"Failed to load image from bytes: {e}")
            return None

    def resize_image(self, img: Image.Image, size: tuple = (64, 64)) -> Image.Image:
        """Resize image to standard size for comparison."""
        return img.resize(size, Image.Resampling.LANCZOS)

    def get_color_histogram(self, img: Image.Image, bins: int = 8) -> list:
        """
        Create a color histogram for the image.
        Divides each RGB channel into bins and counts pixels.
        """
        img = self.resize_image(img, (100, 100))
        pixels = list(img.getdata())

        # Initialize histogram (bins for R, G, B)
        histogram = [0] * (bins * 3)
        bin_size = 256 // bins

        for r, g, b in pixels:
            histogram[r // bin_size] += 1
            histogram[bins + (g // bin_size)] += 1
            histogram[bins * 2 + (b // bin_size)] += 1

        # Normalize histogram
        total = len(pixels) * 3
        histogram = [h / total for h in histogram]

        return histogram

    def get_average_hash(self, img: Image.Image, hash_size: int = 16) -> list:
        """
        Compute average hash of image.
        Resize to small size, convert to grayscale, compare to mean.
        """
        # Resize and convert to grayscale
        img = img.resize((hash_size, hash_size), Image.Resampling.LANCZOS)
        img = img.convert('L')  # Grayscale

        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)

        # Create binary hash
        return [1 if p > avg else 0 for p in pixels]

    def get_block_hash(self, img: Image.Image, blocks: int = 4) -> list:
        """
        Divide image into blocks and compute average color for each block.
        More robust than pixel-level comparison.
        """
        img = self.resize_image(img, (blocks * 10, blocks * 10))
        width, height = img.size
        block_w = width // blocks
        block_h = height // blocks

        block_colors = []

        for by in range(blocks):
            for bx in range(blocks):
                # Get block region
                left = bx * block_w
                top = by * block_h
                right = left + block_w
                bottom = top + block_h

                block = img.crop((left, top, right, bottom))
                pixels = list(block.getdata())

                # Average color of block
                avg_r = sum(p[0] for p in pixels) / len(pixels)
                avg_g = sum(p[1] for p in pixels) / len(pixels)
                avg_b = sum(p[2] for p in pixels) / len(pixels)

                block_colors.extend([avg_r / 255, avg_g / 255, avg_b / 255])

        return block_colors

    def get_edge_signature(self, img: Image.Image, size: int = 32) -> list:
        """
        Create a simple edge signature by comparing adjacent pixels.
        Helps match shapes/outlines of the Pokemon.
        """
        img = img.resize((size, size), Image.Resampling.LANCZOS).convert('L')
        pixels = list(img.getdata())

        edges = []
        for y in range(size):
            for x in range(size - 1):
                idx = y * size + x
                # Horizontal edge
                diff = abs(pixels[idx] - pixels[idx + 1])
                edges.append(1 if diff > 30 else 0)

        return edges

    def cosine_similarity(self, vec1: list, vec2: list) -> float:
        """Compute cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def hamming_similarity(self, hash1: list, hash2: list) -> float:
        """Compute similarity based on hamming distance for binary hashes."""
        if len(hash1) != len(hash2):
            return 0.0

        matches = sum(1 for a, b in zip(hash1, hash2) if a == b)
        return matches / len(hash1)

    def compare_images(self, reference_img: Image.Image, user_img: Image.Image) -> dict:
        """
        Compare reference card image with user's photo.
        Uses multiple methods and combines scores.

        Returns:
            dict with 'match' (bool), 'score' (float), and 'details' (dict)
        """
        if reference_img is None or user_img is None:
            return {'match': False, 'score': 0.0, 'details': {'error': 'Could not load images'}}

        # Method 1: Color histogram comparison
        ref_hist = self.get_color_histogram(reference_img)
        user_hist = self.get_color_histogram(user_img)
        color_score = self.cosine_similarity(ref_hist, user_hist)

        # Method 2: Average hash comparison
        ref_hash = self.get_average_hash(reference_img)
        user_hash = self.get_average_hash(user_img)
        hash_score = self.hamming_similarity(ref_hash, user_hash)

        # Method 3: Block color comparison
        ref_blocks = self.get_block_hash(reference_img)
        user_blocks = self.get_block_hash(user_img)
        block_score = self.cosine_similarity(ref_blocks, user_blocks)

        # Method 4: Edge signature comparison
        ref_edges = self.get_edge_signature(reference_img)
        user_edges = self.get_edge_signature(user_img)
        edge_score = self.hamming_similarity(ref_edges, user_edges)

        # Weighted combination of scores
        # Color and blocks are more important for cards (distinct artwork)
        final_score = (
            color_score * 0.30 +
            hash_score * 0.20 +
            block_score * 0.35 +
            edge_score * 0.15
        )

        is_match = final_score >= self.similarity_threshold

        return {
            'match': is_match,
            'score': round(final_score, 3),
            'percentage': round(final_score * 100, 1),
            'threshold': self.similarity_threshold,
            'details': {
                'color_similarity': round(color_score, 3),
                'hash_similarity': round(hash_score, 3),
                'block_similarity': round(block_score, 3),
                'edge_similarity': round(edge_score, 3)
            }
        }

    def verify_card(self, reference_url: str, user_image_bytes: bytes) -> dict:
        """
        Main verification method.

        Args:
            reference_url: URL of the official card image
            user_image_bytes: Bytes of the user's photo

        Returns:
            dict with verification result
        """
        # Load images
        reference_img = self.load_image_from_url(reference_url)
        user_img = self.load_image_from_bytes(user_image_bytes)

        if reference_img is None:
            return {'match': False, 'score': 0.0, 'error': 'Could not load reference image'}

        if user_img is None:
            return {'match': False, 'score': 0.0, 'error': 'Could not load your photo'}

        # Compare images
        result = self.compare_images(reference_img, user_img)

        return result


# Singleton instance
image_matcher = ImageMatcher(similarity_threshold=0.65)
