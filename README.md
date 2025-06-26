# Invoice Certificate Generator Web App

A professional web application for businesses to extract invoice data, review/edit it, and generate downloadable Certificates of Compliance (CoC) in PDF format. Supports multiple invoice templates, companies, batch processing, and admin dashboard for template management.

## Features
- Upload invoices (PDF/image), extract and review data
- Edit/correct extracted fields before generating CoC
- Download professional, company-branded certificates as PDF
- Batch processing for multiple invoices
- Admin dashboard for template and company management
- User authentication and data security
- Clean, modern UI with company branding/colors

## Tech Stack
- Frontend: React (TypeScript), Tailwind CSS
- Backend: Node.js (Express)
- Database: PostgreSQL
- OCR: Tesseract.js or cloud OCR
- PDF Generation: pdf-lib/jsPDF

## Getting Started
1. Clone the repo and install dependencies for both `client` and `server`:
   ```sh
   cd InvoiceCertApp
   cd client && npm install
   cd ../server && npm install
   ```
2. Start the backend:
   ```sh
   cd server
   npm start
   ```
3. Start the frontend:
   ```sh
   cd client
   npm start
   ```

## Folder Structure
```
InvoiceCertApp/
  client/   # React frontend
  server/   # Express backend
```

---

## License
MIT 