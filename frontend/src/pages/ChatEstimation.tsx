import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  Avatar,
  List,
  ListItem,
  CircularProgress,
  Alert,
  Chip,
  Stack,
  Divider,
  Menu,
  MenuItem,
  ListItemText,
  Tooltip,
} from '@mui/material';
import {
  Send as SendIcon,
  SmartToy as BotIcon,
  Person as PersonIcon,
  KeyboardArrowDown as DownIcon,
  LocationOn as LocationIcon,
} from '@mui/icons-material';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { estimateService } from '../services/estimate.service';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  estimate?: {
    min?: string | number;
    max?: string | number;
  };
}

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

const INITIAL_BOT_MESSAGE =
  "Hello! I'm your home inspection assistant. Tell me the repair or inspection you need along with your ZIP code, and I’ll estimate the cost.";

const QUICK_SUGGESTIONS = [
  'Tile repair in 94102',
  'Sewer fix in 94551',
  'Roof inspection in 90210',
];

const ChatEstimation: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [clusters, setClusters] = useState<any[]>([]);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [loadingClusters, setLoadingClusters] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  /* ---------- Scroll Helpers ---------- */

  const scrollToBottom = (smooth = true) => {
    messagesEndRef.current?.scrollIntoView({
      behavior: smooth ? 'smooth' : 'auto',
    });
  };

  const handleScroll = () => {
    if (!messagesContainerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } =
      messagesContainerRef.current;

    setShowScrollToBottom(scrollHeight - scrollTop - clientHeight > 120);
  };

  useEffect(() => {
    scrollToBottom(false);
  }, [messages]);

  /* ---------- Load Clusters ---------- */

  const loadClusters = async () => {
    setLoadingClusters(true);
    try {
      const response = await estimateService.getClusters(0, 100);
      setClusters(response.data.items || []);
    } catch (err) {
      console.error('Failed to load clusters:', err);
    } finally {
      setLoadingClusters(false);
    }
  };

  const handleClusterMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
    if (clusters.length === 0) {
      loadClusters();
    }
  };

  const handleClusterMenuClose = () => {
    setAnchorEl(null);
  };

  const handleClusterSelect = (cluster: any) => {
    const zipcodes = cluster.zipcodes.join(', ');
    const clusterText = `Cluster: ${cluster.name} (Zipcodes: ${zipcodes})`;
    
    // Append cluster info to the input
    if (inputMessage.trim()) {
      setInputMessage(`${inputMessage} - ${clusterText}`);
    } else {
      setInputMessage(clusterText);
    }
    
    handleClusterMenuClose();
  };

  /* ---------- Stream Initial Bot Message ---------- */

  useEffect(() => {
    const id = Date.now().toString();
    let index = 0;

    setMessages([
      { id, text: '', sender: 'bot', timestamp: new Date() },
    ]);

    const interval = setInterval(() => {
      index++;
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === id
            ? { ...msg, text: INITIAL_BOT_MESSAGE.slice(0, index) }
            : msg
        )
      );
      if (index >= INITIAL_BOT_MESSAGE.length) clearInterval(interval);
    }, 18);
  }, []);

  /* ---------- Refresh ---------- */

  // const handleRefreshChat = () => {
  //   setMessages([]);
  //   setThreadId(null);
  //   setError(null);
  // };

  /* ---------- Send Message ---------- */

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputMessage,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/v1/chat`, {
        message: userMessage.text,
        thread_id: threadId,
      });

      const { message, thread_id, estimate } = response.data;

      if (!threadId) setThreadId(thread_id);

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          text: message,
          sender: 'bot',
          timestamp: new Date(),
          estimate,
        },
      ]);
    } catch (err: any) {
      setError(
        err.response?.data?.detail?.message ||
        'Failed to send message. Please try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  /* ---------- Enter Key ---------- */

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  /* ---------- UI ---------- */

  return (
    <Box sx={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      {/* <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="h6" fontWeight={600} color="#0078d4">
          Home Inspection Assistant
        </Typography>
        <IconButton onClick={handleRefreshChat}>
          <RefreshIcon />
        </IconButton>
      </Box> */}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Messages (Scrollable Area) */}
        <Box
          ref={messagesContainerRef}
          onScroll={handleScroll}
          sx={{
            flex: 1,
            overflowY: 'auto',
            p: 2,
            bgcolor: '#faf9f8',
            position: 'relative',
          }}
        >
          <List>
            {messages.map((message) => {
              const isUser = message.sender === 'user';

              return (
                <ListItem
                  key={message.id}
                  sx={{ justifyContent: isUser ? 'flex-end' : 'flex-start' }}
                >
                  {!isUser && (
                    <Avatar sx={{ bgcolor: '#0078d4', mr: 1 }}>
                      <BotIcon fontSize="small" />
                    </Avatar>
                  )}

                  <Box
                    sx={{
                      maxWidth: '75%',
                      bgcolor: isUser ? '#e8f5e8' : '#ffffff',
                      p: 2,
                      borderRadius: 3,
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                    }}
                  >
                    <Typography variant="caption" fontWeight={600}>
                      {isUser ? 'You' : 'Assistant'}
                    </Typography>

                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.text}
                    </ReactMarkdown>
                  </Box>

                  {isUser && (
                      <Avatar sx={{ border: '1px solid #107c10', ml: 1 }}>
                      <PersonIcon fontSize="small" />
                    </Avatar>
                  )}
                </ListItem>
              );
            })}

            {isLoading && (
              <ListItem sx={{ justifyContent: 'center' }}>
                <CircularProgress size={24} />
              </ListItem>
            )}
          </List>

          {/* Scroll to bottom button */}
          {showScrollToBottom && (
            <IconButton
              onClick={() => scrollToBottom(true)}
              sx={{
                position: 'absolute',
                bottom: 16,
                right: 16,
                bgcolor: 'white',
                boxShadow: 2,
                '&:hover': { bgcolor: '#f5f5f5' },
              }}
            >
              <DownIcon />
            </IconButton>
          )}
        </Box>

        {/* Input (Fixed Bottom) */}
        <Box sx={{ p: 2, bgcolor: '#fff' }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Select Zipcode Cluster">
              <IconButton
                onClick={handleClusterMenuOpen}
                sx={{
                  border: '1px solid #e0e0e0',
                  height: 44,
                  width: 44,
                  '&:hover': { bgcolor: '#f5f5f5' },
                }}
              >
                <LocationIcon />
              </IconButton>
            </Tooltip>

            <TextField
              fullWidth
              multiline
              maxRows={4}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Describe a repair and ZIP code (e.g., tile repair in 94102)"
            />

            <IconButton
              onClick={handleSendMessage}
              disabled={!inputMessage.trim() || isLoading}
              sx={{
                bgcolor: '#0078d4',
                color: 'white',
                height: 44,
                width: 44,
                '&:hover': { bgcolor: '#005a9e' },
              }}
            >
              <SendIcon />
            </IconButton>
          </Box>

          <Stack direction="row" spacing={1} mt={1} flexWrap="wrap">
            {QUICK_SUGGESTIONS.map((text) => (
              <Chip
                key={text}
                label={text}
                size="small"
                clickable
                onClick={() => setInputMessage(text)}
              />
            ))}
          </Stack>
        </Box>

        {/* Cluster Dropdown Menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleClusterMenuClose}
          PaperProps={{
            sx: {
              maxHeight: 400,
              width: 350,
            },
          }}
        >
          {loadingClusters ? (
            <MenuItem disabled>
              <CircularProgress size={20} sx={{ mr: 1 }} />
              Loading clusters...
            </MenuItem>
          ) : clusters.length === 0 ? (
            <MenuItem disabled>No clusters available</MenuItem>
          ) : (
            clusters.map((cluster) => (
              <MenuItem
                key={cluster.id}
                onClick={() => handleClusterSelect(cluster)}
                sx={{ flexDirection: 'column', alignItems: 'flex-start', py: 1.5 }}
              >
                <ListItemText
                  primary={cluster.name}
                  secondary={`${cluster.zipcodes.length} zipcodes: ${cluster.zipcodes.slice(0, 3).join(', ')}${cluster.zipcodes.length > 3 ? '...' : ''}`}
                  primaryTypographyProps={{ fontWeight: 600 }}
                />
              </MenuItem>
            ))
          )}
        </Menu>
      </Paper>
    </Box>
  );
};

export default ChatEstimation;
