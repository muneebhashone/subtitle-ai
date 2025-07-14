#!/bin/bash

# Complete deployment script for S3 → SNS → HTTP workflow
# Enhanced version with comprehensive error handling

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration - can be overridden by environment variables
BUCKET_NAME="${BUCKET_NAME:-aidevlondon}"
TOPIC_NAME="${TOPIC_NAME:-s3-file-upload-notifications}"
ENDPOINT_URL="${ENDPOINT_URL:-http://35.179.146.175/webhook/s3-upload}"
REGION="${REGION:-eu-west-2}"

# Global variables for cleanup
TOPIC_ARN=""
SUBSCRIPTION_ARN=""
TEMP_FILES=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    for file in "${TEMP_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            rm -f "$file"
            log_info "Removed $file"
        fi
    done
}

# Error handler
error_handler() {
    local exit_code=$?
    log_error "Script failed with exit code $exit_code on line $1"
    cleanup
    exit $exit_code
}

# Set up error handling
trap 'error_handler $LINENO' ERR
trap cleanup EXIT

# Validation functions
validate_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi
    log_success "AWS CLI found"
}

validate_aws_credentials() {
    log_info "Validating AWS credentials..."
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        log_error "Please run 'aws configure' or set AWS environment variables"
        exit 1
    fi
    log_success "AWS credentials validated"
}

validate_inputs() {
    log_info "Validating input parameters..."
    
    if [[ -z "$BUCKET_NAME" ]]; then
        log_error "BUCKET_NAME is required"
        exit 1
    fi
    
    if [[ -z "$TOPIC_NAME" ]]; then
        log_error "TOPIC_NAME is required"
        exit 1
    fi
    
    if [[ -z "$ENDPOINT_URL" ]]; then
        log_error "ENDPOINT_URL is required"
        exit 1
    fi
    
    if [[ -z "$REGION" ]]; then
        log_error "REGION is required"
        exit 1
    fi
    
    # Validate URL format
    if [[ ! "$ENDPOINT_URL" =~ ^https?://[^/]+.*$ ]]; then
        log_error "ENDPOINT_URL must be a valid HTTP/HTTPS URL"
        exit 1
    fi
    
    log_success "Input parameters validated"
}

verify_bucket_exists() {
    log_info "Verifying S3 bucket exists..."
    if ! aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$REGION" 2>/dev/null; then
        log_error "S3 bucket '$BUCKET_NAME' does not exist or is not accessible"
        exit 1
    fi
    log_success "S3 bucket verified"
}

# Determine protocol for SNS subscription
get_protocol() {
    if [[ "$ENDPOINT_URL" == https://* ]]; then
        echo "https"
    else
        echo "http"
    fi
}

echo "🚀 Starting S3 → SNS → HTTP deployment..."
echo "📋 Configuration:"
echo "   • Bucket: $BUCKET_NAME"
echo "   • Topic: $TOPIC_NAME"  
echo "   • Endpoint: $ENDPOINT_URL"
echo "   • Region: $REGION"
echo ""

# Run validations
validate_aws_cli
validate_aws_credentials
validate_inputs
verify_bucket_exists

# Step 1: Create SNS Topic
log_info "Creating SNS topic..."
if TOPIC_ARN=$(aws sns create-topic --name "$TOPIC_NAME" --region "$REGION" --query 'TopicArn' --output text 2>/dev/null); then
    log_success "SNS Topic created: $TOPIC_ARN"
else
    log_error "Failed to create SNS topic"
    exit 1
fi

# Step 2: Create HTTP subscription
PROTOCOL=$(get_protocol)
log_info "Creating $PROTOCOL subscription..."
if SUBSCRIPTION_ARN=$(aws sns subscribe \
    --topic-arn "$TOPIC_ARN" \
    --protocol "$PROTOCOL" \
    --notification-endpoint "$ENDPOINT_URL" \
    --region "$REGION" \
    --query 'SubscriptionArn' --output text 2>/dev/null); then
    log_success "Subscription created: $SUBSCRIPTION_ARN"
else
    log_error "Failed to create SNS subscription"
    exit 1
fi

# Step 3: Set delivery policy
log_info "Configuring delivery policy..."
DELIVERY_POLICY='{"healthyRetryPolicy":{"numRetries":3,"minDelayTarget":1,"maxDelayTarget":60,"backoffFunction":"exponential"}}'
if aws sns set-subscription-attributes \
    --subscription-arn "$SUBSCRIPTION_ARN" \
    --attribute-name DeliveryPolicy \
    --attribute-value "$DELIVERY_POLICY" \
    --region "$REGION" &>/dev/null; then
    log_success "Delivery policy configured"
else
    log_error "Failed to set delivery policy"
    exit 1
fi

# Step 4: Get AWS Account ID
log_info "Getting AWS Account ID..."
if ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null); then
    log_success "Account ID retrieved: $ACCOUNT_ID"
else
    log_error "Failed to get AWS Account ID"
    exit 1
fi

# Step 5: Create and apply SNS topic policy
log_info "Setting up SNS topic policy..."
SNS_POLICY_FILE="/tmp/sns-policy-$$.json"
TEMP_FILES+=("$SNS_POLICY_FILE")

cat > "$SNS_POLICY_FILE" << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowS3ToPublishToSNS",
            "Effect": "Allow",
            "Principal": {
                "Service": "s3.amazonaws.com"
            },
            "Action": "SNS:Publish",
            "Resource": "$TOPIC_ARN",
            "Condition": {
                "StringEquals": {
                    "aws:SourceAccount": "$ACCOUNT_ID"
                },
                "StringLike": {
                    "aws:SourceArn": "arn:aws:s3:::$BUCKET_NAME"
                }
            }
        }
    ]
}
EOF

if aws sns set-topic-attributes \
    --topic-arn "$TOPIC_ARN" \
    --attribute-name Policy \
    --attribute-value "file://$SNS_POLICY_FILE" \
    --region "$REGION" &>/dev/null; then
    log_success "SNS topic policy applied"
else
    log_error "Failed to set SNS topic policy"
    exit 1
fi

# Step 6: Configure S3 event notifications
log_info "Configuring S3 event notifications..."
S3_NOTIFICATION_FILE="/tmp/s3-notification-$$.json"
TEMP_FILES+=("$S3_NOTIFICATION_FILE")

cat > "$S3_NOTIFICATION_FILE" << EOF
{
    "TopicConfigurations": [
        {
            "Id": "S3FileUploadNotification",
            "TopicArn": "$TOPIC_ARN",
            "Events": [
                "s3:ObjectCreated:*"
            ],
            "Filter": {
                "Key": {
                    "FilterRules": [
                        {
                            "Name": "prefix",
                            "Value": "uploads/"
                        }
                    ]
                }
            }
        }
    ]
}
EOF

if aws s3api put-bucket-notification-configuration \
    --bucket "$BUCKET_NAME" \
    --notification-configuration "file://$S3_NOTIFICATION_FILE" \
    --region "$REGION" &>/dev/null; then
    log_success "S3 event notifications configured"
else
    log_error "Failed to configure S3 event notifications"
    exit 1
fi

echo ""
log_success "Deployment completed successfully!"
echo ""
echo "📋 Summary:"
echo "   • SNS Topic: $TOPIC_ARN"
echo "   • Subscription: $SUBSCRIPTION_ARN"
echo "   • Protocol: $PROTOCOL"
echo "   • Endpoint: $ENDPOINT_URL"
echo "   • S3 Bucket: $BUCKET_NAME"
echo "   • Region: $REGION"
echo ""
log_info "Test your setup:"
echo "   aws s3 cp test-file.txt s3://$BUCKET_NAME/uploads/"
echo ""
log_warning "Important notes:"
echo "   • Make sure your API is running at $ENDPOINT_URL"
echo "   • Your API must handle SNS subscription confirmation"
echo "   • Check your API logs for incoming requests"
if [[ "$PROTOCOL" == "http" ]]; then
    log_warning "Using HTTP protocol - consider HTTPS for production"
fi
echo ""
log_info "Monitor with:"
echo "   • SNS Topic metrics in CloudWatch"
echo "   • S3 bucket event notifications"
echo "   • Your API application logs"
echo ""
log_info "Configuration can be overridden with environment variables:"
echo "   export BUCKET_NAME='your-bucket'"
echo "   export TOPIC_NAME='your-topic'"
echo "   export ENDPOINT_URL='https://your-domain.com/webhook'"
echo "   export REGION='your-region'"