import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import "../styles/Home.css";

function Home() {
  const [products, setProducts] = useState([]);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProducts();
  }, [category, search]);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      let url = "/api/products";
      const params = new URLSearchParams();

      if (category) params.append("category", category);
      if (search) params.append("search", search);

      if (params.toString()) {
        url += "?" + params.toString();
      }

      const response = await axios.get(url);
      setProducts(response.data);
    } catch (error) {
      console.error("Error fetching products", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="home">
      <div className="hero">
        <h1>Welcome to TechStore</h1>
        <p>Your one-stop shop for all electronics and accessories</p>
      </div>

      <div className="filters">
        <input
          type="text"
          id="search-input"
          placeholder="Search products..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <select
          id="category-select"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">All Categories</option>
          <option value="Electronics">Electronics</option>
          <option value="Accessories">Accessories</option>
        </select>
      </div>

      {loading ? (
        <div className="loading">Loading products...</div>
      ) : (
        <div className="products-grid">
          {products.length === 0 ? (
            <div className="no-products">No products found</div>
          ) : (
            products.map((product) => (
              <div key={product.id} className="product-card" data-testid={`product-${product.id}`}>
                <img src={product.image} alt={product.name} className="product-image" />
                <h3>{product.name}</h3>
                <p className="product-category">{product.category}</p>
                <p className="product-description">{product.description}</p>
                <p className="product-price">${product.price.toFixed(2)}</p>
                <p className="product-stock">
                  {product.stock > 0 ? `In Stock (${product.stock})` : "Out of Stock"}
                </p>
                <Link
                  to={`/product/${product.id}`}
                  className="btn btn-primary"
                  id={`view-product-${product.id}`}
                >
                  View Details
                </Link>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default Home;
