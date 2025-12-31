import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Alert,
  IconButton,
  Grid,
  Button,
  Stack,
  Divider,
  TablePagination,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { estimateService } from '../services/estimate.service';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import Tooltip from '@mui/material/Tooltip';


const SavedItems: React.FC = () => {
  const [items, setItems] = useState<any[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchItems = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await estimateService.getItems(page * rowsPerPage, rowsPerPage);
      setItems(response.data.items);
      setTotalCount(response.data.total_count);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to fetch saved items');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, [page, rowsPerPage]);

  const handleDelete = async (id: string, zipcode: string) => {
    if (!confirm('Are you sure you want to delete this item?')) return;
    try {
      await estimateService.deleteItem(id, zipcode);
      fetchItems();
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to delete item');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'approved': return 'success';
      case 'pending': return 'warning';
      case 'rejected': return 'error';
      default: return 'default';
    }
  };

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error('Copy failed', err);
    }
  };


  const formatLocalDateTime = (dateString?: string) => {
    if (!dateString) return '—';

    const date = new Date(dateString);

    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    }).format(date);
  };


  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={600} color="primary">
            Saved Items
          </Typography>
          <Typography variant="body2" color="text.secondary">
            View all saved cost estimates
          </Typography>
        </Box>
        <IconButton onClick={fetchItems} disabled={loading} color="primary">
          <RefreshIcon />
        </IconButton>
      </Box>

      {/* Error */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Loading */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Cards */}
      {!loading && items.length > 0 && (
        <Stack spacing={2}>
          {items.map((item) => (
            <Card
              key={item.id}
              variant="outlined"
              sx={{
                borderLeft: '4px solid',
                borderColor: 'primary.main',
              }}
            >
              <CardContent>
                <Grid container spacing={2} alignItems="center">
                  {/* Message / Description */}
                  <Grid item xs={12} md={9}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                      <Typography
                        variant="subtitle1"
                        fontWeight={600}
                        sx={{ flexGrow: 1 }}
                      >
                        {item.message}
                      </Typography>

                      <Tooltip title="Copy message">
                        <IconButton
                          size="small"
                          onClick={() => handleCopy(item.message)}
                          sx={{ mt: '2px' }}
                        >
                          <ContentCopyIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                    <Stack direction="row" spacing={1} flexWrap="wrap">
                      <Chip
                        label={`Min: $${item.min_estimate?.toLocaleString()}`}
                        color="success"
                        size="small"
                      />
                      <Chip
                        label={`Max: $${item.max_estimate?.toLocaleString()}`}
                        color="error"
                        size="small"
                      />
                      {/* <Chip
                        label={item.status.toUpperCase()}
                        color={getStatusColor(item.status)}
                        size="small"
                      /> */}
                    </Stack>
                  </Grid>

                  {/* Actions */}
                  <Grid
                    item
                    xs={12}
                    md={3}
                    sx={{ textAlign: { xs: 'left', md: 'right' } }}
                  >
                    <Button
                      variant="outlined"
                      color="error"
                      size="small"
                      startIcon={<DeleteIcon />}
                      onClick={() => handleDelete(item.id, item.zipcode)}
                    >
                      Delete
                    </Button>
                  </Grid>
                </Grid>

                <Divider sx={{ my: 2 }} />
                <Stack direction="row" spacing={1} flexWrap="wrap">
                  <Chip
                    label={`Date: ${formatLocalDateTime(item.dateOfCreation || item.dateofcreation)}`}
                    variant="outlined"
                    size="small"
                  />
                  <Chip
                    label={`Zipcode: ${item.zipcode}`}
                    variant="outlined"
                    size="small"
                  />

                </Stack>
              </CardContent>
            </Card>
          ))}

          {/* Pagination */}
          <TablePagination
            component="div"
            count={totalCount}
            page={page}
            onPageChange={(_, newPage) => setPage(newPage)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[5, 10, 25, 50]}
          />
        </Stack>
      )}

      {/* Empty State */}
      {!loading && items.length === 0 && (
        <Box
          sx={{
            p: 8,
            textAlign: 'center',
            border: '1px dashed #ccc',
            borderRadius: 2,
          }}
        >
          <Typography variant="h6" color="text.secondary">
            No saved items found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Create cost estimates to see them here
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default SavedItems;
