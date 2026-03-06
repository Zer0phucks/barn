#!/usr/bin/env python3
"""
Extract text from image-based PDF via EasyOCR and export entire dataset to CSV.
Usage: python pdf_to_csv_ocr.py <input.pdf> [output.csv]
"""
import csv
import sys
from pathlib import Path

import numpy as np
from pdf2image import convert_from_path
import easyocr


def extract_pdf_to_csv(pdf_path: str, csv_path: str, dpi: int = 150) -> None:
    pdf_path = Path(pdf_path)
    csv_path = Path(csv_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    print("Converting PDF to images...")
    images = convert_from_path(str(pdf_path), dpi=dpi)
    print(f"Loaded {len(images)} pages.")

    reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["page", "x", "y", "text", "confidence"]
    total_rows = 0
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for page_num, img in enumerate(images, start=1):
            print(f"OCR page {page_num}/{len(images)}...")
            img_np = np.array(img)
            result = reader.readtext(img_np)
            for (box, text, confidence) in result:
                x = float(box[0][0])
                y = float(box[0][1])
                w.writerow({
                    "page": page_num,
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "text": text.replace("\n", " ").strip(),
                    "confidence": round(confidence, 4),
                })
                total_rows += 1
            f.flush()

    print(f"Wrote {total_rows} rows to {csv_path}")


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else "screencapture-app-propertyradar-2026-02-25-15_26_00.pdf"
    out = sys.argv[2] if len(sys.argv) > 2 else str(Path(pdf).with_suffix(".csv"))
    extract_pdf_to_csv(pdf, out)


if __name__ == "__main__":
    main()
