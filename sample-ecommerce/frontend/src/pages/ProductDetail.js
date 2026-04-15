import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import "../styles/ProductDetail.css";

function ProductDetail({ onAddToCart }) {
  const { id } = useParams();
  const [product, setProduct] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    fetchProduct();
  }, [id]);

  const fetchProduct = async () => {
    try {
      const response = await axios.get(`/api/products/${id}`);
      setProduct(response.data);
    } catch (error) {
      setError("Failed to load product");
    } finally {
      setLoading(false);
    }
  };

  const handleAddToCart = async () => {
    const token = localStorage.getItem("token");

    if (!token) {
      navigate("/login");
      return;
    }

    try {
      await axios.post(
        "/api/cart/add",
        { productId: parseInt(id), quantity: parseInt(quantity) },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setSuccess(`Added ${quantity} item(s) to cart`);
      onAddToCart();

      setTimeout(() => {
        navigate("/cart");
      }, 1000);
    } catch (error) {
      setError(error.response?.data?.error || "Failed to add to cart");
    }
  };

  if (loading) {
    return <div className="loading">Loading product...</div>;
  }

  if (error) {
    return <div className="error-message">{error}</div>;
  }

  if (!product) {
    return <div className="error-message">Product not found</div>;
  }

  return (
    <div className="product-detail">
      <button onClick={() => navigate("/")} className="btn btn-secondary">
        ← Back to Products
      </button>

      <div className="product-detail-container">
        <div className="product-image-container">
          <img src={product.image} alt={product.name} />
        </div>

        <div className="product-info">
          <h1>{product.name}</h1>
          <p className="category">{product.category}</p>
          <p className="description">{product.description}</p>

          <div className="price-section">
            <p className="price">${product.price.toFixed(2)}</p>
            <p className="stock">
              {product.stock > 0 ? (
                <span className="in-stock">In Stock ({product.stock})</span>
              ) : (
                <span className="out-of-stock">Out of Stock</span>
              )}
            </p>
          </div>

          {error && <div className="error-message">{error}</div>}
          {success && <div className="success-message">{success}</div>}

          <div className="cart-section">
            <div className="quantity-selector">
              <label htmlFor="quantity">Quantity:</label>
              <input
                type="number"
                id="quantity"
                min="1"
                max={product.stock}
                value={quantity}
                onChange={(e) => setQuantity(parseInt(e.target.value))}
              />
            </div>

            <button
              onClick={handleAddToCart}
              className="btn btn-primary"
              id="add-to-cart-button"
              disabled={product.stock === 0}
            >
              Add to Cart
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProductDetail;
