#!/bin/bash
# =============================================================================
# VPT Scanner Installation Script
# =============================================================================
# This script installs all required dependencies for the VPT Scanner including:
# - System packages (apt)
# - Python packages (pip)
# - Playwright browsers
# 
# Usage: ./install.sh
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}==============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}==============================================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_header "VPT Scanner Installation"

# =============================================================================
# Step 1: Check for Python 3
# =============================================================================
print_info "Checking for Python 3..."

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_success "Python 3 found: $PYTHON_VERSION"
else
    print_error "Python 3 is not installed"
    echo "Please install Python 3.10 or higher:"
    echo "  sudo apt-get install python3 python3-pip python3-venv"
    exit 1
fi

# Check Python version is >= 3.10
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    print_error "Python 3.10 or higher is required (found $PYTHON_MAJOR.$PYTHON_MINOR)"
    exit 1
fi

# =============================================================================
# Step 2: Install System Dependencies
# =============================================================================
print_header "Installing System Dependencies"

# List of required apt packages for Playwright/Chromium
APT_PACKAGES=(
    "libnspr4"
    "libnss3"
    "libatk1.0-0t64"
    "libatk-bridge2.0-0t64"
    "libcups2t64"
    "libdrm2"
    "libxcomposite1"
    "libxdamage1"
    "libxfixes3"
    "libxrandr2"
    "libgbm1"
    "libxkbcommon0"
    "libpango-1.0-0"
    "libcairo2"
    "libasound2t64"
)

# Check if we can run sudo
if ! command -v sudo &> /dev/null; then
    print_warning "sudo not available, skipping system package installation"
    print_info "You may need to install system packages manually if Playwright fails"
else
    print_info "Installing system packages (may require sudo password)..."
    
    # Update package list
    sudo apt-get update -qq
    
    # Install packages, ignoring any that don't exist (for compatibility)
    for pkg in "${APT_PACKAGES[@]}"; do
        if sudo apt-get install -y -qq "$pkg" 2>/dev/null; then
            print_success "Installed $pkg"
        else
            # Try alternative package name for older Ubuntu versions
            alt_pkg="${pkg%t64}"  # Remove t64 suffix for older Ubuntu
            if [ "$alt_pkg" != "$pkg" ] && sudo apt-get install -y -qq "$alt_pkg" 2>/dev/null; then
                print_success "Installed $alt_pkg (alternative)"
            else
                print_warning "Could not install $pkg (may already be installed or not needed)"
            fi
        fi
    done
fi

# =============================================================================
# Step 3: Create/Activate Virtual Environment
# =============================================================================
print_header "Setting Up Python Virtual Environment"

VENV_DIR="$SCRIPT_DIR/.venv"

if [ -d "$VENV_DIR" ]; then
    print_success "Virtual environment already exists at $VENV_DIR"
else
    print_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment created at $VENV_DIR"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"
print_success "Virtual environment activated"

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip -q
print_success "pip upgraded"

# =============================================================================
# Step 4: Install Python Dependencies
# =============================================================================
print_header "Installing Python Dependencies"

if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    print_info "Installing from requirements.txt..."
    pip install -r "$SCRIPT_DIR/requirements.txt" -q
    print_success "Python dependencies installed"
else
    print_warning "requirements.txt not found, installing core packages..."
    pip install flask playwright supabase python-dotenv google-genai requests -q
    print_success "Core packages installed"
fi

# =============================================================================
# Step 5: Install Playwright Browsers
# =============================================================================
print_header "Installing Playwright Browsers"

print_info "Installing Chromium browser for Playwright..."
playwright install chromium

if [ $? -eq 0 ]; then
    print_success "Playwright Chromium installed"
else
    print_error "Failed to install Playwright Chromium"
    print_info "Try running: playwright install chromium"
fi

# Also install system dependencies for Playwright (if available)
print_info "Installing Playwright system dependencies..."
playwright install-deps chromium 2>/dev/null || print_warning "Could not auto-install Playwright deps (may need manual installation)"

# =============================================================================
# Step 6: Create .env file if it doesn't exist
# =============================================================================
print_header "Configuration"

if [ ! -f "$SCRIPT_DIR/.env" ]; then
    print_info "Creating .env file from template..."
    cat > "$SCRIPT_DIR/.env" << 'EOF'
# VPT Scanner Configuration
# =========================

# Supabase (optional - for cloud sync)
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_SERVICE_KEY=your-service-key

# Scanner performance tuning
VPT_MAX_WORKERS=32
VPT_REQUEST_DELAY_SEC=0.05
VPT_ENABLE_PGE=false

# Google Gemini API Key (for deep research and condition scanning)
# Get your API key from: https://makersuite.google.com/app/apikey
GOOGLE_API_KEY=

# Enable/disable research scanner
VPT_ENABLE_RESEARCH=true
EOF
    print_success ".env file created"
    print_warning "Please edit .env and add your GOOGLE_API_KEY for AI features"
else
    print_success ".env file already exists"
fi

# =============================================================================
# Step 7: Verify Installation
# =============================================================================
print_header "Verifying Installation"

# Run a quick import test
python3 -c "
import sys
errors = []

try:
    import flask
    print('✓ Flask:', flask.__version__)
except ImportError as e:
    errors.append(f'Flask: {e}')

try:
    from playwright.sync_api import sync_playwright
    print('✓ Playwright: installed')
except ImportError as e:
    errors.append(f'Playwright: {e}')

try:
    from google import genai
    print('✓ Google GenAI: installed')
except ImportError as e:
    errors.append(f'Google GenAI: {e}')

try:
    from dotenv import load_dotenv
    print('✓ python-dotenv: installed')
except ImportError as e:
    errors.append(f'python-dotenv: {e}')

if errors:
    print()
    for err in errors:
        print(f'✗ {err}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    print_success "All Python dependencies verified"
else
    print_error "Some dependencies failed to install"
    exit 1
fi

# =============================================================================
# Complete
# =============================================================================
print_header "Installation Complete!"

echo -e "${GREEN}VPT Scanner is ready to use!${NC}\n"

echo "To start the web interface:"
echo -e "  ${BLUE}source .venv/bin/activate${NC}"
echo -e "  ${BLUE}python webgui/app.py${NC}"
echo ""
echo "To run the scanner:"
echo -e "  ${BLUE}source .venv/bin/activate${NC}"
echo -e "  ${BLUE}python run_all.py --continuous${NC}"
echo ""
echo "Default login: noob / P@ssw0rdz"
echo "Web UI: http://localhost:5000"
echo ""

# Reminder about .env
if ! grep -q "^GOOGLE_API_KEY=." "$SCRIPT_DIR/.env" 2>/dev/null; then
    print_warning "Don't forget to set GOOGLE_API_KEY in .env for AI features!"
fi
