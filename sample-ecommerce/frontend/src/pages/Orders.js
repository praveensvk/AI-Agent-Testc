import React, { useState, useEffect } from "react";
import axios from "axios";
import "../styles/Orders.css";

function Orders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get("/api/orders", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setOrders(response.data);
    } catch (error) {
      setError("Failed to load orders");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading orders...</div>;
  }

  return (
    <div className="orders">
      <h1>My Orders</h1>

      {error && <div className="error-message">{error}</div>}

      {orders.length === 0 ? (
        <div className="no-orders">
          <p>You haven't placed any orders yet</p>
        </div>
      ) : (
        <div className="orders-list">
          {orders.map((order) => (
            <div key={order.id} className="order-card" data-testid={`order-${order.id}`}>
              <div className="order-header">
                <h3>Order #{order.id}</h3>
                <span className={`order-status ${order.status}`}>{order.status}</span>
              </div>

              <div className="order-details">
                <p>
                  <strong>Date:</strong> {new Date(order.createdAt).toLocaleDateString()}
                </p>
                <p>
                  <strong>Items:</strong> {order.items.length}
                </p>
                <p>
                  <strong>Total:</strong> ${order.total.toFixed(2)}
                </p>
                <p>
                  <strong>Shipping Address:</strong> {order.shippingAddress}
                </p>
              </div>

              <div className="order-items">
                <h4>Items:</h4>
                <ul>
                  {order.items.map((item) => (
                    <li key={item.productId}>
                      {item.name} x {item.quantity} - ${(item.price * item.quantity).toFixed(2)}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Orders;
