import React from "react";
import { Link, useNavigate } from "react-router-dom";
import "../styles/Navigation.css";

function Navigation({ user, onLogout, cartCount }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    onLogout();
    navigate("/");
  };

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo" id="logo">
        TechStore
        </Link>

        <div className="navbar-menu">
          <Link to="/" className="nav-link">
            Home
          </Link>

          {user ? (
            <>
              <span className="nav-user">Welcome, {user.name}!</span>
              <Link to="/cart" className="nav-link" id="cart-link">
                🛒 Cart ({cartCount})
              </Link>
              <Link to="/orders" className="nav-link">
                Orders
              </Link>
              <button onClick={handleLogout} className="btn btn-danger" id="logout-btn">
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link" id="login-link">
                Login
              </Link>
              <Link to="/register" className="nav-link">
                Register
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

export default Navigation;
