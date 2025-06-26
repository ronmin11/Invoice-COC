from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pytesseract
import cv2
import numpy as np
from PIL import Image as PILImage
from pdf2image.pdf2image import convert_from_path
import pdfplumber
import re
from datetime import datetime
import os
import tempfile
from typing import Dict, Any, Optional
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
import io
import logging
from reportlab.platypus.flowables import Flowable
from reportlab.platypus import Table, TableStyle, Spacer as RLSpacer
from reportlab.platypus import KeepTogether

app = FastAPI(title="Invoice Certification API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Tesseract path for Windows
try:
    # Try to find Tesseract in common Windows installation paths
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\ronmi\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
    ]
    
    tesseract_found = False
    for path in tesseract_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            tesseract_found = True
            print(f"Tesseract found at: {path}")
            break
    
    if not tesseract_found:
        print("WARNING: Tesseract not found. Please install Tesseract OCR:")
        print("1. Download from: https://github.com/UB-Mannheim/tesseract/wiki")
        print("2. Install to C:\\Program Files\\Tesseract-OCR\\")
        print("3. Add to PATH or update the path in main.py")
        
except Exception as e:
    print(f"Error configuring Tesseract: {e}")

class InvoiceParser:
    def __init__(self):
        self.extracted_data = {}
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Enhance image for better OCR results"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply threshold to get binary image
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Apply morphological operations to clean up
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from image using OCR"""
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError("Could not read image")
            
            # Preprocess image
            processed_image = self.preprocess_image(image)
            
            # OCR configuration for better accuracy
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,$%()/\- '
            
            # Extract text
            text = pytesseract.image_to_string(processed_image, config=custom_config)
            
            return text.strip()
        except Exception as e:
            print(f"Error in OCR: {str(e)}")
            return ""
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using multiple methods"""
        text = ""
        
        try:
            # Method 1: Try pdfplumber first (better for text-based PDFs)
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            # Method 2: If no text found, convert to images and use OCR
            if not text.strip():
                try:
                    images = convert_from_path(pdf_path, dpi=300)
                    for i, image in enumerate(images):
                        # Save image temporarily
                        temp_image_path = f"temp_page_{i}.png"
                        image.save(temp_image_path, "PNG")
                        
                        # Extract text from image
                        page_text = self.extract_text_from_image(temp_image_path)
                        text += page_text + "\n"
                        
                        # Clean up
                        os.remove(temp_image_path)
                except Exception as e:
                    print(f"Error converting PDF to images: {e}")
                    print("You may need to install poppler-utils for PDF processing")
                    
        except Exception as e:
            print(f"Error extracting text from PDF: {str(e)}")
        
        return text.strip()
    
    def parse_invoice_data(self, text: str) -> Dict[str, Any]:
        """Parses the invoice text based on the user's exact structural rules."""
        data = {
            "invoice_number": "", "po_number": "", "date": "", "due_date": "",
            "vendor_name": "", "total_amount": "", "line_items": [], "raw_text": text
        }
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # --- Header and Customer Extraction based on literal text matching ---
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Find customer name on the line after "Bill to Ship to" per user instruction
            if "bill to ship to" in line_lower and i + 1 < len(lines):
                customer_line = lines[i+1]
                # Clean up repeated names like "Company, Inc. Company"
                if ", Inc." in customer_line:
                    data["vendor_name"] = customer_line.split(", Inc.")[0] + ", Inc."
                else:
                    data["vendor_name"] = customer_line
            
            if "invoice details po number:" in line_lower:
                data["po_number"] = line.split(":")[-1].strip()
            if "invoice no.:" in line_lower:
                data["invoice_number"] = line.split(":")[-1].strip()
            if "invoice date:" in line_lower:
                data["date"] = line.split(":")[-1].strip()
            if "due date:" in line_lower:
                data["due_date"] = line.split(":")[-1].strip()
            if line_lower.startswith("total"):
                data["total_amount"] = line.split()[-1]

        # --- Line Item Extraction based on user's rule: last 3 numbers ---
        in_item_section = False
        for line in lines:
            if "product or service" in line.lower() and "qty" in line.lower():
                in_item_section = True
                continue
            if not in_item_section or line.lower().startswith("total") or line.lower().startswith("thank"):
                continue

            # Find all number-like words (including decimals and $)
            all_numbers = re.findall(r"[\d\.,]+", line)
            
            if len(all_numbers) >= 3:
                # Per the user, the last three numbers are Qty, Rate, and Amount
                qty, rate, amount = all_numbers[-3], all_numbers[-2], all_numbers[-1]
                
                # Find where the quantity appears to split description from numbers
                qty_index = line.rfind(qty)
                desc_text = line[:qty_index].strip()
                desc_text = re.sub(r"^\d+\.\s*", "", desc_text) # Remove leading "1. ", etc.

                desc_parts = desc_text.split(" ", 1)
                product_code = desc_parts[0]
                description = desc_parts[1].strip() if len(desc_parts) > 1 else ""
                
                data["line_items"].append({
                    "product_code": product_code,
                    "description": description,
                    "quantity": qty, "rate": rate, "amount": amount
                })
            elif data["line_items"]:
                # This line is likely a multi-line description part
                data["line_items"][-1]["description"] += f" {line.strip()}"
        
        return data

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and process invoice file"""
    try:
        # Create uploads directory if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        
        # Save uploaded file
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Initialize parser
        parser = InvoiceParser()
        
        # Extract text based on file type
        if file.filename and file.filename.lower().endswith('.pdf'):
            extracted_text = parser.extract_text_from_pdf(file_path)
        else:
            extracted_text = parser.extract_text_from_image(file_path)
        
        # Parse invoice data
        invoice_data = parser.parse_invoice_data(extracted_text)
        
        # Clean up uploaded file
        os.remove(file_path)
        
        return JSONResponse(content=invoice_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/generate-certificate")
async def generate_certificate(invoice_data: Dict[str, Any]):
    """Generate a redesigned, professional compliance certificate PDF."""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=0.75*inch, leftMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        story: list[Flowable] = []

        # Calculate total quantity from line items
        total_quantity = 0
        if invoice_data.get("items"):
            for item in invoice_data["items"]:
                try:
                    qty = float(item.get("qty", 0))
                    total_quantity += qty
                except (ValueError, TypeError):
                    pass

        # Extract shipping date (month and year) from due date
        shipping_date = "N/A"
        due_date = invoice_data.get('due_date', '')
        if due_date:
            try:
                # Try to parse the due date and extract month/year
                from datetime import datetime
                # Handle common date formats
                for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%d/%m/%Y']:
                    try:
                        parsed_date = datetime.strptime(due_date, fmt)
                        shipping_date = parsed_date.strftime('%B %Y')
                        break
                    except ValueError:
                        continue
            except Exception:
                shipping_date = "N/A"

        # --- 0. Logo at Top Left, Title/Date Centered on Same Row ---
        logo_path = os.path.join(os.path.dirname(__file__), 'amid-logo.jpeg')
        max_logo_width = 1.2*inch
        max_logo_height = 1.0*inch
        if os.path.exists(logo_path):
            pil_img = PILImage.open(logo_path)
            w, h = pil_img.size
            aspect = w / h
            # Scale proportionally
            logo_width = min(max_logo_width, max_logo_height * aspect)
            logo_height = logo_width / aspect
            if logo_height > max_logo_height:
                logo_height = max_logo_height
                logo_width = logo_height * aspect
            logo_img = Image(logo_path, width=logo_width, height=logo_height)
        else:
            logo_width = max_logo_width
            logo_img = Spacer(logo_width, max_logo_height)

        # --- 1. Title/Date Centered ---
        right_spacer = Spacer(logo_width, max_logo_height)
        page_width = letter[0]
        left_margin = 0.5*inch
        right_margin = 0.75*inch
        printable_width = page_width - left_margin - right_margin
        center_col_width = printable_width - 2 * logo_width
        header_right_style = ParagraphStyle(name='HeaderRight', parent=styles['Normal'], alignment=TA_CENTER, fontSize=14, leading=16)
        header_right_text = f"<b>Certificate of Compliance</b><br/><b>Date: {invoice_data.get('date', 'N/A')}</b>"
        header_para = Paragraph(header_right_text, header_right_style)
        header_para_box = [RLSpacer(1, 0.3*inch), header_para]
        header_table = Table(
            [[logo_img, header_para_box, right_spacer]],
            colWidths=[logo_width, center_col_width, logo_width],
            hAlign='LEFT'
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (0, 0), 'TOP'),
            ('VALIGN', (1, 0), (1, 0), 'TOP'),
            ('VALIGN', (2, 0), (2, 0), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.5*inch))

        # --- 2. Customer and PO Details ---
        details_style = ParagraphStyle(name='DetailsStyle', parent=styles['Normal'], spaceAfter=6)
        story.append(Paragraph(f"<b>Customer:</b> {invoice_data.get('vendor_name', 'N/A')}", details_style))
        story.append(Paragraph(f"<b>Customer Purchase Order No:</b> {invoice_data.get('po_number', 'N/A')}", details_style))
        story.append(Paragraph(f"<b>Customer Purchase Number:</b> {invoice_data.get('customer_purchase_number', 'N/A')}", details_style))
        story.append(Paragraph(f"<b>Shipping Date:</b> {shipping_date}", details_style))
        story.append(Paragraph(f"<b>Total Quantity:</b> {total_quantity:,.0f}", details_style))
        story.append(Spacer(1, 0.25*inch))
        
        # --- 3. Certification Text (Part 1) ---
        body_style = ParagraphStyle(name='BodyStyle', parent=styles['Normal'], spaceAfter=12)
        certification_text = (
            "We certify that all materials, and products listed below have been assembled, produced, "
            "inspected, and tested in full accordance with all applicable specifications, drawings, and "
            "other purchase requirements. Test reports and/or suitable evidence of compliance are on file "
            "and are available from the manufacturer. "
            "Amid Technologies has established a known chain of custody for the material originating from the OEM."
        )
        story.append(Paragraph(certification_text, body_style))
        story.append(Spacer(1, 0.25*inch))

        # --- 4. Line Items Table (Single Table Format) ---
        product_table_data = [
            [
                Paragraph('<b>Product Code</b>', styles['Normal']),
                Paragraph('<b>Description</b>', styles['Normal']),
                Paragraph('<b>Quantity</b>', styles['Normal']),
                Paragraph('<b>Date Code</b>', styles['Normal'])
            ]
        ]
        if invoice_data.get("items"):
            for item in invoice_data["items"]:
                product_table_data.append([
                    Paragraph(item.get("product_code", ""), styles['Normal']),
                    Paragraph(item.get("description", ""), styles['Normal']),
                    Paragraph(f"{item.get('qty', 0):,}", styles['Normal']),
                    Paragraph(item.get("date_code", ""), styles['Normal'])
                ])
        product_table = Table(product_table_data, colWidths=[2.2*inch, 3.2*inch, 1.0*inch, 1.1*inch], hAlign='LEFT')
        product_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            ('ALIGN', (0, 1), (1, -1), 'LEFT'),
            ('ALIGN', (3, 1), (3, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(product_table)
        story.append(Spacer(1, 0.25*inch))

        # --- 5. Signature Block ---
        signature_style = ParagraphStyle(name='SignatureStyle', parent=styles['Normal'], alignment=TA_CENTER, spaceAfter=0, spaceBefore=0, leading=10)
        # Use a single table for the signature block to control spacing tightly
        signature_table = Table([
            [Paragraph("Dima Minin", signature_style)],
            [Paragraph("____________________________", signature_style)],
            [Paragraph("Amid Technologies Inc", signature_style)],
            [Paragraph("<b>Manufacturer's Representative</b>", signature_style)]
        ], colWidths=[3*inch], hAlign='CENTER', style=TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('TOPPADDING', (0, 0), (0, 0), 0),
            ('BOTTOMPADDING', (0, 0), (0, 0), 0),
            ('TOPPADDING', (0, 1), (0, 1), 0),
            ('BOTTOMPADDING', (0, 1), (0, 1), 0),
            ('TOPPADDING', (0, 2), (0, 2), 6),
            ('BOTTOMPADDING', (0, 2), (0, 2), 0),
            ('TOPPADDING', (0, 3), (0, 3), 0),
            ('BOTTOMPADDING', (0, 3), (0, 3), 0),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        signature_block = [
            Spacer(1, 0.25*inch),  # Move signature block further down
            signature_table,
            Spacer(1, 0.1*inch)
        ]

        # --- 6. Assemble Story with Conditional KeepTogether ---
        if len(product_table_data) <= 5:  # 1 header + 4 products
            story_content = story + signature_block
            story = [KeepTogether(story_content)]
        else:
            story.extend(signature_block)

        doc.build(story)
        buffer.seek(0)
        
        return JSONResponse(
            content={"pdf_data": buffer.getvalue().hex()},
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logging.error(f"Failed to generate certificate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating certificate: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Invoice Certification API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 