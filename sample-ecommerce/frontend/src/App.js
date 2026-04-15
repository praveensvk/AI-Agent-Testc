import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import axios from "axios";

// Import pages
import Home from "./pages/Home";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ProductDetail from "./pages/ProductDetail";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import Orders from "./pages/Orders";

// Import components
import Navigation from "./components/Navigation";

import "./styles/App.css";

function App() {
  const [user, setUser] = useState(null);
  const [cart, setCart] = useState([]);

  useEffect(() => {
    // Load user from localStorage
    const storedUser = localStorage.getItem("user");
    const storedToken = localStorage.getItem("token");
    
    if (storedUser && storedToken) {
      setUser(JSON.parse(storedUser));
      axios.defaults.headers.common["Authorization"] = `Bearer ${storedToken}`;
      fetchCart();
    }
  }, []);

  const fetchCart = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get("/api/cart", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCart(response.data.items || []);
    } catch (error) {
      console.error("Error fetching cart", error);
    }
  };

  const handleLogin = (userData, token) => {
    setUser(userData);
    localStorage.setItem("user", JSON.stringify(userData));
    localStorage.setItem("token", token);
    axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    fetchCart();
  };

  const handleLogout = () => {
    setUser(null);
    setCart([]);
    localStorage.removeItem("user");
    localStorage.removeItem("token");
    delete axios.defaults.headers.common["Authorization"];
  };

  return (
    <Router>
      <div className="App">
        <Navigation user={user} onLogout={handleLogout} cartCount={cart.length} />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login onLogin={handleLogin} />} />
            <Route path="/register" element={<Register onLogin={handleLogin} />} />
            <Route path="/product/:id" element={<ProductDetail onAddToCart={fetchCart} />} />
            <Route path="/cart" element={<Cart onCartUpdate={fetchCart} />} />
            <Route path="/checkout" element={<Checkout onCheckout={fetchCart} />} />
            <Route
              path="/orders"
              element={user ? <Orders /> : <Login onLogin={handleLogin} />}
            />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
