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
  Chip,
  Stack,
  Typography,
  Alert,
} from '@mui/material';
import { Close as CloseIcon, Add as AddIcon } from '@mui/icons-material';
import { estimateService } from '../services/estimate.service';

interface AddEditClusterDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: ClusterFormData) => Promise<void>;
  editData?: ClusterFormData | null;
  mode: 'add' | 'edit';
}

export interface ClusterFormData {
  id?: string;
  name: string;
  zipcodes: string[];
  description?: string;
}

const AddEditClusterDialog: React.FC<AddEditClusterDialogProps> = ({
  open,
  onClose,
  onSubmit,
  editData,
  mode,
}) => {
  const [formData, setFormData] = useState<ClusterFormData>({
    name: '',
    zipcodes: [],
    description: '',
  });
  const [zipcodeInput, setZipcodeInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [existingCluster, setExistingCluster] = useState<{
    exists: boolean;
    cluster_id?: string;
    name?: string;
    zipcode_count?: number;
  } | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  useEffect(() => {
    if (open) {
      if (mode === 'edit' && editData) {
        setFormData(editData);
      } else {
        setFormData({
          name: '',
          zipcodes: [],
          description: '',
        });
      }
      setZipcodeInput('');
      setError(null);
      setExistingCluster(null);
      setShowConfirmDialog(false);
    }
  }, [open, mode, editData]);

  const handleAddZipcode = () => {
    const zipcode = zipcodeInput.trim();
    if (!zipcode) return;

    // Basic validation: 5 digits
    if (!/^\d{5}$/.test(zipcode)) {
      setError('Zipcode must be 5 digits');
      return;
    }

    if (formData.zipcodes.includes(zipcode)) {
      setError('Zipcode already added');
      return;
    }

    setFormData({
      ...formData,
      zipcodes: [...formData.zipcodes, zipcode],
    });
    setZipcodeInput('');
    setError(null);
  };

  const handleRemoveZipcode = (zipcode: string) => {
    setFormData({
      ...formData,
      zipcodes: formData.zipcodes.filter((z) => z !== zipcode),
    });
  };

  const handleNameBlur = async () => {
    // Only check for duplicates in 'add' mode and when name is not empty
    if (mode !== 'add' || !formData.name.trim()) {
      setExistingCluster(null);
      return;
    }

    try {
      const result = await estimateService.checkClusterName(formData.name.trim());
      setExistingCluster(result);
    } catch (err) {
      console.error('Failed to check cluster name:', err);
      setExistingCluster(null);
    }
  };

  const handleSubmit = async () => {
    setError(null);

    // Validation
    if (!formData.name.trim()) {
      setError('Cluster name is required');
      return;
    }

    if (formData.zipcodes.length === 0) {
      setError('At least one zipcode is required');
      return;
    }

    // In add mode, check if cluster exists and show confirmation
    if (mode === 'add' && existingCluster?.exists) {
      setShowConfirmDialog(true);
      return;
    }

    // Proceed with save
    await performSave();
  };

  const performSave = async () => {
    setLoading(true);
    try {
      await onSubmit(formData);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save cluster');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmOverwrite = async () => {
    setShowConfirmDialog(false);
    await performSave();
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddZipcode();
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" fontWeight={600}>
            {mode === 'add' ? 'Add New Cluster' : 'Edit Cluster'}
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

          {/* Cluster Name */}
          <Box>
            <TextField
              label="Cluster Name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              onBlur={handleNameBlur}
              fullWidth
              required
              placeholder="Bay Area East"
            />
            {mode === 'add' && existingCluster?.exists && (
              <Alert severity="warning" sx={{ mt: 1 }}>
                Cluster "{existingCluster.name}" already exists with {existingCluster.zipcode_count} zipcode(s). 
                Submitting will replace them with your new zipcodes.
              </Alert>
            )}
          </Box>

          {/* Description */}
          <TextField
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            fullWidth
            multiline
            rows={2}
            placeholder="Optional description of the cluster"
          />

          {/* Zipcode Input */}
          <Box>
            <TextField
              label="Add Zipcode"
              value={zipcodeInput}
              onChange={(e) => setZipcodeInput(e.target.value)}
              onKeyPress={handleKeyPress}
              fullWidth
              placeholder="Enter 5-digit zipcode"
              helperText="Press Enter or click + to add"
              InputProps={{
                endAdornment: (
                  <IconButton
                    onClick={handleAddZipcode}
                    color="primary"
                    disabled={!zipcodeInput.trim()}
                  >
                    <AddIcon />
                  </IconButton>
                ),
              }}
            />
          </Box>

          {/* Zipcode Chips */}
          {formData.zipcodes.length > 0 && (
            <Box>
              <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                Zipcodes ({formData.zipcodes.length}):
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {formData.zipcodes.map((zipcode) => (
                  <Chip
                    key={zipcode}
                    label={zipcode}
                    onDelete={() => handleRemoveZipcode(zipcode)}
                    color="primary"
                    variant="outlined"
                    sx={{ fontFamily: 'monospace' }}
                  />
                ))}
              </Stack>
            </Box>
          )}
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
          {loading ? 'Saving...' : mode === 'add' ? 'Create Cluster' : 'Update Cluster'}
        </Button>
      </DialogActions>

      {/* Confirmation Dialog */}
      <Dialog open={showConfirmDialog} onClose={() => setShowConfirmDialog(false)} maxWidth="xs">
        <DialogTitle>Confirm Update</DialogTitle>
        <DialogContent>
          <Typography>
            Cluster "{existingCluster?.name}" already exists with {existingCluster?.zipcode_count} zipcode(s). 
            Are you sure you want to replace them with your {formData.zipcodes.length} new zipcode(s)?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowConfirmDialog(false)} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirmOverwrite}
            variant="contained"
            color="warning"
            disabled={loading}
          >
            {loading ? 'Updating...' : 'Yes, Update Cluster'}
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  );
};

export default AddEditClusterDialog;

