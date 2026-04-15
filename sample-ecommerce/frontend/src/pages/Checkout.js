import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import "../styles/Checkout.css";

function Checkout({ onCheckout }) {
  const [cart, setCart] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
    fetchCart();
  }, []);

  const fetchCart = async () => {
    try {
      const token = localStorage.getItem("token");
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

  const handlePlaceOrder = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const token = localStorage.getItem("token");
      const response = await axios.post(
        "/api/orders",
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      onCheckout();
      navigate("/orders");
    } catch (error) {
      setError(error.response?.data?.error || "Failed to place order");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading checkout...</div>;
  }

  if (!cart || !cart.items || cart.items.length === 0) {
    return (
      <div className="checkout">
        <div className="error-message">Your cart is empty</div>
      </div>
    );
  }

  const subtotal = cart.total || 0;
  const shipping = 10;
  const tax = subtotal * 0.1;
  const total = subtotal + shipping + tax;

  return (
    <div className="checkout">
      <h1>Checkout</h1>

      {error && <div className="error-message">{error}</div>}

      <div className="checkout-container">
        <div className="checkout-form">
          <form onSubmit={handlePlaceOrder}>
            <div className="form-section">
              <h2>Shipping Information</h2>
              <div className="form-group">
                <label>Name:</label>
                <input type="text" value={user?.name || ""} disabled />
              </div>
              <div className="form-group">
                <label>Email:</label>
                <input type="email" value={user?.email || ""} disabled />
              </div>
              <div className="form-group">
                <label>Shipping Address:</label>
                <input type="text" value={user?.address || ""} disabled />
              </div>
            </div>

            <div className="form-section">
              <h2>Payment Information</h2>
              <div className="form-group">
                <label htmlFor="card-number">Card Number:</label>
                <input
                  type="text"
                  id="card-number"
                  placeholder="4111 1111 1111 1111"
                  defaultValue="4111111111111111"
                  required
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="expiry">Expiry Date:</label>
                  <input
                    type="text"
                    id="expiry"
                    placeholder="MM/YY"
                    defaultValue="12/25"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="cvv">CVV:</label>
                  <input
                    type="text"
                    id="cvv"
                    placeholder="123"
                    defaultValue="123"
                    required
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-block"
              id="place-order-button"
              disabled={submitting}
            >
              {submitting ? "Processing..." : "Place Order"}
            </button>
          </form>
        </div>

        <div className="checkout-summary">
          <div className="summary-box">
            <h2>Order Summary</h2>

            <div className="summary-items">
              {cart.items.map((item) => (
                <div key={item.productId} className="summary-item">
                  <span>{item.name} x {item.quantity}</span>
                  <span>${(item.price * item.quantity).toFixed(2)}</span>
                </div>
              ))}
            </div>

            <div className="summary-totals">
              <div className="summary-row">
                <span>Subtotal:</span>
                <span>${subtotal.toFixed(2)}</span>
              </div>
              <div className="summary-row">
                <span>Shipping:</span>
                <span>${shipping.toFixed(2)}</span>
              </div>
              <div className="summary-row">
                <span>Tax:</span>
                <span>${tax.toFixed(2)}</span>
              </div>
              <div className="summary-row total">
                <span>Total:</span>
                <span>${total.toFixed(2)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Checkout;
