import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import logo from './assets/amid-logo.png';
import Button from '@mui/material/Button';
import Input from '@mui/material/Input';
import TextField from '@mui/material/TextField';
import CircularProgress from '@mui/material/CircularProgress';

type Item = {
  product_code: string;
  description: string;
  qty: number;
  rate: number;
  amount: number;
};

const App: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [extractionResult, setExtractionResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showReview, setShowReview] = useState(false);
  const [parsed, setParsed] = useState(false);
  const [formData, setFormData] = useState<{
    customer: string;
    poNumber: string;
    invoiceNumber: string;
    invoiceDate: string;
    dueDate: string;
    items: Item[];
    total: string;
  }>({
    customer: '',
    poNumber: '',
    invoiceNumber: '',
    invoiceDate: '',
    dueDate: '',
    items: [],
    total: '',
  });
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [extractedText, setExtractedText] = useState<string | null>(null);
  const [backendParsed, setBackendParsed] = useState<any>(null);

  const hexToBytes = (hex: string) => {
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < hex.length; i += 2) {
      bytes[i / 2] = parseInt(hex.substr(i, 2), 16);
    }
    return bytes;
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
      setExtractionResult(null);
      setError(null);
    }
  };

  const handleNext = async () => {
    if (!selectedFile) {
      setError('Please select a file before proceeding.');
      return;
    }
    setLoading(true);
    setError(null);
    setExtractedText(null);
    setShowReview(false);
    setParsed(false);
    try {
      const formDataObj = new FormData();
      formDataObj.append('file', selectedFile);
      
      // Call the Python backend upload endpoint
      const response = await fetch('/upload', {
        method: 'POST',
        body: formDataObj,
      });
      
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Extraction failed');
      
      // Set the extracted text and parsed data from Python backend
      setExtractedText(data.raw_text || '');
      setBackendParsed(data);
      setShowReview(true);
      setParsed(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>, idx?: number, field?: string) => {
    if (typeof idx === 'number' && field) {
      // Update item
      const updatedItems = [...formData.items];
      updatedItems[idx] = { ...updatedItems[idx], [field]: e.target.value };
      setFormData({ ...formData, items: updatedItems });
    } else {
      setFormData({ ...formData, [e.target.name]: e.target.value });
    }
  };

  const handleGenerateCertificate = async () => {
    try {
      setLoading(true);
      
      // Call the Python backend to generate certificate
      const response = await fetch('/generate-certificate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData, // Send the whole form
          invoice_number: formData.invoiceNumber,
          date: formData.invoiceDate,
          due_date: formData.dueDate,
          po_number: formData.poNumber,
          vendor_name: formData.customer,
          total_amount: formData.total,
          line_items: formData.items.map(item => ({
            quantity: item.qty,
            description: `${item.product_code || ''} ${item.description || ''}`.trim(),
            rate: item.rate,
            amount: item.amount
          }))
        }),
      });
      
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Certificate generation failed');
      
      // Convert hex data back to PDF blob using browser-safe code
      const pdfBytes = hexToBytes(data.pdf_data);
      const pdfBlob = new Blob([pdfBytes], { type: 'application/pdf' });
      const url = URL.createObjectURL(pdfBlob);
      
      // Create a temporary link to trigger the download
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Certificate-${formData.invoiceNumber || 'invoice'}.pdf`);
      document.body.appendChild(link);
      link.click();
      
      // Clean up the temporary link and URL
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Parse button handler: use backendParsed to fill formData
  const handleParse = async () => {
    if (!backendParsed) return;
    
    try {
      // Use the parsed data from the Python backend
      setFormData({
        customer: backendParsed.vendor_name || '',
        poNumber: backendParsed.po_number || '',
        invoiceNumber: backendParsed.invoice_number || '',
        invoiceDate: backendParsed.date || '',
        dueDate: backendParsed.due_date || '',
        items: (backendParsed.line_items || []).map((item: any) => ({
          product_code: item.product_code || '',
          description: item.description || '',
          qty: parseInt(item.quantity, 10) || 0,
          rate: parseFloat(item.rate) || 0,
          amount: parseFloat(item.amount) || 0,
        })),
        total: backendParsed.total_amount || '',
      });
      setParsed(true);
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    loading ? (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <CircularProgress color="primary" />
        <Typography variant="h6" sx={{ mt: 2 }}>Extracting text from invoice...</Typography>
      </Box>
    ) : showReview && !parsed ? (
      <Box sx={{ mt: 6, width: '100%', maxWidth: 1400, mx: 'auto', px: 3, bgcolor: 'background.paper', p: 3, borderRadius: 2, boxShadow: 2, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Box sx={{ width: '100%' }}>
          <Typography variant="h6" color="primary" gutterBottom>
            Extracted Invoice Text (Edit as needed)
          </Typography>
          <TextField
            label="Extracted Text"
            value={extractedText || ''}
            onChange={e => setExtractedText(e.target.value)}
            fullWidth
            multiline
            minRows={16}
            margin="normal"
          />
          <Button
            variant="contained"
            color="primary"
            sx={{ mt: 2 }}
            onClick={handleParse}
          >
            Parse
          </Button>
        </Box>
      </Box>
    ) : parsed ? (
      <Box sx={{ mt: 6, width: '100%', maxWidth: 1600, mx: 'auto', px: 3, bgcolor: 'background.paper', p: 3, borderRadius: 2, boxShadow: 2, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Box sx={{ width: '100%' }}>
          <Typography variant="h6" color="primary" gutterBottom>
            Review & Edit Invoice Data
          </Typography>
          <TextField
            label="Customer"
            name="customer"
            value={formData.customer}
            onChange={handleFormChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="PO Number"
            name="poNumber"
            value={formData.poNumber}
            onChange={handleFormChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="Invoice Number"
            name="invoiceNumber"
            value={formData.invoiceNumber}
            onChange={handleFormChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="Invoice Date"
            name="invoiceDate"
            value={formData.invoiceDate}
            onChange={handleFormChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="Due Date"
            name="dueDate"
            value={formData.dueDate}
            onChange={handleFormChange}
            fullWidth
            margin="normal"
          />
          <Typography variant="subtitle1" sx={{ mt: 3 }}>
            Items
          </Typography>
          {formData.items.map((item, idx) => (
            <Box key={idx} sx={{ display: 'flex', gap: 2, mb: 2, width: '100%' }}>
              <TextField
                label="Product Code"
                value={item.product_code}
                onChange={e => handleFormChange(e, idx, 'product_code')}
                sx={{ width: '30%' }}
              />
              <TextField
                label="Description"
                value={item.description}
                onChange={e => handleFormChange(e, idx, 'description')}
                sx={{ flexGrow: 1 }}
              />
              <TextField
                label="Qty"
                name="qty"
                type="number"
                value={item.qty}
                onChange={e => handleFormChange(e, idx, 'qty')}
                sx={{ width: '120px' }}
              />
              <TextField
                label="Rate"
                name="rate"
                type="number"
                value={item.rate}
                onChange={e => handleFormChange(e, idx, 'rate')}
                sx={{ width: '150px' }}
              />
              <TextField
                label="Amount"
                name="amount"
                type="number"
                value={item.amount}
                onChange={e => handleFormChange(e, idx, 'amount')}
                sx={{ width: '150px' }}
              />
            </Box>
          ))}
          <Button
            variant="outlined"
            onClick={() => setFormData({
              ...formData,
              items: [
                ...formData.items,
                { product_code: '', description: '', qty: 0, rate: 0, amount: 0 },
              ],
            })}
          >
            ADD PRODUCT
          </Button>
          <TextField
            label="Total"
            name="total"
            value={formData.total}
            onChange={handleFormChange}
            fullWidth
            margin="normal"
          />
          <Button
            variant="contained"
            color="primary"
            sx={{ mt: 3, minWidth: 180 }}
            onClick={handleGenerateCertificate}
          >
            Generate Certificate
          </Button>
          {pdfUrl && (
            <Box sx={{ mt: 3 }}>
              <Button
                variant="outlined"
                color="secondary"
                href={pdfUrl}
                download="certificate.pdf"
                target="_blank"
              >
                Download Certificate
              </Button>
            </Box>
          )}
        </Box>
      </Box>
    ) : (
      <Container maxWidth="sm" sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', bgcolor: 'background.default' }}>
        <Box sx={{ mb: 3 }}>
          <img src={logo} alt="Amid Technologies Logo" style={{ width: 120, height: 'auto' }} />
        </Box>
        <Typography variant="h4" component="h1" color="primary" gutterBottom fontWeight={700}>
          Amid Technologies
        </Typography>
        <Typography variant="h6" color="secondary" gutterBottom>
          Invoice to Certificate of Compliance Generator
        </Typography>
        <Typography variant="body1" color="text.secondary" align="center" sx={{ mt: 2 }}>
          Upload your invoice to extract all required information and generate a professional Certificate of Compliance PDF. <br />
          Batch processing, template management, and more coming soon.
        </Typography>
        <Box sx={{ mt: 6, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Input
            type="file"
            inputProps={{ accept: '.pdf,image/*' }}
            onChange={handleFileChange}
            sx={{ display: 'none' }}
            id="invoice-upload"
          />
          <label htmlFor="invoice-upload">
            <Button variant="contained" color="primary" component="span">
              Upload Invoice
            </Button>
          </label>
          {selectedFile && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Selected file: {selectedFile.name}
            </Typography>
          )}
          <Button
            variant="outlined"
            color="primary"
            sx={{ mt: 3, minWidth: 120 }}
            onClick={handleNext}
            disabled={!selectedFile}
          >
            Next
          </Button>
          {extractionResult && (
            <Box sx={{ mt: 4, p: 2, border: '1px solid', borderColor: 'grey.300', borderRadius: 2, width: '100%' }}>
              <Typography variant="subtitle1" color="primary" gutterBottom>
                Extraction Result
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {extractionResult}
              </Typography>
            </Box>
          )}
          {error && (
            <Typography variant="body2" color="error" sx={{ mt: 2 }}>
              {error}
            </Typography>
          )}
        </Box>
      </Container>
    )
  );
};

export default App;
