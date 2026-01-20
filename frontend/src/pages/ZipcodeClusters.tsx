import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  IconButton,
  Button,
  Stack,
  Divider,
  TablePagination,
  TextField,
  InputAdornment,
  Chip,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
  Add as AddIcon,
  ContentCopy as ContentCopyIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import Tooltip from '@mui/material/Tooltip';
import AddEditClusterDialog, { ClusterFormData } from '../components/AddEditClusterDialog';
import { estimateService } from '../services/estimate.service';

const ZipcodeClusters: React.FC = () => {
  const [clusters, setClusters] = useState<any[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'add' | 'edit'>('add');
  const [editData, setEditData] = useState<ClusterFormData | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Debouncing effect for search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
      setPage(0);
    }, 500);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchClusters = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await estimateService.getClusters(
        page * rowsPerPage,
        rowsPerPage,
        debouncedSearchQuery.trim()
      );
      setClusters(response.data.items);
      setTotalCount(response.data.total_count);
    } catch (err: any) {
      setError(err.response?.data?.message || err.message || 'Failed to fetch zipcode clusters');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClusters();
  }, [page, rowsPerPage, debouncedSearchQuery]);

  const handleClearSearch = () => {
    setSearchQuery('');
  };

  const handleAddCluster = () => {
    setDialogMode('add');
    setEditData(null);
    setDialogOpen(true);
  };

  const handleEditCluster = (cluster: any) => {
    setDialogMode('edit');
    setEditData({
      id: cluster.id,
      name: cluster.name,
      zipcodes: cluster.zipcodes,
      description: cluster.description || '',
    });
    setDialogOpen(true);
  };

  const handleDialogSubmit = async (data: ClusterFormData) => {
    try {
      let response;
      if (dialogMode === 'add') {
        response = await estimateService.createCluster({
          name: data.name,
          zipcodes: data.zipcodes,
          description: data.description,
        });
        // Check if it was actually an update (backend updates existing cluster with same name)
        const message = response.message || 'Cluster created successfully';
        if (message.includes('updated')) {
          setSuccessMessage(`Cluster "${data.name}" already existed and was updated successfully`);
        } else {
          setSuccessMessage('Cluster created successfully');
        }
      } else {
        await estimateService.updateCluster(data.id!, {
          name: data.name,
          zipcodes: data.zipcodes,
          description: data.description,
        });
        setSuccessMessage('Cluster updated successfully');
      }
      fetchClusters();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      throw new Error(err.response?.data?.detail || err.message || 'Failed to save cluster');
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
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3, alignItems: 'flex-start' }}>
        <Box>
          <Typography variant="h4" fontWeight={600} color="primary">
            Zipcode Clusters
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage zipcode clusters for grouped cost estimates
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <IconButton onClick={fetchClusters} disabled={loading} color="primary">
            <RefreshIcon />
          </IconButton>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddCluster}
            sx={{
              bgcolor: 'primary.main',
              '&:hover': { bgcolor: 'primary.dark' },
            }}
          >
            Add Cluster
          </Button>
        </Stack>
      </Box>

      {/* Search Input */}
      <Box sx={{ mb: 3 }}>
        <TextField
          fullWidth
          placeholder="Search clusters by name, description, or zipcode..."
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
              borderRadius: '999px',
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

      {/* Success */}
      {successMessage && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {/* Loading */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Cards */}
      {!loading && clusters.length > 0 && (
        <Stack spacing={2}>
          {clusters.map((cluster) => (
            <Card
              key={cluster.id}
              variant="outlined"
              sx={{
                borderLeft: '4px solid',
                borderColor: 'secondary.main',
              }}
            >
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 1 }}>
                  <Typography variant="h6" fontWeight={600} sx={{ flexGrow: 1 }}>
                    {cluster.name}
                  </Typography>
                  <Tooltip title="Edit cluster">
                    <IconButton
                      size="small"
                      onClick={() => handleEditCluster(cluster)}
                      color="primary"
                      sx={{ mt: '-4px' }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Copy cluster ID">
                    <IconButton
                      size="small"
                      onClick={() => handleCopy(cluster.id)}
                      sx={{ mt: '-4px' }}
                    >
                      <ContentCopyIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>

                {cluster.description && (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {cluster.description}
                  </Typography>
                )}

                <Divider sx={{ my: 2 }} />

                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                    Zipcodes ({cluster.zipcodes.length}):
                  </Typography>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {cluster.zipcodes.map((zipcode: string) => (
                      <Chip
                        key={zipcode}
                        label={zipcode}
                        size="small"
                        variant="outlined"
                        color="primary"
                        sx={{ fontFamily: 'monospace' }}
                      />
                    ))}
                  </Stack>
                </Box>

                <Divider sx={{ my: 2 }} />

                <Stack direction="row" spacing={1} flexWrap="wrap">
                  <Chip
                    label={`Created: ${formatLocalDateTime(cluster.created_at)}`}
                    variant="outlined"
                    size="small"
                  />
                </Stack>
              </CardContent>
            </Card>
          ))}

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
      {!loading && clusters.length === 0 && (
        <Box
          sx={{
            p: 8,
            textAlign: 'center',
            border: '1px dashed #ccc',
            borderRadius: 2,
          }}
        >
          <Typography variant="h6" color="text.secondary">
            No zipcode clusters found
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Create a cluster to group zipcodes together
          </Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleAddCluster}>
            Add Your First Cluster
          </Button>
        </Box>
      )}

      {/* Add/Edit Cluster Dialog */}
      <AddEditClusterDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleDialogSubmit}
        editData={editData}
        mode={dialogMode}
      />
    </Box>
  );
};

export default ZipcodeClusters;
