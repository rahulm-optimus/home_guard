# Home Guard Frontend

React + TypeScript frontend application with Material UI, Axios, and error handling.

## Features

- ⚛️ React 18 with TypeScript
- 🎨 Material UI for styling
- 🔄 Axios for API calls with interceptors
- 🛡️ Error Boundary for error handling
- 🚦 React Router for navigation
- 📄 404 Page for invalid routes
- ⚡ Vite for fast development

## Getting Started

### Prerequisites

- Node.js (v16 or higher)
- npm or yarn

### Installation

1. Install dependencies:
```bash
npm install
```

2. Environment files are pre-configured:
   - `.env.development` - Development (http://localhost:5000/api)
   - `.env.production` - Production (https://api.homeguard.com/api)

### Development

Run the development server (uses `.env.development`):
```bash
npm run dev
```

The application will be available at `http://localhost:3000`

### Build

Build for production (uses `.env.production`):
```bash
npm run build
```

Build for development environment:
```bash
npm run build:dev
```

Preview production build:
```bash
npm run preview
```

## Environment Configuration

The application uses different environment files based on the mode:

| Command | Mode | Environment File | API URL |
|---------|------|------------------|---------|
| `npm run dev` | development | `.env.development` | http://localhost:5000/api |
| `npm run build` | production | `.env.production` | https://api.homeguard.com/api |
| `npm run build:dev` | development | `.env.development` | http://localhost:5000/api |

### Environment Variables

All environment variables must be prefixed with `VITE_` to be accessible in the application.

Available variables:
- `VITE_API_BASE_URL` - Base URL for API calls
- `VITE_ENV` - Environment name (development/production)

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── ErrorBoundary.tsx      # Error boundary component
│   ├── pages/
│   │   ├── Dashboard.tsx          # Dashboard page
│   │   └── NotFound.tsx           # 404 page
│   ├── types/
│   │   └── error.types.ts         # Error type definitions
│   ├── utils/
│   │   └── axios.ts               # Axios instance with interceptors
│   ├── App.tsx                    # Main app component
│   ├── main.tsx                   # Entry point
│   └── vite-env.d.ts              # Vite type definitions
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

## Features Explained

### Axios Configuration (`src/utils/axios.ts`)

- Configurable base URL via environment variables
- Request interceptor that adds JWT token to headers
- Response interceptor for centralized error handling
- Handles 401, 403, 404, 500 errors automatically

### Error Boundary (`src/components/ErrorBoundary.tsx`)

- Catches React component errors
- Displays user-friendly error message
- Provides "Try Again" functionality

### 404 Page (`src/pages/NotFound.tsx`)

- Displayed for all routes except `/dashboard`
- Styled with Material UI
- Provides navigation back to dashboard

### Routing

- Root (`/`) redirects to `/dashboard`
- `/dashboard` - Main dashboard page
- All other routes show 404 page

## Usage Examples

### Making API Calls

```typescript
import axios from './utils/axios';

// GET request
const fetchData = async () => {
  try {
    const response = await axios.get('/endpoint');
    console.log(response.data);
  } catch (error) {
    // Error is already handled by interceptor
    console.error('Error fetching data:', error);
  }
};

// POST request
const postData = async (data: any) => {
  try {
    const response = await axios.post('/endpoint', data);
    return response.data;
  } catch (error) {
    console.error('Error posting data:', error);
  }
};
```

## License

ISC
