#!/bin/bash

# Automotive Predictive Maintenance Frontend - Quick Setup Script

echo "=================================================="
echo "🚗 Automotive Predictive Maintenance Frontend"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Node.js
echo -e "${BLUE}Checking Node.js...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}❌ Node.js not found. Please install Node.js 18+ first.${NC}"
    exit 1
fi

NODE_VERSION=$(node --version)
echo -e "${GREEN}✅ Node.js ${NODE_VERSION} found${NC}"
echo ""

# Check npm
echo -e "${BLUE}Checking npm...${NC}"
if ! command -v npm &> /dev/null; then
    echo -e "${YELLOW}❌ npm not found. Please install npm first.${NC}"
    exit 1
fi

NPM_VERSION=$(npm --version)
echo -e "${GREEN}✅ npm ${NPM_VERSION} found${NC}"
echo ""

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
npm install

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Dependencies installed successfully${NC}"
else
    echo -e "${YELLOW}❌ Failed to install dependencies${NC}"
    exit 1
fi
echo ""

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo -e "${YELLOW}⚠️  .env.local not found, creating from template...${NC}"
    cat > .env.local << EOF
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Feature Flags
NEXT_PUBLIC_ENABLE_WEBSOCKET=true
NEXT_PUBLIC_ENABLE_MAP=true
NEXT_PUBLIC_POLLING_INTERVAL=10000

# Dashboard Configuration
NEXT_PUBLIC_DASHBOARD_REFRESH_RATE=10000
NEXT_PUBLIC_MAX_ALERTS_DISPLAY=50
EOF
    echo -e "${GREEN}✅ .env.local created${NC}"
else
    echo -e "${GREEN}✅ .env.local already exists${NC}"
fi
echo ""

# Check backend availability
echo -e "${BLUE}Checking backend availability...${NC}"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is running at http://localhost:8000${NC}"
else
    echo -e "${YELLOW}⚠️  Backend not responding at http://localhost:8000${NC}"
    echo -e "${YELLOW}   Make sure backend services are running before starting the frontend${NC}"
fi
echo ""

# Success message
echo -e "${GREEN}=================================================="
echo -e "✅ Frontend setup complete!"
echo -e "==================================================${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "1. Start backend services (if not running):"
echo -e "   ${YELLOW}cd ../docker && docker-compose up -d${NC}"
echo ""
echo -e "2. Start the development server:"
echo -e "   ${YELLOW}npm run dev${NC}"
echo ""
echo -e "3. Open your browser:"
echo -e "   ${YELLOW}http://localhost:3000${NC}"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"
