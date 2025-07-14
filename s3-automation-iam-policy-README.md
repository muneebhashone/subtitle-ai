# IAM Policy for S3 Automation Script

This document describes the minimum IAM permissions required to execute the `s3-automation-flow.sh` script successfully.

## Policy File
The complete IAM policy is defined in: `s3-automation-iam-policy.json`

## Required Permissions

### 1. STS (Security Token Service)
- **Action**: `sts:GetCallerIdentity`
- **Purpose**: Validate AWS credentials and retrieve account ID
- **Resource**: `*` (required for STS operations)

### 2. S3 Bucket Operations
- **Actions**:
  - `s3:HeadBucket` - Verify bucket exists and is accessible
  - `s3:PutBucketNotification` - Configure S3 event notifications
  - `s3:GetBucketNotification` - Read existing notification configurations
- **Resources**: 
  - `arn:aws:s3:::aidevlondon` (or your specific bucket name)
  - `arn:aws:s3:::${aws:userid}/*` (for dynamic bucket access)

### 3. SNS (Simple Notification Service)
- **Actions**:
  - `sns:CreateTopic` - Create SNS topic for notifications
  - `sns:SetTopicAttributes` - Apply topic policy for S3 access
  - `sns:GetTopicAttributes` - Read topic configuration
  - `sns:Subscribe` - Create HTTP/HTTPS subscription
  - `sns:SetSubscriptionAttributes` - Configure delivery policy
- **Resources**:
  - `arn:aws:sns:*:*:s3-file-upload-notifications` (topic ARN)
  - `arn:aws:sns:*:*:s3-file-upload-notifications:*` (subscription ARNs)

## How to Apply the Policy

### Option 1: Attach to Existing User
```bash
aws iam put-user-policy \
  --user-name YOUR_USERNAME \
  --policy-name S3AutomationPolicy \
  --policy-document file://s3-automation-iam-policy.json
```

### Option 2: Create Managed Policy
```bash
aws iam create-policy \
  --policy-name S3AutomationPolicy \
  --policy-document file://s3-automation-iam-policy.json
  
aws iam attach-user-policy \
  --user-name YOUR_USERNAME \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/S3AutomationPolicy
```

### Option 3: Via AWS Console
1. Go to IAM → Users → Select your user
2. Click "Add permissions" → "Attach policies directly"
3. Click "Create policy" → JSON tab
4. Copy contents of `s3-automation-iam-policy.json`
5. Review and create policy
6. Attach to your user

## Customization Notes

### For Different Bucket Names
Update the S3 resource ARN in the policy:
```json
"Resource": [
  "arn:aws:s3:::YOUR_BUCKET_NAME",
  "arn:aws:s3:::YOUR_BUCKET_NAME/*"
]
```

### For Different Topic Names
Update the SNS resource ARNs:
```json
"Resource": [
  "arn:aws:sns:*:*:YOUR_TOPIC_NAME",
  "arn:aws:sns:*:*:YOUR_TOPIC_NAME:*"
]
```

### For Multiple Regions
The current policy uses `*` for regions in SNS ARNs. To restrict to specific regions:
```json
"Resource": [
  "arn:aws:sns:eu-west-2:*:s3-file-upload-notifications",
  "arn:aws:sns:us-east-1:*:s3-file-upload-notifications"
]
```

## Security Best Practices

1. **Principle of Least Privilege**: This policy includes only the minimum required permissions
2. **Resource Restrictions**: Permissions are scoped to specific resources where possible
3. **Regular Review**: Periodically review and update permissions as needed
4. **Temporary Access**: Consider using IAM roles with temporary credentials for automated scripts

## Troubleshooting

### Common Permission Errors
- **AccessDenied on s3:HeadBucket**: User lacks permission to access the S3 bucket
- **AccessDenied on sns:CreateTopic**: User cannot create SNS topics
- **AccessDenied on s3:PutBucketNotification**: User cannot modify bucket notifications

### Testing Permissions
Test individual permissions before running the full script:
```bash
# Test STS access
aws sts get-caller-identity

# Test S3 bucket access
aws s3api head-bucket --bucket aidevlondon

# Test SNS access
aws sns list-topics
```