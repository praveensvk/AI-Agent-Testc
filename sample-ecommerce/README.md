# Sample E-Commerce Application

A fully functional e-commerce web application built with Node.js/Express (backend) and React (frontend). This application is designed to be used as a testing target for the AI-Agent Testing Platform.

## Features

### Authentication
- User registration and login
- JWT token-based authentication
- User profiles with shipping addresses

### Products
- Browse products by category (Electronics, Accessories)
- Search products by name and description
- View product details with images and stock info
- Filter products by category

### Shopping Cart
- Add/remove items from cart
- Update quantities
- View cart summary with totals
- Clear entire cart

### Checkout & Orders
- Secure checkout process
- Multiple payment fields (card, CVV, expiry)
- Order confirmation
- Order history and tracking

## Technology Stack

### Backend
- **Node.js** with Express.js
- **JWT** for authentication
- **In-memory database** (easily replaceable with real DB)

### Frontend
- **React 18** with hooks
- **React Router** for navigation
- **Axios** for API calls
- **CSS3** for styling (responsive design)

## Getting Started

### Prerequisites

- Node.js 14+ and npm
- npm or yarn package manager

### Backend Setup

1. Navigate to backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the server:
   ```bash
   npm start
   ```

   The backend will run on `http://localhost:5000`

### Frontend Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

   The frontend will open at `http://localhost:3000`

## Default Test Credentials

**Email:** test@example.com
**Password:** password123

## API Documentation

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/profile` - Get user profile (requires auth token)

### Products
- `GET /api/products` - Get all products (supports `category` and `search` query params)
- `GET /api/products/:id` - Get product details
- `GET /api/products/category/:category` - Get products by category

### Cart
- `GET /api/cart` - Get user's cart (requires auth)
- `POST /api/cart/add` - Add item to cart (requires auth)
- `POST /api/cart/remove` - Remove item from cart (requires auth)
- `POST /api/cart/clear` - Clear entire cart (requires auth)

### Orders
- `POST /api/orders` - Create new order from cart (requires auth)
- `GET /api/orders` - Get user's orders (requires auth)
- `GET /api/orders/:id` - Get order details (requires auth)

### Health
- `GET /health` - Backend health check
- `GET /api/health` - API health check

## Sample Test Paths for UI Testing Platform

Here are some useful test paths you can use with your AI-Agent Testing Platform:

### Login Tests
- **Path:** `/login`
- **Test Cases:** 
  - Successful login with valid credentials
  - Failed login with invalid credentials
  - Redirect after successful login

### Product Listing Tests
- **Path:** `/`
- **Test Cases:**
  - Display all products
  - Filter by category
  - Search for products
  - View product details

### Cart Tests
- **Path:** `/cart`
- **Test Cases:**
  - Add item to cart
  - Remove item from cart
  - Clear cart
  - Update quantities

### Checkout Tests
- **Path:** `/checkout`
- **Test Cases:**
  - Enter shipping information
  - Enter payment details
  - Place order
  - Order confirmation

### Order History Tests
- **Path:** `/orders`
- **Test Cases:**
  - View all orders
  - View order details
  - Check order status

## Known Limitations

- This is a sample app with in-memory database (data resets on server restart)
- Passwords are stored in plain text (for demo purposes only)
- Frontend and backend must run on localhost:3000 and localhost:5000
- CORS is enabled for all origins (development only)

## Production Notes

Before deploying to production, consider:
1. Implement proper database (PostgreSQL, MongoDB, etc.)
2. Hash passwords using bcrypt or similar
3. Implement rate limiting for API endpoints
4. Add input validation and sanitization
5. Use HTTPS for all communications
6. Implement proper error handling
7. Add comprehensive logging
8. Set up CI/CD pipeline
9. Configure CORS properly
10. Implement caching strategies

## License

MIT
