# E-Commerce Sample Application

Quick-start directory for running the sample e-commerce app locally.

## Quick Start

### Windows
```bash
start-app.bat
```

### Linux/Mac
```bash
chmod +x start-app.sh
./start-app.sh
```

### Manual Start

**Terminal 1 - Backend:**
```bash
cd backend
npm install
npm start
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm install
npm start
```

## Test Credentials

- **Email:** test@example.com
- **Password:** password123

## Endpoints

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:5000

## Troubleshooting

### Port Already in Use
If port 3000 or 5000 is already in use:

**Frontend on different port:**
```bash
PORT=3001 npm start
```

**Backend on different port:**
Edit `server.js` and change `const PORT = 5000` to your desired port

### Dependencies Issues
Clear and reinstall dependencies:
```bash
# Backend
cd backend
rm -rf node_modules package-lock.json
npm install

# Frontend
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Using with AI-Agent Testing Platform

This sample e-commerce app is perfect for testing your UI Testing Platform:

1. Start the app using the startup scripts
2. Create a test suite with base URL: `http://localhost:3000`
3. Create test cases for each path:
   - `/` - Product Listing
   - `/login` - Authentication
   - `/register` - User Registration
   - `/product/1` - Product Details
   - `/cart` - Shopping Cart
   - `/checkout` - Checkout Process
   - `/orders` - Order History

4. Use the LLM to generate test cases for each page
5. Run tests and verify results

Happy testing!
