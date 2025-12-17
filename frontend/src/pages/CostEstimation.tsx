/**
 * Cost Estimation Page
 * Form to input items and get cost estimates
 */
import React, { useState } from 'react';
import logo from '../assets/homeguard-incorporated-logo.png';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Chip,
  InputAdornment,
  IconButton,
  Alert,
  CircularProgress,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Stepper,
  Step,
  StepLabel,
  Card,
  CardContent,
  Divider,
  Grid,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Send as SendIcon,
  Edit as EditIcon,
  Save as SaveIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import { estimateService } from '../services/estimate.service';
import { EstimationFormData, ItemDetail } from '../types/api.types';
import ReviewEstimateForm from '../components/ReviewEstimateForm';

const CATEGORIES = [
  'Home inspection',
  'Termite inspection',
  'Roof inspection',
  'Sewer inspection',
  'NHD Inspection',
];

const steps = ['Enter Details', 'Review Estimates', 'Saved'];

const CostEstimation: React.FC = () => {
  // Step management
  const [activeStep, setActiveStep] = useState(0);

  // Form data
  const [formData, setFormData] = useState<EstimationFormData>({
    items: [''],
    category: 'Home inspection',
    zipcode: '',
    address: '',
    username: '',
  });

  // Current item input
  const [currentItem, setCurrentItem] = useState('');

  // Estimate results
  const [estimateData, setEstimateData] = useState<any>(null);
  const [editableItems, setEditableItems] = useState<ItemDetail[]>([]);

  // UI states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Add item to list
  const handleAddItem = () => {
    if (currentItem.trim()) {
      setFormData((prev) => ({
        ...prev,
        items: [...prev.items.filter((item) => item.trim()), currentItem.trim()],
      }));
      setCurrentItem('');
    }
  };

  // Remove item from list
  const handleRemoveItem = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      items: prev.items.filter((_, i) => i !== index),
    }));
  };

  // Handle form field changes
  const handleFieldChange = (field: keyof EstimationFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  // Submit for estimation
  const handleGetEstimate = async () => {
    setError(null);
    setSuccess(null);

    // Validation
    const validItems = formData.items.filter((item) => item.trim());
    if (validItems.length === 0) {
      setError('Please add at least one item');
      return;
    }
    if (!formData.zipcode || formData.zipcode.trim().length < 5) {
      setError('Please enter a valid zipcode (minimum 5 characters)');
      return;
    }
    if (!formData.address || !formData.address.trim()) {
      setError('Please enter the property address');
      return;
    }
    if (!formData.username || !formData.username.trim()) {
      setError('Please enter your username');
      return;
    }
    if (!formData.category) {
      setError('Please select a category');
      return;
    }

    setLoading(true);

    try {
      const response = await estimateService.getEstimate({
        query: validItems,
        category: formData.category,
        zipcode: formData.zipcode.trim(),
        address: formData.address.trim(),
        username: formData.username.trim(),
      });

      // Check if response has data
      if (!response.data || !response.data.items || response.data.items.length === 0) {
        setError('Failed to generate estimates. No valid items were processed. Please try again.');
        return;
      }

      setEstimateData(response.data);
      setEditableItems(response.data.items);
      setActiveStep(1);
      
      // Show success with any warnings
      if (response.error && response.error.length > 0) {
        setSuccess('Estimates generated with some warnings. Please review.');
        console.warn('Estimate warnings:', response.error);
      } else {
        setSuccess('Estimates generated successfully!');
      }
      
    } catch (err: any) {
      console.error('Error getting estimates:', err);
      
      // Extract user-friendly error message
      let errorMsg = 'Failed to get estimates. Please try again.';
      
      if (err.userMessage) {
        errorMsg = err.userMessage;
      } else if (err.response?.data?.detail?.message) {
        errorMsg = err.response.data.detail.message;
      } else if (err.response?.data?.message) {
        errorMsg = err.response.data.message;
      } else if (err.message) {
        errorMsg = err.message;
      }
      
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // Save approved estimates
  const handleSaveEstimates = async () => {
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      // Validate that we have estimate data
      if (!estimateData || !editableItems || editableItems.length === 0) {
        setError('No estimates to save. Please generate estimates first.');
        setLoading(false);
        return;
      }

      const saveData = {
        items: [
          {
            id: `inspection-${Date.now()}`,
            category: estimateData.category,
            items: editableItems,
            dateofcreation: estimateData.dateofcreation,
            zipcode: estimateData.zipcode,
            address: estimateData.address,
            username: estimateData.username,
            status: 'approved',
          },
        ],
      };

      await estimateService.saveItems(saveData);
      setActiveStep(2);
      setSuccess('Estimates saved successfully!');
    } catch (err: any) {
      console.error('Error saving estimates:', err);
      
      // Extract user-friendly error message
      let errorMsg = 'Failed to save estimates. Please try again.';
      
      if (err.userMessage) {
        errorMsg = err.userMessage;
      } else if (err.response?.data?.detail?.message) {
        errorMsg = err.response.data.detail.message;
      } else if (err.response?.data?.message) {
        errorMsg = err.response.data.message;
      } else if (err.message) {
        errorMsg = err.message;
      }
      
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // Reset form
  const handleReset = () => {
    setFormData({
      items: [''],
      category: 'Home inspection',
      zipcode: '',
      address: '',
      username: '',
    });
    setCurrentItem('');
    setEstimateData(null);
    setEditableItems([]);
    setActiveStep(0);
    setError(null);
    setSuccess(null);
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1200, mx: 'auto' }}>
      {/* Header */}
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 600, color: '#0078d4' }}>
        Cost Estimation
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Enter inspection items to get cost estimates
      </Typography>

      {/* Stepper */}
      <Box sx={{ mb: 4 }}>
        <Stepper activeStep={activeStep}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
      </Box>

      {/* Alerts */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {/* Step 0: Input Form */}
      {activeStep === 0 && (
        <Paper elevation={0} sx={{ p: 4, border: '1px solid #e0e0e0' }}>
          {/* Basic Info Grid */}
          <Grid container spacing={3}>
            {/* Category */}
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Category *</InputLabel>
                <Select
                  value={formData.category}
                  onChange={(e) => handleFieldChange('category', e.target.value)}
                  label="Category *"
                >
                  {CATEGORIES.map((cat) => (
                    <MenuItem key={cat} value={cat}>
                      {cat}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            {/* Username */}
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Username *"
                value={formData.username}
                onChange={(e) => handleFieldChange('username', e.target.value)}
                placeholder="Enter username"
              />
            </Grid>

            {/* Zipcode */}
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Zipcode *"
                value={formData.zipcode}
                onChange={(e) => handleFieldChange('zipcode', e.target.value)}
                placeholder="e.g., 94551"
              />
            </Grid>

            {/* Address */}
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Address *"
                value={formData.address}
                onChange={(e) => handleFieldChange('address', e.target.value)}
                placeholder="Enter full address"
              />
            </Grid>
          </Grid>

          {/* Inspection Items Section - Full Width Outside Grid */}
          <Box sx={{ mt: 4 }}>
            <Divider sx={{ mb: 3 }} />
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
              <Box
                component="img"
                src={logo}
                alt="HomeGuard Logo"
                sx={{
                  height: 28,
                  width: 28,
                  objectFit: 'contain',
                }}
              />
              <Typography variant="h6" sx={{ fontWeight: 600, color: '#0078d4' }}>
                Inspection Items
              </Typography>
            </Box>

            <TextField
              fullWidth
              label="Add Item"
              value={currentItem}
              onChange={(e) => setCurrentItem(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleAddItem()}
              placeholder="e.g., Fungus damage was noted to the rafter tail"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton onClick={handleAddItem} color="primary">
                      <AddIcon />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              sx={{ mb: 2 }}
            />

            {/* Display items */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 3 ,height:"100%"}}>
              {formData.items
                .filter((item) => item.trim())
                .map((item, index) => (
                  <Chip
                    key={index}
                    label={item}
                    onDelete={() => handleRemoveItem(index)}
                    deleteIcon={<DeleteIcon />}
                    sx={{ 
                      width: '100%',
                      height: 'auto',
                      padding: '5px',
                      justifyContent: 'space-between',
                      '& .MuiChip-label': {
                        display: 'block',
                        whiteSpace: 'normal',
                        textAlign: 'left',
                        textWrap: 'wrap'
                      }
                    }}
                  />
                ))}
            </Box>

            {/* Submit Button at the bottom */}
            <Button
              fullWidth
              variant="contained"
              size="large"
              onClick={handleGetEstimate}
              disabled={loading}
              startIcon={loading ? <CircularProgress size={20} /> : <SendIcon />}
              sx={{
                mt: 2,
                py: 1.5,
                bgcolor: '#0078d4',
                '&:hover': { bgcolor: '#106ebe' },
              }}
            >
              {loading ? 'Processing...' : 'Get Estimates'}
            </Button>
          </Box>
        </Paper>
      )}

      {/* Step 1: Review and Edit */}
      {activeStep === 1 && estimateData && (
        <ReviewEstimateForm
          estimateData={estimateData}
          editableItems={editableItems}
          onItemsChange={setEditableItems}
          onSave={handleSaveEstimates}
          onCancel={handleReset}
          loading={loading}
        />
      )}

      {/* Step 2: Success */}
      {activeStep === 2 && (
        <Paper elevation={0} sx={{ p: 6, border: '1px solid #e0e0e0', textAlign: 'center' }}>
          <CheckCircleIcon sx={{ fontSize: 80, color: '#107c10', mb: 2 }} />
          <Typography variant="h5" gutterBottom sx={{ fontWeight: 600 }}>
            Estimates Saved Successfully!
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
            Your cost estimates have been approved and saved to the database.
          </Typography>
          <Button
            variant="contained"
            size="large"
            onClick={handleReset}
            sx={{
              px: 4,
              bgcolor: '#0078d4',
              '&:hover': { bgcolor: '#106ebe' },
            }}
          >
            Create New Estimate
          </Button>
        </Paper>
      )}
    </Box>
  );
};

export default CostEstimation;
