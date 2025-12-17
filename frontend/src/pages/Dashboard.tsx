import { Box, Container, Typography, Card, CardContent, Stack } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';

const Dashboard = () => {
  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h3" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <DashboardIcon fontSize="large" />
          Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Welcome to Home Guard Dashboard
        </Typography>
      </Box>

      <Stack spacing={3} direction={{ xs: 'column', sm: 'row' }} flexWrap="wrap">
        <Card sx={{ flex: { xs: '1 1 100%', sm: '1 1 calc(50% - 12px)', md: '1 1 calc(33.333% - 16px)' } }}>
          <CardContent>
            <Typography variant="h5" gutterBottom>
              Total Alerts
            </Typography>
            <Typography variant="h3" color="primary">
              0
            </Typography>
          </CardContent>
        </Card>

        <Card sx={{ flex: { xs: '1 1 100%', sm: '1 1 calc(50% - 12px)', md: '1 1 calc(33.333% - 16px)' } }}>
          <CardContent>
            <Typography variant="h5" gutterBottom>
              Active Cameras
            </Typography>
            <Typography variant="h3" color="success.main">
              0
            </Typography>
          </CardContent>
        </Card>

        <Card sx={{ flex: { xs: '1 1 100%', sm: '1 1 calc(50% - 12px)', md: '1 1 calc(33.333% - 16px)' } }}>
          <CardContent>
            <Typography variant="h5" gutterBottom>
              Status
            </Typography>
            <Typography variant="h3" color="text.secondary">
              Online
            </Typography>
          </CardContent>
        </Card>
      </Stack>
    </Container>
  );
};

export default Dashboard;
