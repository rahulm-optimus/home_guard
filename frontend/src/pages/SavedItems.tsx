/**
 * Saved Items Page
 * Display all saved estimates with pagination
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  Grid,
  Divider,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { estimateService } from '../services/estimate.service';
import { SaveItemInput } from '../types/api.types';

const SavedItems: React.FC = () => {
  const [items, setItems] = useState<SaveItemInput[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  // Fetch items
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

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const toggleRowExpansion = (id: string) => {
    setExpandedRows((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'approved':
        return 'success';
      case 'pending':
        return 'warning';
      case 'rejected':
        return 'error';
      default:
        return 'default';
    }
  };

  const calculateTotal = (items: any[]) => {
    if (!items || !Array.isArray(items) || items.length === 0) {
      return { min: 0, max: 0 };
    }
    const minTotal = items.reduce((sum, item) => sum + (item.estimate?.min || 0), 0);
    const maxTotal = items.reduce((sum, item) => sum + (item.estimate?.max || 0), 0);
    return { min: minTotal, max: maxTotal };
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom sx={{ fontWeight: 600, color: '#0078d4' }}>
            Saved Items
          </Typography>
          <Typography variant="body1" color="text.secondary">
            View all saved cost estimates
          </Typography>
        </Box>
        <IconButton onClick={fetchItems} disabled={loading} color="primary">
          <RefreshIcon />
        </IconButton>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Table */}
      {!loading && items.length > 0 && (
        <Paper elevation={0} sx={{ border: '1px solid #e0e0e0' }}>
          <TableContainer>
            <Table>
              <TableHead sx={{ bgcolor: '#f5f5f5' }}>
                <TableRow>
                  <TableCell width={50}></TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>ID</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Category</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Username</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Zipcode</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Date</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Items</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => {
                  const isExpanded = expandedRows.has(item.id);
                  const totals = calculateTotal(item.items);

                  return (
                    <React.Fragment key={item.id}>
                      <TableRow
                        hover
                        sx={{ cursor: 'pointer', '&:hover': { bgcolor: '#f9f9f9' } }}
                        onClick={() => toggleRowExpansion(item.id)}
                      >
                        <TableCell>
                          <IconButton size="small">
                            {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                          </IconButton>
                        </TableCell>
                        <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                          {item.id}
                        </TableCell>
                        <TableCell>{item.category}</TableCell>
                        <TableCell>{item.username}</TableCell>
                        <TableCell>{item.zipcode}</TableCell>
                        <TableCell>{item.dateofcreation}</TableCell>
                        <TableCell>
                          <Chip 
                            label={item.items?.length || 0} 
                            size="small" 
                            color="primary" 
                          />
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={item.status}
                            size="small"
                            color={getStatusColor(item.status)}
                            variant="outlined"
                          />
                        </TableCell>
                      </TableRow>

                      {/* Expanded Row */}
                      <TableRow>
                        <TableCell colSpan={8} sx={{ p: 0, border: 0 }}>
                          <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                            <Box sx={{ p: 3, bgcolor: '#fafafa' }}>
                              <Grid container spacing={2} sx={{ mb: 3 }}>
                                <Grid item xs={12}>
                                  <Typography variant="subtitle2" color="text.secondary">
                                    Address
                                  </Typography>
                                  <Typography variant="body1">{item.address}</Typography>
                                </Grid>
                              </Grid>

                              <Divider sx={{ my: 2 }} />

                              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                                Items ({item.items?.length || 0})
                              </Typography>

                              {item.items && item.items.length > 0 ? (
                                item.items.map((detail, idx) => (
                                <Card key={idx} sx={{ mb: 2, boxShadow: 1 }}>
                                  <CardContent>
                                    <Box
                                      sx={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'start',
                                        mb: 1,
                                      }}
                                    >
                                      <Typography variant="subtitle2" sx={{ fontWeight: 500 }}>
                                        {detail.description}
                                      </Typography>
                                      <Chip
                                        label={detail.subcategory}
                                        size="small"
                                        color="primary"
                                        variant="outlined"
                                      />
                                    </Box>
                                    <Grid container spacing={2} sx={{ mt: 1 }}>
                                      <Grid item xs={12} md={4}>
                                        <Typography variant="caption" color="text.secondary">
                                          Estimate Range
                                        </Typography>
                                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                          ${(detail.estimate?.min || 0).toLocaleString()} - $
                                          {(detail.estimate?.max || 0).toLocaleString()}
                                        </Typography>
                                      </Grid>
                                      <Grid item xs={12} md={8}>
                                        <Typography variant="caption" color="text.secondary">
                                          Note
                                        </Typography>
                                        <Typography variant="body2">{detail.note}</Typography>
                                      </Grid>
                                    </Grid>
                                  </CardContent>
                                </Card>
                              ))) : (
                                <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                                  No items found
                                </Typography>
                              )}

                              {/* Total */}
                              {item.items && item.items.length > 0 && (
                              <Paper
                                elevation={0}
                                sx={{ p: 2, mt: 2, bgcolor: '#e3f2fd', border: '1px solid #0078d4' }}
                              >
                                <Grid container spacing={2}>
                                  <Grid item xs={12} md={6}>
                                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                      Total Estimate Range
                                    </Typography>
                                  </Grid>
                                  <Grid item xs={6} md={3}>
                                    <Typography variant="caption" color="text.secondary">
                                      Minimum
                                    </Typography>
                                    <Typography variant="h6" sx={{ fontWeight: 600, color: '#107c10' }}>
                                      ${totals.min.toLocaleString()}
                                    </Typography>
                                  </Grid>
                                  <Grid item xs={6} md={3}>
                                    <Typography variant="caption" color="text.secondary">
                                      Maximum
                                    </Typography>
                                    <Typography variant="h6" sx={{ fontWeight: 600, color: '#d83b01' }}>
                                      ${totals.max.toLocaleString()}
                                    </Typography>
                                  </Grid>
                                </Grid>
                              </Paper>
                              )}
                            </Box>
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    </React.Fragment>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>

          {/* Pagination */}
          <TablePagination
            component="div"
            count={totalCount}
            page={page}
            onPageChange={handleChangePage}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={handleChangeRowsPerPage}
            rowsPerPageOptions={[5, 10, 25, 50]}
          />
        </Paper>
      )}

      {/* Empty State */}
      {!loading && items.length === 0 && (
        <Paper elevation={0} sx={{ p: 8, textAlign: 'center', border: '1px solid #e0e0e0' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No saved items found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Create cost estimates to see them here
          </Typography>
        </Paper>
      )}
    </Box>
  );
};

export default SavedItems;
