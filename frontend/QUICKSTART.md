# HomeGuard Frontend - Quick Start Guide

## ✅ **Setup Complete!**

Your frontend application is now running successfully.

### **Access the Application**

- **Frontend URL**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

---

## 📱 **Application Features**

### **1. Dashboard (Home)**
- Navigate to: `http://localhost:3000/`
- Two main action cards:
  - **Cost Estimation** - Create new estimates
  - **Saved Items** - View saved estimates

### **2. Cost Estimation Flow**
Navigate to: `http://localhost:3000/estimation`

**Step 1: Enter Details**
- Select category (Home inspection, Termite inspection, etc.)
- Enter username (e.g., "John doe")
- Enter zipcode (e.g., "94551")
- Enter address (e.g., "2623 Anywhere Street, Hometown, CA 94551")
- Add items by typing and clicking + or pressing Enter
- Click "Get Estimates" button

**Step 2: Review & Edit**
- Review all generated estimates
- Edit any field (description, subcategory, min/max values, notes)
- See total estimate range at bottom
- Click "Approve & Save" to save or "Cancel" to discard

**Step 3: Success**
- Confirmation screen
- Click "Create New Estimate" to start over

### **3. Saved Items**
Navigate to: `http://localhost:3000/saved-items`

- View all saved estimates in table format
- Click any row to expand and see:
  - Full address
  - All items with details
  - Individual and total estimates
- Use pagination controls at bottom
- Click refresh icon to reload

---

## 🎨 **Design Features**

- **Microsoft Fluent Design** inspired UI
- **Colors**:
  - Primary: Microsoft Blue (#0078d4)
  - Success: Microsoft Green (#107c10)
  - Error: Microsoft Red (#d83b01)
- **Responsive** - Works on mobile, tablet, and desktop
- **Sidebar Navigation** - Easy access to all features
- **Material-UI Components** - Professional look and feel

---

## 🧪 **Test the Application**

### **Test Case 1: Home Inspection**

1. Go to Cost Estimation
2. Fill in:
   - Category: `Home inspection`
   - Username: `John Doe`
   - Zipcode: `94551`
   - Address: `2623 Anywhere Street, Hometown, CA 94551`
3. Add items:
   - `Fix leaking kitchen faucet`
   - `Repair broken window`
4. Click "Get Estimates"
5. Review and click "Approve & Save"
6. Go to Saved Items to verify

### **Test Case 2: Termite Inspection**

1. Go to Cost Estimation
2. Fill in:
   - Category: `Termite inspection`
   - Username: `Jane Smith`
   - Zipcode: `90210`
   - Address: `456 Oak Avenue, Beverly Hills, CA 90210`
3. Add items:
   - `Fungus damage was noted to the rafter tail as indicated on the diagram`
   - `Fungus damage was noted to the roof sheathing as indicated on the diagram`
4. Click "Get Estimates"
5. Edit estimates if needed
6. Click "Approve & Save"

---

## 🔧 **Development Commands**

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type checking
npm run lint
```

---

## 📁 **Project Structure**

```
frontend/
├── src/
│   ├── components/
│   │   ├── ErrorBoundary.tsx          # Error handling
│   │   └── ReviewEstimateForm.tsx     # Estimate review component
│   ├── pages/
│   │   ├── CostEstimation.tsx         # Main estimation page (3-step)
│   │   ├── SavedItems.tsx             # Saved items with pagination
│   │   └── NotFound.tsx               # 404 page
│   ├── services/
│   │   └── estimate.service.ts        # API calls
│   ├── types/
│   │   └── api.types.ts               # TypeScript types
│   ├── utils/
│   │   └── axios.ts                   # Axios configuration
│   ├── App.tsx                        # Main app with routing
│   └── main.tsx                       # Entry point
├── .env.development                   # Development config
└── package.json
```

---

## 🌐 **API Endpoints Used**

### **POST /api/v1/estimate**
Get cost estimates for inspection items
```json
{
  "query": ["item 1", "item 2"],
  "category": "Home inspection",
  "zipcode": "94551",
  "address": "123 Main St",
  "username": "john_doe"
}
```

### **POST /api/v1/save-items**
Save approved estimates to Cosmos DB
```json
{
  "items": [{
    "id": "inspection-001",
    "category": "Home inspection",
    "items": [...],
    "zipcode": "94551",
    "address": "123 Main St",
    "username": "john_doe",
    "status": "approved"
  }]
}
```

### **GET /api/v1/items?offset=0&limit=10**
Get saved items with pagination

---

## 🐛 **Troubleshooting**

### **Backend Connection Error**
```
Error: Network Error
```
**Solution**: Ensure backend is running on port 8000
```bash
cd backend
python main.py
```

### **CORS Error**
```
Access to XMLHttpRequest blocked by CORS policy
```
**Solution**: Backend should allow `http://localhost:3000`

Check `backend/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### **Page Not Found (404)**
- Make sure you're on the correct URL
- Use the sidebar navigation
- Routes:
  - `/` - Dashboard
  - `/estimation` - Cost Estimation
  - `/saved-items` - Saved Items

### **Items Not Saving**
- Check browser console for errors (F12)
- Verify backend is running
- Check network tab in DevTools
- Ensure all required fields are filled

---

## 🚀 **Next Steps**

1. **Test the complete flow**:
   - Create estimate → Review → Save → View in Saved Items

2. **Customize**:
   - Update colors in `App.tsx` theme
   - Add more categories in `CostEstimation.tsx`
   - Modify subcategories in backend

3. **Deploy**:
   - Frontend: Vercel, Netlify, or Azure Static Web Apps
   - Backend: Azure Container Apps (deployment files already created)

---

## 📚 **Documentation**

- **Backend API**: http://localhost:8000/docs
- **MUI Components**: https://mui.com/
- **React Router**: https://reactrouter.com/
- **Vite**: https://vitejs.dev/

---

## 💡 **Tips**

- Use browser DevTools (F12) to inspect network requests
- Check console for any JavaScript errors
- Use the refresh button in Saved Items to reload data
- Estimates are editable in the review step
- All data is saved to Azure Cosmos DB with zipcode as partition key

---

## ✨ **Success Indicators**

✅ Frontend running on http://localhost:3000
✅ Backend running on http://localhost:8000
✅ No console errors
✅ Can create estimates
✅ Can save items
✅ Can view saved items with pagination
✅ Microsoft-inspired design loads correctly
✅ Responsive layout works

---

**Enjoy using HomeGuard Cost Estimation System!** 🎉
