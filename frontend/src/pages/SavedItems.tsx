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
  TextField,
  InputAdornment,
  Snackbar,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { estimateService } from '../services/estimate.service';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import Tooltip from '@mui/material/Tooltip';
import EditItemDialog, { EditItemFormData } from '../components/EditItemDialog';


const SavedItems: React.FC = () => {
  const [items, setItems] = useState<any[]>([]);
  const [groupedItems, setGroupedItems] = useState<any[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Debouncing effect for search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
      setPage(0); // Reset to first page when search query changes
    }, 500); // 500ms debounce delay

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchItems = async () => {
    setLoading(true);
    setError(null);
    try {
      let response;
      if (debouncedSearchQuery.trim()) {
        // Search items if query exists
        response = await estimateService.searchItems(
          debouncedSearchQuery.trim(),
          page * rowsPerPage,
          rowsPerPage
        );
      } else {
        // Get all items if no search query
        response = await estimateService.getItems(page * rowsPerPage, rowsPerPage);
      }
      setItems(response.data.items);
      setTotalCount(response.data.total_count);
      
      // Group items by cluster_name and message
      const grouped = groupItemsByClusterAndMessage(response.data.items);
      setGroupedItems(grouped);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to fetch saved items');
    } finally {
      setLoading(false);
    }
  };

  // Group items by cluster_name and message
  const groupItemsByClusterAndMessage = (items: any[]) => {
    const groups: { [key: string]: any } = {};
    
    items.forEach((item) => {
      // Create a unique key based on cluster_name and message
      const key = `${item.cluster_name || 'Unknown'}_${item.message}`;
      
      if (!groups[key]) {
        groups[key] = {
          cluster_name: item.cluster_name || 'Unknown',
          message: item.message,
          status: item.status,
          type: item.type,
          currency: item.currency,
          dateOfCreation: item.dateOfCreation || item.dateofcreation,
          thread_id: item.thread_id,
          min_estimate: item.min_estimate,
          max_estimate: item.max_estimate,
          zipcodes: [item.zipcode],
          items: [item], // Keep reference to all items in this group
        };
      } else {
        // Add zipcode to the group
        if (!groups[key].zipcodes.includes(item.zipcode)) {
          groups[key].zipcodes.push(item.zipcode);
        }
        groups[key].items.push(item);
      }
    });
    
    return Object.values(groups);
  };

  useEffect(() => {
    fetchItems();
  }, [page, rowsPerPage, debouncedSearchQuery]);

  const handleClearSearch = () => {
    setSearchQuery('');
  };

  const handleEditClick = (item: any) => {
    setSelectedItem(item);
    setEditDialogOpen(true);
  };

  const handleEditSubmit = async (formData: EditItemFormData) => {
    if (!selectedItem) return;

    try {
      await estimateService.updateItem(
        selectedItem.id,
        selectedItem.zipcode,
        { item: formData }
      );
      setSuccessMessage('Cost Estimate updated successfully');
      setEditDialogOpen(false);
      fetchItems(); // Refresh the list
    } catch (err: any) {
      throw err; // Let the dialog handle the error
    }
  };

  // const getStatusColor = (status: string) => {
  //   switch (status.toLowerCase()) {
  //     case 'approved': return 'success';
  //     case 'pending': return 'warning';
  //     case 'rejected': return 'error';
  //     default: return 'default';
  //   }
  // };

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
      
      {/* Search Input */}
      <Box sx={{ mb: 3 }}>
        <TextField
          fullWidth
          placeholder="Search items by items..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          variant="outlined"
          size="medium"
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
            endAdornment: searchQuery && (
              <InputAdornment position="end">
                <IconButton
                  size="small"
                  onClick={handleClearSearch}
                  edge="end"
                  sx={{
                    bgcolor: 'grey.100',
                    '&:hover': { bgcolor: 'grey.200' },
                  }}
                >
                  <ClearIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ),
          }}
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: '999px', // pill shape
              backgroundColor: '#fff',
              paddingRight: 1,
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
              transition: 'all 0.2s ease-in-out',

              '& fieldset': {
                borderColor: 'transparent',
              },

              '&:hover fieldset': {
                borderColor: 'transparent',
              },

              '&.Mui-focused fieldset': {
                borderColor: 'primary.main',
                borderWidth: '1px',
              },
            },

            '& input::placeholder': {
              color: 'text.secondary',
              opacity: 0.8,
            },
          }}
        />
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
      {!loading && groupedItems.length > 0 && (
        <Stack spacing={2}>
          {groupedItems.map((group, index) => (
            <Card
              key={`${group.cluster_name}-${group.message}-${index}`}
              variant="outlined"
              sx={{
                borderLeft: '4px solid',
                borderColor: 'primary.main',
              }}
            >
              <CardContent>
                <Grid container spacing={2} alignItems="center">
                  {/* Message / Description */}
                  <Grid item xs={12} md={7}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                      <Typography
                        variant="subtitle1"
                        fontWeight={600}
                        sx={{ flexGrow: 1 }}
                      >
                        {group.message}
                      </Typography>

                      <Tooltip title="Copy message">
                        <IconButton
                          size="small"
                          onClick={() => handleCopy(group.message)}
                          sx={{ mt: '2px' }}
                        >
                          <ContentCopyIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                    <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 1 }}>
                      <Chip
                        label={`Min: $${group.min_estimate?.toLocaleString()}`}
                        color="success"
                        size="small"
                      />
                      <Chip
                        label={`Max: $${group.max_estimate?.toLocaleString()}`}
                        color="error"
                        size="small"
                      />
                    </Stack>
                  </Grid>

                  {/* Actions */}
                  <Grid
                    item
                    xs={12}
                    md={5}
                    sx={{ textAlign: { xs: 'left', md: 'right' } }}
                  >
                    <Button
                      variant="outlined"
                      color="primary"
                      size="small"
                      startIcon={<EditIcon />}
                      onClick={() => handleEditClick(group.items[0])}
                    >
                      Edit
                    </Button>
                  </Grid>
                </Grid>

                <Divider sx={{ my: 2 }} />
                <Stack direction="row" spacing={1} flexWrap="wrap">
                  <Chip
                    label={`Date: ${formatLocalDateTime(group.dateOfCreation)}`}
                    variant="outlined"
                    size="small"
                  />
                  <Chip
                    label={`Cluster: ${group.cluster_name}`}
                    variant="outlined"
                    size="small"
                    color="primary"
                    sx={{ fontWeight: 600 }}
                  />
                  <Chip
                    label={`${group.zipcodes.length} Zipcode${group.zipcodes.length > 1 ? 's' : ''}`}
                    variant="outlined"
                    size="small"
                    color="secondary"
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
      {!loading && groupedItems.length === 0 && (
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

      {/* Edit Dialog */}
      <EditItemDialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        onSubmit={handleEditSubmit}
        editData={selectedItem}
      />

      {/* Success Snackbar */}
      <Snackbar
        open={!!successMessage}
        autoHideDuration={4000}
        onClose={() => setSuccessMessage(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="success" onClose={() => setSuccessMessage(null)} sx={{ width: '100%' }}>
          {successMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default SavedItems;
