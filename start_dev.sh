#!/bin/bash
#
# ProxyPoolMaster Development Startup Script for macOS/Linux
# Usage: ./start_dev.sh [backend|api|frontend|all]
#   backend  - Start only Backend (Collectors + Testers)
#   api      - Start only API Server
#   frontend - Start only Frontend
#   all      - Start all services (default if no argument provided)
#

set -e

# Default to 'all' if no argument provided
MODE="${1:-all}"

# Colors for output
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Port configuration
API_PORT=8000
FRONTEND_PORT=5173

# ===========================================
# Load environment variables from .env file
# ===========================================
load_env_file() {
    local env_file="$1"
    
    if [ -f "$env_file" ]; then
        echo -e "${GRAY}[INFO] Loading environment from: $env_file${NC}"
        while IFS= read -r line || [ -n "$line" ]; do
            # Skip empty lines and comments
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ -z "${line// }" ]] && continue
            
            # Remove inline comments (text after #) before parsing
            local clean_line="${line%%#*}"
            # Remove trailing whitespace
            clean_line="${clean_line%% }"
            [[ -z "$clean_line" ]] && continue
            
            # Parse KEY=VALUE format
            if [[ "$clean_line" =~ ^[[:space:]]*([^=]+)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
                key="${BASH_REMATCH[1]}"
                value="${BASH_REMATCH[2]}"
                
                # Remove trailing whitespace from value
                value="${value%% }"
                
                # Remove quotes if present
                value="${value%\"}"
                value="${value#\"}"
                value="${value%\'}"
                value="${value#\'}"
                
                # Only set if not already set (allow command line override)
                if [ -z "${!key:-}" ]; then
                    export "$key=$value"
                fi
            fi
        done < "$env_file"
    else
        echo -e "${YELLOW}[WARNING] .env file not found at: $env_file${NC}"
        echo -e "${YELLOW}          Using default values...${NC}"
    fi
}

# Load .env file
ENV_FILE="$PROJECT_ROOT/.env"
load_env_file "$ENV_FILE"

# ===========================================
# Set default values if not loaded from .env
# ===========================================

# Essential defaults (used if not in .env)
export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export REDIS_DB="${REDIS_DB:-0}"
export API_TOKEN="${API_TOKEN:-test}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  ProxyPoolMaster - Development Mode${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# ===========================================
# Check and install dependencies
# ===========================================
echo -e "${YELLOW}[Check] Checking Python dependencies...${NC}"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}[ERROR] pip3 is not installed. Please install Python and pip3 first.${NC}"
    exit 1
fi

# Check concurrent-log-handler
if ! pip3 show concurrent-log-handler &> /dev/null; then
    echo -e "${YELLOW}  Installing concurrent-log-handler...${NC}"
    pip3 install "concurrent-log-handler>=0.9.20"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  [OK] concurrent-log-handler installed${NC}"
    else
        echo -e "${RED}  [ERROR] Failed to install concurrent-log-handler${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}  [OK] concurrent-log-handler is installed${NC}"
fi

# ===========================================
# Ensure logs directory exists
# ===========================================
LOGS_DIR="$PROJECT_ROOT/logs"
if [ ! -d "$LOGS_DIR" ]; then
    mkdir -p "$LOGS_DIR"
    echo -e "${GREEN}[OK] Created logs directory: $LOGS_DIR${NC}"
else
    echo -e "${GREEN}[OK] Logs directory exists: $LOGS_DIR${NC}"
fi

# Create .gitkeep for logs directory
GITKEEP_FILE="$LOGS_DIR/.gitkeep"
if [ ! -f "$GITKEEP_FILE" ]; then
    echo "# Keep logs directory in git" > "$GITKEEP_FILE"
fi

# ===========================================
# Function to check and free port
# ===========================================
check_and_free_port() {
    local port="$1"
    local service_name="$2"
    
    echo -e "${YELLOW}[Check] Checking port $port for $service_name...${NC}"
    
    # Check if port is in use (macOS compatible)
    local pids
    pids=$(lsof -ti tcp:"$port" 2>/dev/null | tr '\n' ' ' | sed 's/ $//' || true)
    
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}  Port $port is occupied (PID: $pids), attempting to free...${NC}"
        local killed=0
        for pid in $pids; do
            if kill -9 "$pid" 2>/dev/null; then
                ((killed++))
            fi
        done
        if [ $killed -gt 0 ]; then
            echo -e "${GREEN}  OK: Freed port $port (killed $killed process(es))${NC}"
            sleep 2
        else
            echo -e "${RED}  WARNING: Could not free port $port${NC}"
            return 1
        fi
    else
        echo -e "${GREEN}  OK: Port $port is available${NC}"
    fi
    return 0
}

# Check ports if needed
if [ "$MODE" = "all" ] || [ "$MODE" = "api" ]; then
    if ! check_and_free_port "$API_PORT" "API"; then
        echo -e "${RED}[ERROR] Cannot use port $API_PORT${NC}"
        exit 1
    fi
fi

# ===========================================
# Check Redis
# ===========================================
if [ "$MODE" = "all" ] || [ "$MODE" = "backend" ] || [ "$MODE" = "api" ]; then
    echo -e "${YELLOW}[Check] Checking Redis connection to $REDIS_HOST:$REDIS_PORT...${NC}"
    
    # Try to ping Redis using Python
    redis_test=$(python3 -c "
import sys
try:
    import redis
    r = redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT, socket_connect_timeout=2)
    if r.ping():
        print('OK')
    else:
        print('FAIL')
except Exception as e:
    print('FAIL')
    sys.exit(1)
" 2>&1) || redis_test="FAIL"
    
    if [ "$redis_test" = "OK" ]; then
        echo -e "${GREEN}  [OK] Redis is running on $REDIS_HOST:$REDIS_PORT${NC}"
    else
        echo -e "${RED}  [ERROR] Redis connection failed!${NC}"
        echo -e "${YELLOW}         Start Redis: docker run -d --name redis-dev -p 6379:6379 redis:7-alpine${NC}"
        exit 1
    fi
fi

echo ""

# ===========================================
# Function to start a service in a new terminal
# ===========================================
start_in_terminal() {
    local title="$1"
    local command="$2"
    local working_dir="$3"
    
    # Create a temporary script file to avoid AppleScript escaping issues
    local temp_script
    temp_script=$(mktemp)
    cat > "$temp_script" << SCRIPT_EOF
#!/bin/bash
cd "$working_dir"
echo '[INFO] Starting: $title'
$command
echo '[INFO] $title Stopped'
read -p 'Press Enter to close...'
SCRIPT_EOF
    chmod +x "$temp_script"
    
    # Try different terminal emulators
    if command -v osascript &> /dev/null; then
        # macOS - use AppleScript to open Terminal.app
        # Escape backslashes and quotes for AppleScript
        local script_path_escaped
        script_path_escaped=$(echo "$temp_script" | sed 's/\\/\\\\/g; s/"/\\"/g')
        osascript <<EOF
            tell application "Terminal"
                do script "bash \"$script_path_escaped\""
                set custom title of front window to "$title"
            end tell
EOF
    elif command -v gnome-terminal &> /dev/null; then
        gnome-terminal --title="$title" -- bash "$temp_script"
    elif command -v xterm &> /dev/null; then
        xterm -T "$title" -e "bash '$temp_script'" &
    else
        # Fallback: run in background with nohup
        echo -e "${YELLOW}[WARNING] No suitable terminal found. Running in background...${NC}"
        bash "$temp_script" > /tmp/${title// /_}.log 2>&1 &
        echo -e "${GREEN}[OK] $title started in background (logs: /tmp/${title// /_}.log)${NC}"
    fi
}

# ===========================================
# Start services
# ===========================================

# Start Backend (Collectors + Testers)
if [ "$MODE" = "all" ] || [ "$MODE" = "backend" ]; then
    echo -e "${YELLOW}[1/3] Starting Backend (Collectors + Testers)...${NC}"
    
    # Create a temporary script for the backend
    BACKEND_SCRIPT=$(mktemp)
    cat > "$BACKEND_SCRIPT" << BACKEND_EOF
#!/bin/bash
SCRIPT_DIR="$PROJECT_ROOT"
cd "$SCRIPT_DIR"

# Load .env file if exists (remove inline comments and export)
if [ -f ".env" ]; then
    set -a
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip empty lines and pure comment lines
        [[ -z "\$line" ]] && continue
        [[ "\$line" =~ ^[[:space:]]*# ]] && continue
        # Remove inline comments (text after #), preserving quotes
        clean_line="\${line%%#*}"
        # Remove trailing whitespace
        clean_line="\${clean_line%%[[:space:]]}"
        [[ -z "\$clean_line" ]] && continue
        # Export only if contains =
        [[ "\$clean_line" == *"="* ]] && export "\$clean_line"
    done < ".env"
    set +a
fi

# Set defaults
export REDIS_HOST="${REDIS_HOST:-localhost}"
export API_TOKEN="${API_TOKEN:-test}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

echo -e "\033[1;36m[Backend] Starting...\033[0m"
python3 main.py
echo -e "\n\033[1;31m[Backend Stopped]\033[0m"
read -p "Press Enter to close..."
BACKEND_EOF
    chmod +x "$BACKEND_SCRIPT"
    
    start_in_terminal "ProxyPoolMaster Backend" "bash $BACKEND_SCRIPT" "$PROJECT_ROOT"
    sleep 2
fi

# Start API Server
if [ "$MODE" = "all" ] || [ "$MODE" = "api" ]; then
    echo -e "${YELLOW}[2/3] Starting API Server on port $API_PORT...${NC}"
    
    # Determine if collector/tester should be disabled
    # 当运行 all 或 backend 模式时，Backend 会启动 Collector/Tester，API 不需要重复启动
    DISABLE_TESTER="0"
    DISABLE_COLLECTOR="0"
    if [ "$MODE" = "all" ] || [ "$MODE" = "backend" ]; then
        DISABLE_TESTER="1"
        DISABLE_COLLECTOR="1"
    fi
    
    # Create a temporary script for the API
    API_SCRIPT=$(mktemp)
    cat > "$API_SCRIPT" << API_EOF
#!/bin/bash
SCRIPT_DIR="$PROJECT_ROOT"
cd "\$SCRIPT_DIR"

# Load .env file if exists (remove inline comments)
if [ -f ".env" ]; then
    set -a
    while IFS= read -r line || [[ -n "\$line" ]]; do
        [[ -z "\$line" ]] && continue
        [[ "\$line" =~ ^[[:space:]]*# ]] && continue
        clean_line="\${line%%#*}"
        clean_line="\${clean_line%%[[:space:]]}"
        [[ -z "\$clean_line" ]] && continue
        [[ "\$clean_line" == *"="* ]] && export "\$clean_line"
    done < ".env"
    set +a
fi

# Set defaults
export REDIS_HOST="\${REDIS_HOST:-localhost}"
export API_TOKEN="\${API_TOKEN:-test}"
export LOG_LEVEL="\${LOG_LEVEL:-INFO}"
export PYTHONIOENCODING="\${PYTHONIOENCODING:-utf-8}"

# Disable collector/tester if backend is running
if [ "$DISABLE_COLLECTOR" = "1" ]; then
    export DISABLE_API_COLLECTOR="1"
fi

if [ "$DISABLE_TESTER" = "1" ]; then
    export DISABLE_API_TESTER="1"
    echo -e "\033[1;36m[API] Starting on port $API_PORT (Collector/Tester disabled, using Backend scheduler)...\033[0m"
else
    echo -e "\033[1;36m[API] Starting on port $API_PORT (with Tester)...\033[0m"
fi

python3 src/api/main.py --reload
echo -e "\n\033[1;31m[API Server Stopped]\033[0m"
read -p "Press Enter to close..."
API_EOF
    chmod +x "$API_SCRIPT"
    
    start_in_terminal "ProxyPoolMaster API Server" "bash $API_SCRIPT" "$PROJECT_ROOT"
    sleep 2
fi

# Start Frontend
if [ "$MODE" = "all" ] || [ "$MODE" = "frontend" ]; then
    echo -e "${YELLOW}[3/3] Starting Frontend...${NC}"
    
    # Create a temporary script for the frontend (use relative path since start_in_terminal cds to PROJECT_ROOT)
    FRONTEND_SCRIPT=$(mktemp)
    cat > "$FRONTEND_SCRIPT" << 'FRONTEND_EOF'
#!/bin/bash
cd "web-ui"

if [ ! -d "node_modules" ]; then
    echo -e "\033[1;33m[Frontend] Installing dependencies...\033[0m"
    npm install
fi

echo -e "\033[1;36m[Frontend] Starting dev server...\033[0m"
npm run dev
echo -e "\n\033[1;31m[Frontend Stopped]\033[0m"
read -p "Press Enter to close..."
FRONTEND_EOF
    chmod +x "$FRONTEND_SCRIPT"
    
    start_in_terminal "ProxyPoolMaster Frontend" "bash $FRONTEND_SCRIPT" "$PROJECT_ROOT"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All services started successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}Access URLs:${NC}"
echo -e "${YELLOW}  Frontend:  http://localhost:$FRONTEND_PORT${NC}"
echo -e "${YELLOW}  API Docs:  http://localhost:$API_PORT/docs${NC}"
echo -e "${YELLOW}  Health:    http://localhost:$API_PORT/health${NC}"
echo -e "${YELLOW}  Logs:      ./logs/app.log (unified)${NC}"
echo ""
echo -e "${CYAN}Log Components:${NC}"
echo -e "${GRAY}  [APP]       - Main application${NC}"
echo -e "${GRAY}  [API]       - API server requests${NC}"
echo -e "${GRAY}  [COLLECTOR] - Proxy collectors${NC}"
echo -e "${GRAY}  [TESTER]    - Proxy testers${NC}"
echo -e "${GRAY}  [REDIS]     - Redis operations${NC}"
echo ""

# Wait for user input before closing
if [ "$MODE" = "all" ]; then
    echo -e "${GRAY}Press Enter to close this window...${NC}"
    read -r
fi
