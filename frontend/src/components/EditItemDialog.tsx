import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  IconButton,
  Stack,
  Typography,
  Alert,
} from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';

interface EditItemDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: EditItemFormData) => Promise<void>;
  editData: any;
}

export interface EditItemFormData {
  message: string;
  min_estimate: number;
  max_estimate: number;
}

const EditItemDialog: React.FC<EditItemDialogProps> = ({
  open,
  onClose,
  onSubmit,
  editData,
}) => {
  const [formData, setFormData] = useState<EditItemFormData>({
    message: '',
    min_estimate: 0,
    max_estimate: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && editData) {
      setFormData({
        message: editData.message || '',
        min_estimate: editData.min_estimate || 0,
        max_estimate: editData.max_estimate || 0,
      });
      setError(null);
    }
  }, [open, editData]);

  const handleSubmit = async () => {
    setError(null);

    // Validation
    if (!formData.message.trim()) {
      setError('Message is required');
      return;
    }

    if (formData.min_estimate < 0) {
      setError('Minimum estimate must be non-negative');
      return;
    }

    if (formData.max_estimate < 0) {
      setError('Maximum estimate must be non-negative');
      return;
    }

    if (formData.min_estimate > formData.max_estimate) {
      setError('Minimum estimate cannot be greater than maximum estimate');
      return;
    }

    setLoading(true);
    try {
      await onSubmit(formData);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to update item');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" fontWeight={600}>
            Edit Saved Item
          </Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        <Stack spacing={3}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {/* Message */}
          <TextField
            label="Message / Description"
            value={formData.message}
            onChange={(e) => setFormData({ ...formData, message: e.target.value })}
            fullWidth
            required
            multiline
            rows={3}
            placeholder="Enter item description"
          />

          {/* Min Estimate */}
          <TextField
            label="Minimum Estimate ($)"
            type="number"
            value={formData.min_estimate}
            onChange={(e) => setFormData({ ...formData, min_estimate: parseFloat(e.target.value) || 0 })}
            fullWidth
            required
            inputProps={{ min: 0, step: 0.01 }}
          />

          {/* Max Estimate */}
          <TextField
            label="Maximum Estimate ($)"
            type="number"
            value={formData.max_estimate}
            onChange={(e) => setFormData({ ...formData, max_estimate: parseFloat(e.target.value) || 0 })}
            fullWidth
            required
            inputProps={{ min: 0, step: 0.01 }}
          />
        </Stack>
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading}
          sx={{
            bgcolor: 'primary.main',
            '&:hover': { bgcolor: 'primary.dark' },
          }}
        >
          {loading ? 'Updating...' : 'Update Item'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EditItemDialog;
