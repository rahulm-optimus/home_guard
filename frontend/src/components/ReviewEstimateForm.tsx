/**
 * Review Estimate Form Component
 * Allows editing of estimate values before saving
 */
import React from 'react';
import {
    Box,
    Paper,
    Typography,
    TextField,
    Button,
    Card,
    CardContent,
    Grid,
    Chip,
} from '@mui/material';
import { Save as SaveIcon, Cancel as CancelIcon } from '@mui/icons-material';
import { ItemDetail } from '../types/api.types';

interface ReviewEstimateFormProps {
    estimateData: any;
    editableItems: ItemDetail[];
    onItemsChange: (items: ItemDetail[]) => void;
    onSave: () => void;
    onCancel: () => void;
    loading: boolean;
}

const ReviewEstimateForm: React.FC<ReviewEstimateFormProps> = ({
    estimateData,
    editableItems,
    onItemsChange,
    onSave,
    onCancel,
    loading,
}) => {
    const handleItemChange = (index: number, field: keyof ItemDetail, value: any) => {
        const updated = [...editableItems];
        if (field === 'estimate') {
            updated[index] = { ...updated[index], estimate: value };
        } else {
            updated[index] = { ...updated[index], [field]: value };
        }
        onItemsChange(updated);
    };

    const calculateTotal = () => {
        const minTotal = editableItems.reduce((sum, item) => sum + item.estimate.min, 0);
        const maxTotal = editableItems.reduce((sum, item) => sum + item.estimate.max, 0);
        return { min: minTotal, max: maxTotal };
    };

    const totals = calculateTotal();

    return (
        <Box>
            {/* Header Info */}
            <Paper elevation={0} sx={{ p: 3, mb: 3, border: '1px solid #e0e0e0' }}>
                <Grid container spacing={2}>
                    <Grid item xs={12} md={3}>
                        <Typography variant="caption" color="text.secondary">
                            Category
                        </Typography>
                        <Typography variant="body1" sx={{ fontWeight: 500 }}>
                            {estimateData.category}
                        </Typography>
                    </Grid>
                    <Grid item xs={12} md={3}>
                        <Typography variant="caption" color="text.secondary">
                            Username
                        </Typography>
                        <Typography variant="body1" sx={{ fontWeight: 500 }}>
                            {estimateData.username}
                        </Typography>
                    </Grid>
                    <Grid item xs={12} md={3}>
                        <Typography variant="caption" color="text.secondary">
                            Zipcode
                        </Typography>
                        <Typography variant="body1" sx={{ fontWeight: 500 }}>
                            {estimateData.zipcode}
                        </Typography>
                    </Grid>
                    <Grid item xs={12} md={3}>
                        <Typography variant="caption" color="text.secondary">
                            Date
                        </Typography>
                        <Typography variant="body1" sx={{ fontWeight: 500 }}>
                            {estimateData.dateofcreation}
                        </Typography>
                    </Grid>
                    {/* <Grid item xs={12}>
                        <Typography variant="caption" color="text.secondary">
                            Address
                        </Typography>
                        <Typography variant="body1" sx={{ fontWeight: 500 }}>
                            {estimateData.address}
                        </Typography>
                    </Grid> */}
                </Grid>
            </Paper>

            {/* Editable Items */}
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 500, mb: 2 }}>
                Review and Edit Estimates
            </Typography>

            {editableItems.map((item, index) => (
                <Card
                    key={index}
                    sx={{
                        mb: 2,
                        border: '1px solid #e0e0e0',
                        boxShadow: 'none',
                        '&:hover': { boxShadow: 2 },
                    }}
                >
                    <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                            <Typography variant="subtitle1" sx={{ fontWeight: 500, flex: 1 }}>
                                Item {index + 1}
                            </Typography>
                            <Chip label={item.subcategory} size="small" color="primary" variant="outlined" />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                            <TextField
                                multiline
                                minRows={2}
                                maxRows={10}
                                fullWidth
                                label="Description"
                                value={item.description}
                                onChange={(e) =>
                                    handleItemChange(index, "description", e.target.value)
                                }

                            />
                        </Box>

                        <Grid container spacing={2}>
                            {/* NEXT ROW */}
                            <Grid item xs={12} md={6}>
                                <TextField
                                    fullWidth
                                    label="Subcategory"
                                    value={item.subcategory}
                                    onChange={(e) =>
                                        handleItemChange(index, "subcategory", e.target.value)
                                    }
                                    size="small"
                                />
                            </Grid>

                            <Grid item xs={6} md={3}>
                                <TextField
                                    fullWidth
                                    label="Min Estimate ($)"
                                    type="number"
                                    value={item.estimate.min}
                                    onChange={(e) =>
                                        handleItemChange(index, "estimate", {
                                            ...item.estimate,
                                            min: parseFloat(e.target.value) || 0,
                                        })
                                    }
                                    size="small"
                                    inputProps={{ step: 50, min: 0 }}
                                />
                            </Grid>

                            <Grid item xs={6} md={3}>
                                <TextField
                                    fullWidth
                                    label="Max Estimate ($)"
                                    type="number"
                                    value={item.estimate.max}
                                    onChange={(e) =>
                                        handleItemChange(index, "estimate", {
                                            ...item.estimate,
                                            max: parseFloat(e.target.value) || 0,
                                        })
                                    }
                                    size="small"
                                    inputProps={{ step: 50, min: 0 }}
                                />
                            </Grid>
                        </Grid>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2, mt: 2 }}>
                            <TextField
                                fullWidth
                                label="Note"
                                value={item.note}
                                onChange={(e) => handleItemChange(index, "note", e.target.value)}
                                size="small"
                            />
                        </Box>
                    </CardContent>
                </Card>
            ))}

            {/* Total */}
            <Paper elevation={0} sx={{ p: 3, mb: 3, border: '2px solid #0078d4', bgcolor: '#f3f9fd' }}>
                <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={6}>
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                            Total Estimate Range
                        </Typography>
                    </Grid>
                    <Grid item xs={6} md={3}>
                        <Typography variant="caption" color="text.secondary">
                            Minimum
                        </Typography>
                        <Typography variant="h5" sx={{ fontWeight: 600, color: '#107c10' }}>
                            ${totals.min.toLocaleString()}
                        </Typography>
                    </Grid>
                    <Grid item xs={6} md={3}>
                        <Typography variant="caption" color="text.secondary">
                            Maximum
                        </Typography>
                        <Typography variant="h5" sx={{ fontWeight: 600, color: '#d83b01' }}>
                            ${totals.max.toLocaleString()}
                        </Typography>
                    </Grid>
                </Grid>
            </Paper>

            {/* Action Buttons */}
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                <Button
                    variant="outlined"
                    size="large"
                    onClick={onCancel}
                    startIcon={<CancelIcon />}
                    disabled={loading}
                    sx={{ px: 4 }}
                >
                    Cancel
                </Button>
                <Button
                    variant="contained"
                    size="large"
                    onClick={onSave}
                    disabled={loading}
                    startIcon={<SaveIcon />}
                    sx={{
                        px: 4,
                        bgcolor: '#107c10',
                        '&:hover': { bgcolor: '#0e6b0e' },
                    }}
                >
                    Approve & Save
                </Button>
            </Box>
        </Box>
    );
};

export default ReviewEstimateForm;
