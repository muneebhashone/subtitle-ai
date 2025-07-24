#!/bin/bash

# SubsAI System Monitor Script
# This script monitors the SubsAI containers and restarts them if necessary
# Can be run as a cron job or systemd service

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/../docker-compose.yml"
SERVICE_NAME="subsai-webui"
LOG_FILE="/var/log/subsai-monitor.log"
MAX_LOG_SIZE=10485760  # 10MB in bytes
NOTIFICATION_EMAIL=""  # Set to email address to receive notifications
SLACK_WEBHOOK=""       # Set to Slack webhook URL for notifications

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "${GREEN}[MONITOR]${NC} $message"
    
    # Log to file if log file is writable
    if [ -w "$(dirname "$LOG_FILE")" ] 2>/dev/null; then
        echo "$message" >> "$LOG_FILE"
        
        # Rotate log if it gets too large
        if [ -f "$LOG_FILE" ] && [ "$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null)" -gt "$MAX_LOG_SIZE" ]; then
            mv "$LOG_FILE" "${LOG_FILE}.old"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Log rotated" > "$LOG_FILE"
        fi
    fi
}

warn() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1"
    echo -e "${YELLOW}[MONITOR]${NC} $message"
    [ -w "$(dirname "$LOG_FILE")" ] 2>/dev/null && echo "$message" >> "$LOG_FILE"
}

error() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1"
    echo -e "${RED}[MONITOR]${NC} $message"
    [ -w "$(dirname "$LOG_FILE")" ] 2>/dev/null && echo "$message" >> "$LOG_FILE"
}

# Function to send notifications
send_notification() {
    local subject="$1"
    local message="$2"
    
    # Email notification
    if [ -n "$NOTIFICATION_EMAIL" ] && command -v mail > /dev/null; then
        echo "$message" | mail -s "$subject" "$NOTIFICATION_EMAIL"
    fi
    
    # Slack notification
    if [ -n "$SLACK_WEBHOOK" ] && command -v curl > /dev/null; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"$subject: $message\"}" \
            "$SLACK_WEBHOOK" 2>/dev/null || true
    fi
}

# Function to check container health
check_container_health() {
    local container_name="$1"
    
    # Check if container exists and is running
    if ! docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
        return 1
    fi
    
    # Check container health status
    local health_status
    health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "unknown")
    
    if [ "$health_status" = "healthy" ]; then
        return 0
    elif [ "$health_status" = "unhealthy" ]; then
        return 2
    else
        # No health check defined or starting, check if container is running
        local running_status
        running_status=$(docker inspect --format='{{.State.Running}}' "$container_name" 2>/dev/null || echo "false")
        
        if [ "$running_status" = "true" ]; then
            return 0
        else
            return 1
        fi
    fi
}

# Function to get container resource usage
get_container_stats() {
    local container_name="$1"
    
    if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
        docker stats --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" "$container_name" 2>/dev/null || echo "N/A"
    else
        echo "Container not running"
    fi
}

# Function to restart service
restart_service() {
    local service="$1"
    log "Attempting to restart service: $service"
    
    # Try graceful restart first
    if docker compose -f "$COMPOSE_FILE" restart "$service"; then
        log "Successfully restarted $service"
        send_notification "SubsAI Service Restarted" "Service $service was restarted successfully"
        return 0
    else
        error "Failed to restart $service with docker compose restart"
        
        # Try harder restart
        log "Attempting force restart of $service"
        if docker compose -f "$COMPOSE_FILE" stop "$service" && \
           docker compose -f "$COMPOSE_FILE" rm -f "$service" && \
           docker compose -f "$COMPOSE_FILE" up -d "$service"; then
            log "Successfully force-restarted $service"
            send_notification "SubsAI Service Force-Restarted" "Service $service was force-restarted after restart failure"
            return 0
        else
            error "Failed to force-restart $service"
            send_notification "SubsAI Service Restart Failed" "Failed to restart service $service. Manual intervention required."
            return 1
        fi
    fi
}

# Function to cleanup resources
cleanup_resources() {
    log "Performing resource cleanup..."
    
    # Clean up stopped containers
    docker container prune -f 2>/dev/null || true
    
    # Clean up dangling images
    docker image prune -f 2>/dev/null || true
    
    # Clean up unused volumes (be careful with this)
    # docker volume prune -f 2>/dev/null || true
    
    # Clean up temporary files older than 24 hours
    find /tmp -name "tmp*" -type f -mtime +1 -delete 2>/dev/null || true
    
    log "Resource cleanup completed"
}

# Main monitoring function
main() {
    log "Starting SubsAI system monitoring check"
    
    # Change to the directory containing docker-compose.yml
    cd "$(dirname "$COMPOSE_FILE")"
    
    # Get the actual container name
    local container_name
    container_name=$(docker compose ps -q "$SERVICE_NAME" 2>/dev/null | head -1)
    
    if [ -z "$container_name" ]; then
        container_name=$(docker compose -f "$COMPOSE_FILE" ps | grep "$SERVICE_NAME" | awk '{print $1}' | head -1)
    fi
    
    if [ -z "$container_name" ]; then
        error "Could not find container for service $SERVICE_NAME"
        
        # Try to start the service
        log "Attempting to start service $SERVICE_NAME"
        if docker compose -f "$COMPOSE_FILE" up -d "$SERVICE_NAME"; then
            log "Successfully started $SERVICE_NAME"
            send_notification "SubsAI Service Started" "Service $SERVICE_NAME was started from stopped state"
        else
            error "Failed to start $SERVICE_NAME"
            send_notification "SubsAI Service Start Failed" "Failed to start service $SERVICE_NAME. Manual intervention required."
        fi
        return
    fi
    
    # Check container health
    local health_check_result
    check_container_health "$container_name"
    health_check_result=$?
    
    case $health_check_result in
        0)
            log "Container $container_name is healthy"
            
            # Show resource usage
            local stats
            stats=$(get_container_stats "$container_name")
            log "Resource usage: $stats"
            ;;
        1)
            warn "Container $container_name is not running"
            restart_service "$SERVICE_NAME"
            ;;
        2)
            warn "Container $container_name is unhealthy"
            restart_service "$SERVICE_NAME"
            ;;
    esac
    
    # Periodic cleanup (run every 6 hours based on file timestamp)
    local cleanup_marker="/tmp/.subsai_last_cleanup"
    if [ ! -f "$cleanup_marker" ] || [ "$(find "$cleanup_marker" -mmin +360 2>/dev/null)" ]; then
        cleanup_resources
        touch "$cleanup_marker" 2>/dev/null || true
    fi
    
    log "Monitoring check completed"
}

# Handle script arguments
case "${1:-check}" in
    "check")
        main
        ;;
    "restart")
        restart_service "$SERVICE_NAME"
        ;;
    "cleanup")
        cleanup_resources
        ;;
    "install-cron")
        # Install as cron job (run every 5 minutes)
        cron_entry="*/5 * * * * $(realpath "$0") check"
        (crontab -l 2>/dev/null; echo "$cron_entry") | crontab -
        log "Installed cron job: $cron_entry"
        ;;
    "uninstall-cron")
        # Remove from cron
        crontab -l 2>/dev/null | grep -v "$(realpath "$0")" | crontab -
        log "Removed cron job"
        ;;
    *)
        echo "Usage: $0 {check|restart|cleanup|install-cron|uninstall-cron}"
        echo "  check         - Check container health and restart if needed (default)"
        echo "  restart       - Force restart the service"
        echo "  cleanup       - Clean up Docker resources and temp files"
        echo "  install-cron  - Install as cron job (every 5 minutes)"
        echo "  uninstall-cron - Remove from cron job"
        exit 1
        ;;
esac