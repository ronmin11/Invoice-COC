# Python Backend Setup

This backend uses Python with FastAPI for better OCR and invoice processing capabilities.

## Prerequisites

1. **Python 3.8+** installed on your system
2. **Tesseract OCR** installed on your system
   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - Install to `C:\Program Files\Tesseract-OCR\`
   - Add to PATH or uncomment the tesseract path in main.py

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. If you're on Windows and Tesseract is not in PATH, uncomment this line in main.py:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

## Running the Server

### Option 1: Direct Python
```bash
python main.py
```

### Option 2: Using uvicorn directly
```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

### Option 3: From root directory
```bash
npm run server
```

## API Endpoints

- `GET /` - Health check
- `POST /upload` - Upload and process invoice files
- `POST /generate-certificate` - Generate compliance certificate PDF

## Features

- **Better OCR**: Uses pytesseract with OpenCV preprocessing
- **PDF Processing**: Supports both text-based and image-based PDFs
- **Advanced Parsing**: Regex-based invoice field extraction
- **PDF Generation**: Professional certificate generation with ReportLab
- **Error Handling**: Comprehensive error handling and logging

## Troubleshooting

1. **Tesseract not found**: Install Tesseract and update the path in main.py
2. **PDF processing errors**: Install poppler-utils (Windows: download from https://github.com/oschwartz10612/poppler-windows/releases/)
3. **Import errors**: Make sure all requirements are installed with `pip install -r requirements.txt` 