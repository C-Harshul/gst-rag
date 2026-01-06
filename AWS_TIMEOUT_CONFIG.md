# AWS Timeout Configuration Guide

## Problem
Getting `504 Gateway Timeout` errors when processing queries that take longer to complete.

## Solution
Configure timeouts at multiple levels depending on your AWS infrastructure setup.

## Timeout Configuration by AWS Service

### 1. AWS API Gateway
**Default Timeout:** 30 seconds (hard limit)
**Maximum:** 30 seconds (cannot be increased)

**Solutions:**
- **Option A:** Use Lambda integration instead of HTTP integration
  - Lambda can handle up to 15 minutes
  - Configure Lambda timeout separately (see below)

- **Option B:** Use Application Load Balancer (ALB) instead of API Gateway
  - ALB supports up to 4000 seconds (66+ minutes)

**Configuration:**
```bash
# If using API Gateway with Lambda integration
# Configure in Lambda settings (see Lambda section below)
```

### 2. AWS Lambda
**Default Timeout:** 3 seconds
**Maximum:** 15 minutes (900 seconds)

**Configuration:**
1. Go to AWS Lambda Console
2. Select your function
3. Go to **Configuration** → **General configuration**
4. Click **Edit**
5. Set **Timeout** to maximum: **15 minutes** (900 seconds)
6. Click **Save**

**Or via AWS CLI:**
```bash
aws lambda update-function-configuration \
  --function-name your-function-name \
  --timeout 900
```

**Or via Terraform:**
```hcl
resource "aws_lambda_function" "rag_api" {
  timeout = 900  # 15 minutes
}
```

### 3. Application Load Balancer (ALB)
**Default Timeout:** 60 seconds
**Maximum:** 4000 seconds (66+ minutes)

**Configuration:**
1. Go to EC2 Console → Load Balancers
2. Select your ALB
3. Go to **Listeners** tab
4. Select your listener → **Edit**
5. Under **Default actions**, click **Edit**
6. Set **Idle timeout** to desired value (e.g., 300 seconds = 5 minutes)
7. Click **Save**

**Or via AWS CLI:**
```bash
aws elbv2 modify-load-balancer-attributes \
  --load-balancer-arn <your-alb-arn> \
  --attributes Key=idle_timeout.timeout_seconds,Value=300
```

### 4. EC2/ECS with Uvicorn
**Configuration:**
The code has been updated to support configurable timeouts via environment variable:

```bash
# Set timeout in seconds (default: 300 = 5 minutes)
export REQUEST_TIMEOUT=600  # 10 minutes

# Run uvicorn with increased timeouts
uvicorn rag.api:app \
  --host 0.0.0.0 \
  --port 8002 \
  --timeout-keep-alive 600 \
  --timeout-graceful-shutdown 30
```

### 5. ECS Task Definition
If running in ECS, ensure task timeout is sufficient:

```json
{
  "containerDefinitions": [{
    "name": "rag-api",
    "stopTimeout": 300
  }]
}
```

## Recommended Configuration

### For Lambda-based deployment:
1. **Lambda Timeout:** 900 seconds (15 minutes)
2. **API Gateway:** Use Lambda integration (not HTTP proxy)
3. **Environment Variable:** `REQUEST_TIMEOUT=900`

### For EC2/ECS deployment:
1. **ALB Idle Timeout:** 300-600 seconds (5-10 minutes)
2. **Uvicorn:** Use `--timeout-keep-alive 600`
3. **Environment Variable:** `REQUEST_TIMEOUT=600`

### For API Gateway with HTTP integration:
- **Not recommended** for long-running queries
- Maximum 30 seconds is too short for comprehensive RAG queries
- **Switch to Lambda integration** or use ALB instead

## Environment Variables

Add to your deployment configuration:

```bash
# Request timeout in seconds (default: 300 = 5 minutes)
REQUEST_TIMEOUT=600

# For uvicorn directly
export REQUEST_TIMEOUT=600
uvicorn rag.api:app --host 0.0.0.0 --port 8002
```

## Testing Timeout Configuration

Test with a simple query first:
```bash
curl -X POST http://your-api-url/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is GST?"}'
```

If it still times out, check:
1. Lambda timeout settings
2. ALB idle timeout
3. API Gateway integration type
4. Network connectivity to ChromaDB

## Monitoring

Monitor timeout errors in:
- CloudWatch Logs (Lambda/ECS)
- API Gateway CloudWatch metrics
- ALB access logs

Look for patterns:
- Are timeouts happening at a consistent time?
- Are certain queries always timing out?
- Is ChromaDB response time the bottleneck?

## Troubleshooting

1. **Check CloudWatch Logs:**
   ```bash
   aws logs tail /aws/lambda/your-function-name --follow
   ```

2. **Verify ChromaDB connectivity:**
   - Ensure ChromaDB server is accessible
   - Check network security groups
   - Test connection from Lambda/EC2

3. **Optimize Query Processing:**
   - Reduce number of documents retrieved (k parameter)
   - Use smaller chunk sizes
   - Cache frequently accessed data

4. **Consider Async Processing:**
   - For very long queries, consider async job processing
   - Use SQS + Lambda for background processing
   - Return job ID immediately, poll for results


