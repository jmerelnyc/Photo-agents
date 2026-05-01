#!/usr/bin/env python3
"""
Minimal UI element detector built on the OmniParser YOLO model.

Dependencies: ultralytics, rapidocr-onnxruntime, pillow, numpy.
"""
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from ultralytics import YOLO

DEFAULT_MODEL = str(Path(os.path.expanduser('~/.photoagents/weights')) / 'icon_detect' / 'model.pt')

try:
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("Warning: rapidocr is not installed; OCR step will be skipped.")


def detect_ui_elements(image_path, model_path=None, conf_threshold=0.25):
    """Detect UI elements and return their bounding boxes."""
    model_path = model_path or DEFAULT_MODEL
    model = YOLO(model_path)

    results = model(image_path, conf=conf_threshold, verbose=False)

    detections = []
    for result in results:
        boxes = result.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            detections.append({
                'bbox': [int(x1), int(y1), int(x2), int(y2)],
                'confidence': conf,
                'class': cls,
            })

    return detections


def ocr_text(image_path):
    """Run OCR and return recognized text regions."""
    if not HAS_OCR:
        return []

    result, _ = ocr_engine(image_path)
    if not result:
        return []

    texts = []
    for item in result:
        bbox, text, conf = item
        texts.append({
            'text': text,
            'bbox': bbox,
            'confidence': conf,
        })
    return texts


def visualize(image_path, detections, ocr_results=None, output_path=None):
    """Draw detections (and optional OCR results) onto the image."""
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        draw.rectangle([x1, y1, x2, y2], outline='red', width=2)
        draw.text((x1, y1 - 10), f"{det['confidence']:.2f}", fill='red')

    if ocr_results:
        for ocr in ocr_results:
            bbox = ocr['bbox']
            points = [(bbox[i][0], bbox[i][1]) for i in range(4)]
            draw.polygon(points, outline='blue')
            draw.text((points[0][0], points[0][1] - 10), ocr['text'][:10], fill='blue')

    if output_path:
        img.save(output_path)
    return img


def main():
    if len(sys.argv) < 2:
        print("Usage: python ui_detect.py <image_path> [model_path] [output_path]")
        print("Example: python ui_detect.py screenshot.png weights/icon_detect/model.pt output.png")
        sys.exit(1)

    image_path = sys.argv[1]
    model_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL
    output_path = sys.argv[3] if len(sys.argv) > 3 else "output.png"

    print(f"Detecting on image: {image_path}")
    print(f"Using model: {model_path}")

    print("\n[1/2] YOLO detecting UI elements...")
    detections = detect_ui_elements(image_path, model_path)
    print(f"Detected {len(detections)} UI elements")
    for i, det in enumerate(detections, 1):
        print(f"  {i}. bbox={det['bbox']}, conf={det['confidence']:.3f}")

    ocr_results = None
    if HAS_OCR:
        print("\n[2/2] OCR recognizing text...")
        ocr_results = ocr_text(image_path)
        print(f"Recognized {len(ocr_results)} text regions")
        for i, ocr in enumerate(ocr_results, 1):
            print(f"  {i}. text='{ocr['text']}', conf={ocr['confidence']:.3f}")

    print(f"\nSaving result to: {output_path}")
    visualize(image_path, detections, ocr_results, output_path)

    import json
    result = {
        'ui_elements': detections,
        'ocr_texts': ocr_results or [],
    }
    json_path = output_path.replace('.png', '.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"JSON result: {json_path}")


if __name__ == "__main__":
    main()
