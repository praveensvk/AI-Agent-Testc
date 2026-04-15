/**
 * In-memory database for sample e-commerce app
 */

// Sample products
const products = [
  {
    id: 1,
    name: "Wireless Headphones",
    price: 79.99,
    category: "Electronics",
    description: "High-quality wireless headphones with noise cancellation",
    image: "https://via.placeholder.com/300x200?text=Headphones",
    stock: 15,
  },
  {
    id: 2,
    name: "USB-C Cable",
    price: 12.99,
    category: "Accessories",
    description: "Durable USB-C charging and data cable",
    image: "https://via.placeholder.com/300x200?text=USB+Cable",
    stock: 50,
  },
  {
    id: 3,
    name: "Phone Case",
    price: 19.99,
    category: "Accessories",
    description: "Protective phone case with shock absorption",
    image: "https://via.placeholder.com/300x200?text=Phone+Case",
    stock: 30,
  },
  {
    id: 4,
    name: "Portable Charger",
    price: 34.99,
    category: "Electronics",
    description: "20000mAh portable power bank",
    image: "https://via.placeholder.com/300x200?text=Charger",
    stock: 20,
  },
  {
    id: 5,
    name: "Screen Protector",
    price: 9.99,
    category: "Accessories",
    description: "Tempered glass screen protector",
    image: "https://via.placeholder.com/300x200?text=Protector",
    stock: 40,
  },
  {
    id: 6,
    name: "Smart Watch",
    price: 199.99,
    category: "Electronics",
    description: "Feature-rich smartwatch with health tracking",
    image: "https://via.placeholder.com/300x200?text=SmartWatch",
    stock: 10,
  },
];

// Sample users
const users = [
  {
    id: 1,
    email: "test@example.com",
    password: "password123", // In production, this would be hashed
    name: "John Doe",
    address: "123 Main St, New York, NY 10001",
  },
  {
    id: 2,
    email: "user@example.com",
    password: "password456",
    name: "Jane Smith",
    address: "456 Oak Ave, Los Angeles, CA 90001",
  },
];

// Cart storage (in production, this would be in database/session)
const carts = {};

// Orders storage
const orders = [];

module.exports = {
  products,
  users,
  carts,
  orders,
};
