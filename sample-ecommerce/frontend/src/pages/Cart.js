import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import "../styles/Cart.css";

function Cart({ onCartUpdate }) {
  const [cart, setCart] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    fetchCart();
  }, []);

  const fetchCart = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        navigate("/login");
        return;
      }

      const response = await axios.get("/api/cart", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCart(response.data);
    } catch (error) {
      setError("Failed to load cart");
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveItem = async (productId) => {
    try {
      const token = localStorage.getItem("token");
      await axios.post(
        "/api/cart/remove",
        { productId },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      fetchCart();
      onCartUpdate();
    } catch (error) {
      setError("Failed to remove item");
    }
  };

  const handleClearCart = async () => {
    try {
      const token = localStorage.getItem("token");
      await axios.post(
        "/api/cart/clear",
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      fetchCart();
      onCartUpdate();
    } catch (error) {
      setError("Failed to clear cart");
    }
  };

  if (loading) {
    return <div className="loading">Loading cart...</div>;
  }

  if (!cart) {
    return <div className="error-message">Cart not available</div>;
  }

  return (
    <div className="cart">
      <h1>Shopping Cart</h1>

      {error && <div className="error-message">{error}</div>}

      {cart.items && cart.items.length === 0 ? (
        <div className="empty-cart">
          <p>Your cart is empty</p>
          <Link to="/" className="btn btn-primary">
            Continue Shopping
          </Link>
        </div>
      ) : (
        <div className="cart-container">
          <div className="cart-items">
            <table className="cart-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Price</th>
                  <th>Quantity</th>
                  <th>Subtotal</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {cart.items.map((item) => (
                  <tr key={item.productId} className="cart-item" data-testid={`cart-item-${item.productId}`}>
                    <td className="product-name">{item.name}</td>
                    <td className="product-price">${item.price.toFixed(2)}</td>
                    <td className="product-quantity">{item.quantity}</td>
                    <td className="product-subtotal">
                      ${(item.price * item.quantity).toFixed(2)}
                    </td>
                    <td className="product-action">
                      <button
                        onClick={() => handleRemoveItem(item.productId)}
                        className="btn btn-danger"
                        id={`remove-item-${item.productId}`}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="cart-summary">
            <div className="summary-box">
              <h2>Order Summary</h2>
              <div className="summary-row">
                <span>Subtotal:</span>
                <span>${cart.total.toFixed(2)}</span>
              </div>
              <div className="summary-row">
                <span>Shipping:</span>
                <span>$10.00</span>
              </div>
              <div className="summary-row">
                <span>Tax:</span>
                <span>${(cart.total * 0.1).toFixed(2)}</span>
              </div>
              <div className="summary-row total">
                <span>Total:</span>
                <span>${(cart.total + 10 + cart.total * 0.1).toFixed(2)}</span>
              </div>

              <button
                onClick={() => navigate("/checkout")}
                className="btn btn-primary btn-block"
                id="checkout-button"
              >
                Proceed to Checkout
              </button>

              <button
                onClick={handleClearCart}
                className="btn btn-secondary btn-block"
                id="clear-cart-button"
              >
                Clear Cart
              </button>

              <Link to="/" className="btn btn-secondary btn-block">
                Continue Shopping
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Cart;
