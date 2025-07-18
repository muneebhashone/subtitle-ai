#!/bin/bash

# SubsAI Health Check Script
# This script checks both Streamlit app health and system resource usage

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[HEALTHCHECK]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Streamlit app is responding
log "Checking Streamlit health endpoint..."
if ! curl --fail --silent --max-time 10 http://localhost:8501/_stcore/health > /dev/null 2>&1; then
    error "Streamlit health check failed"
    exit 1
fi
log "Streamlit health check passed"

# Check memory usage
log "Checking memory usage..."
if command -v free > /dev/null; then
    MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100.0)}')
    log "Memory usage: ${MEMORY_USAGE}%"
    
    # Fail if memory usage is above 85% (more conservative for 32GB system)
    if [ "$MEMORY_USAGE" -gt 85 ]; then
        error "Memory usage too high: ${MEMORY_USAGE}%"
        exit 1
    fi
    
    # Warn if memory usage is above 70%
    if [ "$MEMORY_USAGE" -gt 70 ]; then
        warn "High memory usage: ${MEMORY_USAGE}%"
    fi
else
    warn "Memory check skipped - 'free' command not available"
fi

# Check disk space (optional, if /tmp is mounted)
log "Checking disk space..."
if command -v df > /dev/null; then
    DISK_USAGE=$(df /tmp | tail -1 | awk '{print $5}' | sed 's/%//')
    log "Disk usage (/tmp): ${DISK_USAGE}%"
    
    # Fail if disk usage is above 95%
    if [ "$DISK_USAGE" -gt 95 ]; then
        error "Disk usage too high: ${DISK_USAGE}%"
        exit 1
    fi
    
    # Warn if disk usage is above 85%
    if [ "$DISK_USAGE" -gt 85 ]; then
        warn "High disk usage: ${DISK_USAGE}%"
    fi
else
    warn "Disk check skipped - 'df' command not available"
fi

# Check for running Python processes (should have Streamlit)
log "Checking Python processes..."
if ! pgrep -f "streamlit\|subsai" > /dev/null; then
    error "No Streamlit/SubsAI processes found"
    exit 1
fi
log "Python processes check passed"

# Optional: Check CUDA availability if GPU is expected
if command -v nvidia-smi > /dev/null 2>&1; then
    log "Checking CUDA/GPU status..."
    if nvidia-smi > /dev/null 2>&1; then
        log "CUDA/GPU check passed"
    else
        warn "CUDA/GPU check failed, but continuing (may be CPU-only mode)"
    fi
fi

log "All health checks passed successfully"
exit 0