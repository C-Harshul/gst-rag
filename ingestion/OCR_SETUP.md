# OCR Setup Guide

This document explains how to set up OCR (Optical Character Recognition) as a fallback option for PDF extraction when both regular extraction and AWS Textract fail.

## Overview

The OCR functionality uses Tesseract OCR to extract text from PDFs by:
1. Converting PDF pages to images
2. Running OCR on each image
3. Combining the extracted text

## Installation

### 1. Install Python Dependencies

```bash
pip install pdf2image pytesseract Pillow
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### 2. Install Tesseract OCR (System Dependency)

Tesseract OCR must be installed on your system. The installation method depends on your operating system:

#### macOS
```bash
brew install tesseract
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

#### Windows
1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer
3. Add Tesseract to your system PATH, or specify the path in code:
   ```python
   ocr_processor = OCRProcessor(tesseract_cmd=r'C:\Program Files\Tesseract-OCR\tesseract.exe')
   ```

#### CentOS/RHEL
```bash
sudo yum install tesseract
```

### 3. Install Poppler (Required for pdf2image)

`pdf2image` requires Poppler to convert PDFs to images:

#### macOS
```bash
brew install poppler
```

#### Ubuntu/Debian
```bash
sudo apt-get install poppler-utils
```

#### Windows
1. Download Poppler from: http://blog.alivate.com.au/poppler-windows/
2. Extract and add to PATH, or specify the path:
   ```python
   from pdf2image import convert_from_path
   images = convert_from_path('file.pdf', poppler_path=r'C:\path\to\poppler\bin')
   ```

## Usage

OCR is automatically used as a fallback when:
1. Regular PDF extraction (PyPDF) fails
2. AWS Textract fails or is unavailable

No additional configuration is needed - the system will automatically try OCR if both previous methods fail.

## Configuration

You can configure OCR settings when initializing the PDFLoader:

```python
from ingestion.pdf_loader import PDFLoader

# Higher DPI = better quality but slower processing
pdf_loader = PDFLoader(ocr_dpi=300)  # Default is 300
```

## Troubleshooting

### "Tesseract OCR is not installed"
- Make sure Tesseract is installed on your system
- Verify installation: `tesseract --version`
- On Windows, you may need to specify the path to tesseract.exe

### "pdf2image is required for OCR"
- Install pdf2image: `pip install pdf2image`
- Make sure Poppler is installed on your system

### "Poppler not found"
- Install Poppler utilities (see installation instructions above)
- On Windows, add Poppler to your PATH or specify the path in code

### OCR is slow
- Reduce the DPI setting (e.g., `ocr_dpi=200` instead of 300)
- Note: Lower DPI may reduce accuracy

### OCR accuracy is poor
- Increase the DPI setting (e.g., `ocr_dpi=400`)
- Ensure the PDF pages are clear and not too blurry
- Some PDFs may have inherent quality issues that OCR cannot overcome

## How It Works

1. **Regular Extraction**: Tries PyPDF first (fastest, works for text-based PDFs)
2. **Textract Fallback**: If regular extraction fails, tries AWS Textract (good for scanned PDFs)
3. **OCR Fallback**: If both fail, converts PDF to images and uses Tesseract OCR (slowest but most compatible)

The system automatically selects the best available method and falls back gracefully.

