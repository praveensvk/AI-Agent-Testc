/**
 * Express server - Sample e-commerce backend
 */

const express = require("express");
const cors = require("cors");
const bodyParser = require("body-parser");
const jwt = require("jsonwebtoken");
const db = require("./db");

const app = express();
const PORT = 5000;
const JWT_SECRET = "your-secret-key-change-in-production";

// Middleware
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Logging middleware
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
  next();
});

// Helper function to generate JWT token
function generateToken(user) {
  return jwt.sign({ id: user.id, email: user.email }, JWT_SECRET, {
    expiresIn: "24h",
  });
}

// Authentication middleware
function authenticate(req, res, next) {
  const token = req.headers.authorization?.split(" ")[1];
  if (!token) {
    return res.status(401).json({ error: "No token provided" });
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = decoded;
    next();
  } catch (error) {
    return res.status(401).json({ error: "Invalid token" });
  }
}

// ============ AUTHENTICATION ROUTES ============

/**
 * POST /api/auth/register
 * Register a new user
 */
app.post("/api/auth/register", (req, res) => {
  const { email, password, name, address } = req.body;

  // Validation
  if (!email || !password || !name) {
    return res.status(400).json({ error: "Missing required fields" });
  }

  // Check if user exists
  const existingUser = db.users.find((u) => u.email === email);
  if (existingUser) {
    return res.status(409).json({ error: "User already exists" });
  }

  // Create new user
  const newUser = {
    id: db.users.length + 1,
    email,
    password,
    name,
    address: address || "",
  };

  db.users.push(newUser);

  return res.status(201).json({
    message: "Registration successful",
    user: { id: newUser.id, email: newUser.email, name: newUser.name },
  });
});

/**
 * POST /api/auth/login
 * Login user and return JWT token
 */
app.post("/api/auth/login", (req, res) => {
  const { email, password } = req.body;

  // Validation
  if (!email || !password) {
    return res.status(400).json({ error: "Email and password required" });
  }

  // Find user
  const user = db.users.find((u) => u.email === email && u.password === password);
  if (!user) {
    return res.status(401).json({ error: "Invalid credentials" });
  }

  // Generate token
  const token = generateToken(user);

  return res.json({
    message: "Login successful",
    token,
    user: { id: user.id, email: user.email, name: user.name },
  });
});

/**
 * GET /api/auth/profile
 * Get current user profile
 */
app.get("/api/auth/profile", authenticate, (req, res) => {
  const user = db.users.find((u) => u.id === req.user.id);
  if (!user) {
    return res.status(404).json({ error: "User not found" });
  }

  return res.json({
    id: user.id,
    email: user.email,
    name: user.name,
    address: user.address,
  });
});

// ============ PRODUCT ROUTES ============

/**
 * GET /api/products
 * Get all products with optional filtering
 */
app.get("/api/products", (req, res) => {
  const { category, search } = req.query;

  let filtered = [...db.products];

  if (category) {
    filtered = filtered.filter((p) =>
      p.category.toLowerCase().includes(category.toLowerCase())
    );
  }

  if (search) {
    filtered = filtered.filter(
      (p) =>
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.description.toLowerCase().includes(search.toLowerCase())
    );
  }

  return res.json(filtered);
});

/**
 * GET /api/products/:id
 * Get product details
 */
app.get("/api/products/:id", (req, res) => {
  const product = db.products.find((p) => p.id === parseInt(req.params.id));
  if (!product) {
    return res.status(404).json({ error: "Product not found" });
  }

  return res.json(product);
});

/**
 * GET /api/products/category/:category
 * Get products by category
 */
app.get("/api/products/category/:category", (req, res) => {
  const products = db.products.filter(
    (p) => p.category.toLowerCase() === req.params.category.toLowerCase()
  );

  return res.json(products);
});

// ============ CART ROUTES ============

/**
 * GET /api/cart
 * Get current user's cart
 */
app.get("/api/cart", authenticate, (req, res) => {
  const userId = req.user.id;
  const cart = db.carts[userId] || {
    items: [],
    total: 0,
  };

  return res.json(cart);
});

/**
 * POST /api/cart/add
 * Add item to cart
 */
app.post("/api/cart/add", authenticate, (req, res) => {
  const userId = req.user.id;
  const { productId, quantity } = req.body;

  if (!productId || !quantity) {
    return res.status(400).json({ error: "Missing productId or quantity" });
  }

  const product = db.products.find((p) => p.id === productId);
  if (!product) {
    return res.status(404).json({ error: "Product not found" });
  }

  if (product.stock < quantity) {
    return res.status(400).json({ error: "Insufficient stock" });
  }

  if (!db.carts[userId]) {
    db.carts[userId] = { items: [], total: 0 };
  }

  const cart = db.carts[userId];
  const existingItem = cart.items.find((item) => item.productId === productId);

  if (existingItem) {
    existingItem.quantity += quantity;
  } else {
    cart.items.push({
      productId,
      name: product.name,
      price: product.price,
      quantity,
    });
  }

  // Calculate total
  cart.total = cart.items.reduce((sum, item) => sum + item.price * item.quantity, 0);

  return res.json({
    message: "Item added to cart",
    cart,
  });
});

/**
 * POST /api/cart/remove
 * Remove item from cart
 */
app.post("/api/cart/remove", authenticate, (req, res) => {
  const userId = req.user.id;
  const { productId } = req.body;

  if (!productId) {
    return res.status(400).json({ error: "Missing productId" });
  }

  if (!db.carts[userId]) {
    return res.status(404).json({ error: "Cart not found" });
  }

  const cart = db.carts[userId];
  cart.items = cart.items.filter((item) => item.productId !== productId);
  cart.total = cart.items.reduce((sum, item) => sum + item.price * item.quantity, 0);

  return res.json({
    message: "Item removed from cart",
    cart,
  });
});

/**
 * POST /api/cart/clear
 * Clear cart
 */
app.post("/api/cart/clear", authenticate, (req, res) => {
  const userId = req.user.id;
  db.carts[userId] = { items: [], total: 0 };

  return res.json({
    message: "Cart cleared",
    cart: db.carts[userId],
  });
});

// ============ ORDER ROUTES ============

/**
 * POST /api/orders
 * Create new order from cart
 */
app.post("/api/orders", authenticate, (req, res) => {
  const userId = req.user.id;
  const user = db.users.find((u) => u.id === userId);
  const cart = db.carts[userId];

  if (!cart || cart.items.length === 0) {
    return res.status(400).json({ error: "Cart is empty" });
  }

  const order = {
    id: db.orders.length + 1,
    userId,
    items: cart.items,
    total: cart.total,
    status: "pending",
    shippingAddress: user.address,
    createdAt: new Date(),
  };

  db.orders.push(order);

  // Clear cart
  db.carts[userId] = { items: [], total: 0 };

  return res.status(201).json({
    message: "Order created successfully",
    order,
  });
});

/**
 * GET /api/orders
 * Get current user's orders
 */
app.get("/api/orders", authenticate, (req, res) => {
  const userId = req.user.id;
  const userOrders = db.orders.filter((o) => o.userId === userId);

  return res.json(userOrders);
});

/**
 * GET /api/orders/:id
 * Get order details
 */
app.get("/api/orders/:id", authenticate, (req, res) => {
  const order = db.orders.find(
    (o) => o.id === parseInt(req.params.id) && o.userId === req.user.id
  );

  if (!order) {
    return res.status(404).json({ error: "Order not found" });
  }

  return res.json(order);
});

// ============ HEALTH CHECK ============

/**
 * GET /health
 * Health check endpoint
 */
app.get("/health", (req, res) => {
  return res.json({
    status: "ok",
    service: "E-Commerce Backend",
    timestamp: new Date(),
  });
});

/**
 * GET /api/health
 * API health check
 */
app.get("/api/health", (req, res) => {
  return res.json({
    status: "ok",
    service: "E-Commerce API",
    timestamp: new Date(),
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: "Internal server error" });
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 E-Commerce Backend running on http://localhost:${PORT}`);
  console.log(`📚 API endpoints:`);
  console.log(`   POST /api/auth/login`);
  console.log(`   POST /api/auth/register`);
  console.log(`   GET /api/products`);
  console.log(`   GET /api/cart`);
  console.log(`   POST /api/orders`);
  console.log(`   GET /api/health`);
});
