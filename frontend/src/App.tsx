import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  CssBaseline,
  ThemeProvider,
  createTheme,
  IconButton,
  Divider,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  AttachMoney as MoneyIcon,
  Storage as StorageIcon,
  Chat as ChatIcon,
  Menu as MenuIcon,
} from '@mui/icons-material';
import CostEstimation from './pages/CostEstimation';
import SavedItems from './pages/SavedItems';
import ChatEstimation from './pages/ChatEstimation';
import NotFound from './pages/NotFound';
import ErrorBoundary from './components/ErrorBoundary';
import logo from './assets/homeguard-incorporated-logo.png';

const drawerWidth = 260;

// Microsoft Fluent Design inspired theme with improved typography
const theme = createTheme({
  palette: {
    primary: {
      main: '#0078d4',
      light: '#50a3e0',
      dark: '#005a9e',
    },
    secondary: {
      main: '#107c10',
      light: '#4d9e4d',
      dark: '#0d5e0d',
    },
    error: {
      main: '#d83b01',
    },
    background: {
      default: '#faf9f8',
      paper: '#ffffff',
    },
    text: {
      primary: '#323130',
      secondary: '#605e5c',
    },
  },
  typography: {
    fontFamily: '"Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif',
    fontSize: 14,
    h4: {
      fontWeight: 600,
      fontSize: '1.75rem',
      lineHeight: 1.3,
      '@media (max-width:600px)': {
        fontSize: '1.5rem',
      },
    },
    h5: {
      fontWeight: 600,
      fontSize: '1.5rem',
      lineHeight: 1.3,
      '@media (max-width:600px)': {
        fontSize: '1.25rem',
      },
    },
    h6: {
      fontWeight: 600,
      fontSize: '1.25rem',
      lineHeight: 1.3,
      '@media (max-width:600px)': {
        fontSize: '1.125rem',
      },
    },
    subtitle1: {
      fontSize: '1rem',
      fontWeight: 500,
      lineHeight: 1.5,
    },
    subtitle2: {
      fontSize: '0.875rem',
      fontWeight: 500,
      lineHeight: 1.57,
    },
    body1: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
    },
    body2: {
      fontSize: '0.8125rem',
      lineHeight: 1.43,
    },
    button: {
      fontSize: '0.875rem',
      fontWeight: 600,
      textTransform: 'none',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 4,
          padding: '8px 20px',
          fontSize: '0.875rem',
          '@media (max-width:600px)': {
            padding: '6px 16px',
            fontSize: '0.8125rem',
          },
        },
        sizeLarge: {
          padding: '12px 28px',
          fontSize: '1rem',
          '@media (max-width:600px)': {
            padding: '10px 24px',
            fontSize: '0.875rem',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiInputBase-root': {
            fontSize: '0.875rem',
          },
          '& .MuiInputLabel-root': {
            fontSize: '0.875rem',
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          fontSize: '0.875rem',
          padding: '12px 16px',
          '@media (max-width:600px)': {
            padding: '8px 12px',
            fontSize: '0.8125rem',
          },
        },
      },
    },
  },
});

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Cost Estimation', icon: <MoneyIcon />, path: '/estimation' },
  { text: 'Chatbot', icon: <ChatIcon />, path: '/chatbot' },
  { text: 'Saved Items', icon: <StorageIcon />, path: '/saved-items' },
];

const DashboardLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const drawer = (
    <Box>
      <Toolbar sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 2 }}>
        <Box
          component="img"
          src={logo}
          alt="HomeGuard Logo"
          sx={{
            height: 40,
            width: 40,
            objectFit: 'contain',
          }}
        />
        <Typography variant="h6" noWrap component="div" sx={{ fontWeight: 700, color: '#0078d4', fontSize: '1.25rem' }}>
          HomeGuard
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => {
                navigate(item.path);
                setMobileOpen(false);
              }}
              sx={{
                '&.Mui-selected': {
                  bgcolor: '#e3f2fd',
                  borderLeft: '4px solid #0078d4',
                  '&:hover': {
                    bgcolor: '#d0e8f7',
                  },
                },
              }}
            >
              <ListItemIcon sx={{ color: location.pathname === item.path ? '#0078d4' : 'inherit' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText 
                primary={item.text}
                primaryTypographyProps={{
                  fontWeight: location.pathname === item.path ? 600 : 400,
                }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          ml: { sm: `${drawerWidth}px` },
          bgcolor: '#ffffff',
          color: '#323130',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Box
            component="img"
            src={logo}
            alt="HomeGuard Logo"
            sx={{
              height: 32,
              width: 32,
              objectFit: 'contain',
              mr: 2,
              display: { xs: 'block', sm: 'none' },
            }}
          />
          <Typography variant="h6" noWrap component="div" sx={{ fontWeight: 600, fontSize: { xs: '1rem', sm: '1.25rem' } }}>
            Cost Estimation System
          </Typography>
        </Toolbar>
      </AppBar>

      <Box
        component="nav"
        sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          minHeight: '100vh',
          bgcolor: '#f3f2f1',
        }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
};

const DashboardHome: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 600, color: '#0078d4' }}>
        Welcome to HomeGuard
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Manage your inspection cost estimates efficiently
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
        <Box
          onClick={() => navigate('/estimation')}
          sx={{
            p: 4,
            bgcolor: '#ffffff',
            border: '1px solid #e0e0e0',
            borderRadius: 2,
            cursor: 'pointer',
            transition: 'all 0.2s',
            '&:hover': {
              boxShadow: 4,
              transform: 'translateY(-4px)',
            },
          }}
        >
          <MoneyIcon sx={{ fontSize: 48, color: '#0078d4', mb: 2 }} />
          <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
            Cost Estimation
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Create new cost estimates for inspection items
          </Typography>
        </Box>

        <Box
          onClick={() => navigate('/saved-items')}
          sx={{
            p: 4,
            bgcolor: '#ffffff',
            border: '1px solid #e0e0e0',
            borderRadius: 2,
            cursor: 'pointer',
            transition: 'all 0.2s',
            '&:hover': {
              boxShadow: 4,
              transform: 'translateY(-4px)',
            },
          }}
        >
          <StorageIcon sx={{ fontSize: 48, color: '#107c10', mb: 2 }} />
          <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
            Saved Items
          </Typography>
          <Typography variant="body2" color="text.secondary">
            View and manage all saved cost estimates
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};

function App() {
  return (
    <ThemeProvider theme={theme}>
      <ErrorBoundary>
        <Router>
          <DashboardLayout>
            <Routes>
              <Route path="/" element={<DashboardHome />} />
              <Route path="/estimation" element={<CostEstimation />} />
              <Route path="/chatbot" element={<ChatEstimation />} />
              <Route path="/saved-items" element={<SavedItems />} />
              <Route path="/404" element={<NotFound />} />
              <Route path="*" element={<Navigate to="/404" replace />} />
            </Routes>
          </DashboardLayout>
        </Router>
      </ErrorBoundary>
    </ThemeProvider>
  );
}

export default App;
