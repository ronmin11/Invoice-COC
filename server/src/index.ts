import express from 'express';
import cors from 'cors';
import multer from 'multer';
// @ts-ignore
import Tesseract from 'tesseract.js';
import fs from 'fs';
import path from 'path';
import { PDFDocument } from 'pdf-lib';
import sharp from 'sharp';
// @ts-ignore
import { convert } from 'pdf-poppler';
import { Request } from 'express';

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

const upload = multer({ dest: 'uploads/' });

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Helper function to parse Amid Technologies invoice OCR text
function parseAmidInvoice(text: string) {
  // Extract fields using regex and line matching
  const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  const result: any = {
    invoiceNumber: '',
    poNumber: '',
    terms: '',
    invoiceDate: '',
    dueDate: '',
    total: '',
    products: [] as any[],
    billTo: '',
    shipTo: '',
    raw: text
  };

  // Extract fields
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/PO number[:\s]*([\d]+)/i.test(line)) {
      result.poNumber = line.match(/PO number[:\s]*([\d]+)/i)?.[1] || '';
    }
    if (/Invoice no\.?[:\s]*([\d]+)/i.test(line)) {
      result.invoiceNumber = line.match(/Invoice no\.?[:\s]*([\d]+)/i)?.[1] || '';
    }
    if (/Terms[:\s]*(.+)/i.test(line)) {
      result.terms = line.match(/Terms[:\s]*(.+)/i)?.[1] || '';
    }
    if (/Invoice date[:\s]*([\d/]+)/i.test(line)) {
      result.invoiceDate = line.match(/Invoice date[:\s]*([\d/]+)/i)?.[1] || '';
    }
    if (/Due date[:\s]*([\d/]+)/i.test(line)) {
      result.dueDate = line.match(/Due date[:\s]*([\d/]+)/i)?.[1] || '';
    }
    if (/Total\s*\$([\d.,]+)/i.test(line)) {
      result.total = line.match(/Total\s*\$([\d.,]+)/i)?.[1] || '';
    }
    // Bill to and Ship to
    if (line.toLowerCase().startsWith('po box')) {
      result.billTo = lines.slice(i, i+3).join(' ');
    }
    if (line.toLowerCase().includes('sun valley')) {
      result.shipTo = lines.slice(i-1, i+2).join(' ');
    }
  }

  // Extract products table
  let productStart = lines.findIndex(l => l.match(/^#?\s*Product/));
  if (productStart === -1) productStart = lines.findIndex(l => l.match(/^1\./));
  if (productStart !== -1) {
    for (let i = productStart + 1; i < lines.length; i++) {
      const line = lines[i];
      // Product lines start with a number and a dot
      if (/^\d+\./.test(line)) {
        // Try to split line into parts: code, description, qty, rate, amount
        // Fallback: just code and description
        const parts = line.split(/\s{2,}|\t| {5,}/).filter(Boolean);
        // Try to extract code and description
        const codeMatch = line.match(/^[\d.]+\s*([A-Z0-9,\-]+)\s/);
        let code = '';
        if (codeMatch) {
          code = codeMatch[1];
        } else {
          // fallback: first word after number
          code = line.split(' ')[1] || '';
        }
        // Description: everything after code
        let desc = line.replace(/^\d+\.\s*[A-Z0-9,\-]+\s*/, '');
        // Try to extract qty, rate, amount if present
        let qty = '', rate = '', amount = '';
        const amtMatch = line.match(/\$([\d.,]+)$/);
        if (amtMatch) amount = amtMatch[1];
        // Add to products
        result.products.push({ code, description: desc, qty, rate, amount });
      } else if (/^Total/i.test(line)) {
        break;
      }
    }
  }
  return result;
}

app.post('/api/extract', upload.single('file'), async (req: Request, res) => {
  const file = req.file as Express.Multer.File;
  if (!file) {
    return res.status(400).json({ error: 'No file uploaded' });
  }
  const filePath = path.resolve(file.path);
  try {
    let text = '';
    if (file.mimetype === 'application/pdf') {
      // Convert PDF to images using pdf-poppler
      const outputDir = path.join('uploads', `pdf_${Date.now()}`);
      fs.mkdirSync(outputDir);
      const options = {
        format: 'png',
        out_dir: outputDir,
        out_prefix: 'page',
        page: null,
      };
      await convert(filePath, options);
      // OCR each page image
      const files = fs.readdirSync(outputDir).filter(f => f.endsWith('.png'));
      let allText = '';
      for (const imgFile of files) {
        const imgPath = path.join(outputDir, imgFile);
        const result = await Tesseract.recognize(imgPath, 'eng');
        allText += result.data.text + '\n';
        fs.unlinkSync(imgPath);
      }
      fs.rmdirSync(outputDir);
      fs.unlinkSync(filePath);
      text = allText;
    } else {
      // Only process images for now
      const result = await Tesseract.recognize(filePath, 'eng');
      text = result.data.text;
      fs.unlinkSync(filePath);
    }
    res.json({ text, parsed: parseAmidInvoice(text) });
  } catch (err) {
    console.error('OCR error:', err);
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
    res.status(500).json({ error: 'OCR failed', details: (err as any).message });
  }
});

app.post('/api/parse-text', express.json(), (req, res) => {
  const { text } = req.body;
  if (!text) return res.status(400).json({ error: 'No text provided' });
  const parsed = parseAmidInvoice(text);
  res.json({ parsed });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
}); 