# SubsAI Webhook Setup Guide

This guide explains how to set up and use the SubsAI webhook endpoint for automatic Hebrew audio processing from S3 uploads.

## Overview

The webhook system automatically processes Hebrew audio/video files uploaded to your S3 bucket, generating subtitles in Hebrew, English, and French in both SRT and OOONA formats.

## Architecture

- **FastAPI Webhook Server** (Port 8000): Handles SNS notifications
- **Streamlit Web UI** (Port 8501): Existing user interface
- **Shared Processing Engine**: Uses existing SubsAI batch processing workflow

## Prerequisites

1. **AWS S3 Bucket**: Configured with upload notifications
2. **AWS SNS Topic**: Set up to receive S3 events
3. **AWS Credentials**: For S3 and SNS access
4. **OOONA API**: (Optional) For .ooona format output

## Installation

### 1. Install Dependencies

```bash
# Install the updated requirements
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

### 2. Environment Variables

Create a `.env` file or set environment variables:

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=eu-west-2
WEBHOOK_S3_BUCKET=aidevlondon

# OOONA API (Optional)
OOONA_API_BASE_URL=https://your-ooona-api.com
OOONA_CLIENT_ID=your_client_id
OOONA_CLIENT_SECRET=your_client_secret
```

## Deployment Options

### Option 1: Direct Python Execution

```bash
# Start the Streamlit web UI (existing)
subsai-webui

# Start the webhook server (new)
subsai-webhook

# Or run directly
python -m subsai.webhook_server
```

### Option 2: Docker with GPU Support

```bash
# Start both services with GPU support
docker-compose -f docker-compose-webhook.yml up subsai-webui subsai-webhook

# For GPU environments
docker-compose -f docker-compose-webhook.yml --profile gpu up
```

### Option 3: Docker CPU-Only

```bash
# Start CPU-only version
docker-compose -f docker-compose-webhook.yml --profile cpu-only up subsai-webui subsai-webhook-cpu
```

## AWS SNS Configuration

### Update Your SNS Topic Endpoint

Update your S3 automation script to point to the webhook endpoint:

```bash
# Update the endpoint URL in s3-automation-flow.sh
ENDPOINT_URL="http://YOUR_SERVER_IP:8000/webhook/upload"

# Or for HTTPS (recommended for production)
ENDPOINT_URL="https://your-domain.com/webhook/upload"
```

### Re-run the S3 Automation Script

```bash
# Run the updated automation script
./s3-automation-flow.sh
```

## Processing Configuration

The webhook automatically processes files with these settings:

- **Source Language**: Hebrew (`he`)
- **Target Languages**: Hebrew (transcription), English, French
- **Output Formats**: SRT, OOONA
- **Device**: Auto-detection (GPU preferred, CPU fallback)
- **S3 Storage**: Results uploaded to `/processed/{date}/` folder

## API Endpoints

### Webhook Endpoint
- **URL**: `POST /webhook/upload`
- **Purpose**: Receives SNS notifications for S3 uploads
- **Authentication**: None (public endpoint for AWS SNS)

### Health Check
- **URL**: `GET /webhook/health`
- **Purpose**: Service health monitoring

### Status Check
- **URL**: `GET /webhook/status`
- **Purpose**: Detailed service status and configuration

## Testing the Webhook

### 1. Test File Upload

Upload a Hebrew audio/video file to your S3 bucket:

```bash
# Upload a test file to trigger processing
aws s3 cp hebrew_audio.mp3 s3://aidevlondon/uploads/
```

### 2. Monitor Logs

Watch the webhook server logs:

```bash
# If running directly
python -m subsai.webhook_server

# If using Docker
docker-compose -f docker-compose-webhook.yml logs -f subsai-webhook
```

### 3. Check Processing Results

Results will be uploaded to S3 in the processed folder:

```bash
# List processed files
aws s3 ls s3://aidevlondon/webhook-20240114/ --recursive
```

## Troubleshooting

### Common Issues

1. **SNS Subscription Failed**
   - Check that your endpoint URL is publicly accessible
   - Verify AWS SNS has permission to reach your server
   - Check firewall and security group settings

2. **S3 Download Failed**
   - Verify AWS credentials have S3 read access
   - Check bucket name and region configuration
   - Ensure files are in the `/uploads` folder

3. **Processing Failed**
   - Check GPU/CUDA availability for optimal performance
   - Verify OOONA API credentials (if using .ooona format)
   - Monitor memory usage for large files

4. **Authentication Error**
   - System user is automatically created on startup
   - Check webhook server logs for user creation status

### Log Levels

Set log level for detailed debugging:

```bash
export LOG_LEVEL=DEBUG
python -m subsai.webhook_server
```

### Health Checks

Monitor service health:

```bash
# Check webhook server health
curl http://localhost:8000/webhook/health

# Check detailed status
curl http://localhost:8000/webhook/status
```

## Security Considerations

### Production Deployment

1. **HTTPS**: Use HTTPS for webhook endpoints in production
2. **Firewall**: Restrict access to webhook ports
3. **SNS Signature Verification**: Enabled by default
4. **Rate Limiting**: Consider adding rate limiting for webhook endpoint
5. **Monitoring**: Set up CloudWatch or similar monitoring

### Recommended Security Settings

```bash
# Use IAM roles instead of access keys in production
# Configure SNS topic policy to restrict source IPs
# Enable SNS message encryption
# Use VPC endpoints for S3 access
```

## Monitoring and Analytics

The webhook system integrates with SubsAI's analytics:

- **Processing Events**: Tracked automatically
- **Success/Failure Rates**: Monitored per job
- **Performance Metrics**: Processing time and file sizes
- **User Attribution**: Associated with system user account

## File Processing Workflow

1. **File Upload**: Media file uploaded to S3 `/uploads` folder
2. **SNS Notification**: S3 triggers SNS message
3. **Webhook Trigger**: SNS calls webhook endpoint
4. **File Download**: Webhook downloads file from S3
5. **Processing**: Hebrew audio processing with predefined settings
6. **Result Upload**: SRT and OOONA files uploaded to S3
7. **Cleanup**: Temporary files removed

## Support

For issues or questions:

1. Check webhook server logs for detailed error messages
2. Verify AWS configuration and permissions
3. Test individual components (S3 access, SNS delivery)
4. Review the existing SubsAI documentation for processing issues