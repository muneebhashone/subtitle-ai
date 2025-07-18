# SubsAI Auto-Recovery Setup Guide

This guide explains how to set up automatic recovery for your SubsAI deployment to handle system failures and high load situations.

## Overview

The auto-recovery system includes:
- **Docker restart policies** - Automatic container restart on failure
- **Health checks** - Monitor application and system health
- **Resource limits** - Prevent resource exhaustion
- **System monitoring** - External monitoring with automatic remediation
- **Cleanup mechanisms** - Automatic resource cleanup

## Quick Setup

### 1. Environment Configuration

Copy the environment template and configure your settings:

```bash
cp .env.example .env
# Edit .env with your actual configuration values
```

### 2. Deploy with Auto-Recovery

For GPU-enabled servers:
```bash
docker-compose up -d subsai-webui
```

For CPU-only servers:
```bash
docker-compose --profile cpu-only up -d subsai-webui-cpu
```

### 3. Install System Monitor (Optional but Recommended)

```bash
# Install as a cron job (runs every 5 minutes)
./scripts/system_monitor.sh install-cron

# Or run manually when needed
./scripts/system_monitor.sh check
```

## Detailed Configuration

### Docker Restart Policies

The `docker-compose.yml` now includes:

```yaml
restart: unless-stopped
```

This policy ensures containers:
- Restart automatically on failure
- Restart after host reboot
- Don't restart if manually stopped

### Health Checks

Health checks monitor:
- **Streamlit application health** - Tests `/_stcore/health` endpoint
- **Memory usage** - Warns at 80%, fails at 90%
- **Disk space** - Warns at 85%, fails at 95%
- **Process health** - Ensures Streamlit processes are running
- **GPU status** - Checks CUDA availability (if applicable)

Health check configuration:
- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Start period**: 60 seconds (grace period)
- **Retries**: 3 attempts before marking unhealthy

### Resource Limits

#### GPU Service (`subsai-webui`)
- **Memory**: 8GB limit, 2GB reserved
- **CPU**: 4.0 cores maximum
- **GPU**: NVIDIA GPU access

#### CPU Service (`subsai-webui-cpu`)
- **Memory**: 6GB limit, 1GB reserved
- **CPU**: 2.0 cores maximum
- **No GPU**: CPU-only processing

### System Monitor Features

The `system_monitor.sh` script provides:

#### Monitoring Capabilities
- Container health status checking
- Resource usage monitoring
- Automatic restart on failures
- Resource cleanup (containers, images, temp files)
- Notification support (email, Slack)

#### Usage Commands
```bash
# Check system health
./scripts/system_monitor.sh check

# Force restart service
./scripts/system_monitor.sh restart

# Clean up resources
./scripts/system_monitor.sh cleanup

# Install monitoring cron job
./scripts/system_monitor.sh install-cron

# Remove monitoring cron job
./scripts/system_monitor.sh uninstall-cron
```

## Monitoring and Notifications

### Email Notifications

To enable email notifications, set in your environment:
```bash
NOTIFICATION_EMAIL=your-email@example.com
```

Requires `mail` command to be available on the host system.

### Slack Notifications

To enable Slack notifications, set in your environment:
```bash
SLACK_WEBHOOK=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
```

### Log Files

Monitor logs in:
- **System monitor logs**: `/var/log/subsai-monitor.log`
- **Container logs**: `docker-compose logs subsai-webui`
- **Health check logs**: `docker inspect <container_name>`

## Troubleshooting

### Common Issues

#### 1. High Memory Usage
**Symptoms**: Container restarts frequently, health checks fail
**Solutions**:
- Increase memory limits in `docker-compose.yml`
- Enable CUDA memory cleanup in WebUI
- Reduce model size or batch processing

#### 2. GPU Memory Issues
**Symptoms**: CUDA out of memory errors
**Solutions**:
- Use CPU-only mode: `docker-compose --profile cpu-only up -d`
- Implement CUDA memory cleanup in application
- Reduce concurrent processing

#### 3. Health Check Failures
**Symptoms**: Container marked as unhealthy
**Solutions**:
- Check application logs: `docker-compose logs subsai-webui`
- Verify Streamlit is responding: `curl localhost:8501/_stcore/health`
- Increase health check timeout or retries

#### 4. Persistent Failures
**Symptoms**: Container keeps restarting
**Solutions**:
- Check resource usage: `docker stats`
- Review system logs: `journalctl -u docker`
- Check disk space: `df -h`

### Manual Recovery

If automatic recovery fails:

```bash
# Stop all services
docker-compose down

# Clean up resources
docker system prune -f

# Restart services
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs subsai-webui
```

### Debugging Health Checks

```bash
# Check health status
docker inspect <container_name> | grep -A 10 "Health"

# Run health check manually
docker exec <container_name> /usr/local/bin/healthcheck.sh

# View health check logs
docker logs <container_name> | grep HEALTHCHECK
```

## Performance Optimization

### Memory Management

1. **Monitor memory usage**:
   ```bash
   docker stats subsai-webui
   ```

2. **Adjust memory limits** in `docker-compose.yml`:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 8g  # Adjust based on your server
   ```

3. **Enable memory cleanup** in application code

### CPU Optimization

1. **Monitor CPU usage**:
   ```bash
   docker stats subsai-webui
   ```

2. **Adjust CPU limits**:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '4.0'  # Adjust based on your server
   ```

### Disk Space Management

1. **Regular cleanup**:
   ```bash
   # Clean Docker resources
   docker system prune -f
   
   # Clean temporary files
   find /tmp -type f -mtime +1 -delete
   ```

2. **Monitor disk usage**:
   ```bash
   df -h
   du -sh /var/lib/docker
   ```

## Security Considerations

1. **Environment variables**: Keep `.env` file secure and never commit to git
2. **Resource limits**: Prevent resource exhaustion attacks
3. **Health checks**: Don't expose sensitive information in health check responses
4. **Monitoring**: Secure notification channels (email, Slack)

## Maintenance

### Regular Tasks

1. **Update containers**:
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

2. **Clean up resources**:
   ```bash
   ./scripts/system_monitor.sh cleanup
   ```

3. **Check logs**:
   ```bash
   docker-compose logs --tail=100 subsai-webui
   ```

4. **Monitor performance**:
   ```bash
   docker stats subsai-webui
   ```

### Scheduled Maintenance

Consider setting up:
- **Weekly resource cleanup**
- **Monthly container updates**
- **Quarterly configuration review**

## Support

For issues with auto-recovery setup:

1. Check the troubleshooting section above
2. Review logs for error messages
3. Test components individually
4. Consult the main SubsAI documentation

## Advanced Configuration

### Custom Health Checks

Modify `scripts/healthcheck.sh` to add custom checks:

```bash
# Add your custom checks here
log "Running custom application check..."
# Your custom logic
```

### Custom Monitoring

Extend `scripts/system_monitor.sh` for additional monitoring:

```bash
# Add custom monitoring logic
check_custom_metrics() {
    # Your custom monitoring logic
}
```

### Integration with External Monitoring

The auto-recovery system can be integrated with:
- **Prometheus + Grafana** for metrics
- **ELK Stack** for log analysis
- **Nagios/Zabbix** for infrastructure monitoring
- **Cloud monitoring** (AWS CloudWatch, Azure Monitor, etc.)

---

**Note**: This auto-recovery system significantly improves reliability but doesn't replace proper infrastructure monitoring and maintenance. Regular updates and monitoring are still recommended.