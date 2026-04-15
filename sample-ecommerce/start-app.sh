#!/bin/bash

# Start E-Commerce Application on Linux/Mac

echo ""
echo "===================================="
echo "  TechStore E-Commerce App Startup"
echo "===================================="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Starting Backend (Port 5000)..."
cd "$SCRIPT_DIR/backend"

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing backend dependencies..."
    npm install
fi

# Start backend in background
npm start &
BACKEND_PID=$!

echo ""
echo "Waiting 3 seconds before starting frontend..."
sleep 3

echo "Starting Frontend (Port 3000)..."
cd "$SCRIPT_DIR/frontend"

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start frontend
npm start &
FRONTEND_PID=$!

echo ""
echo "===================================="
echo "  Services Starting..."
echo "===================================="
echo ""
echo "Backend:  http://localhost:5000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Test Credentials:"
echo "  Email:    test@example.com"
echo "  Password: password123"
echo ""
echo "Press Ctrl+C to stop all services..."
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID

echo "All services stopped."
