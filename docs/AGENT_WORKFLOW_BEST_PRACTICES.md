# AWS CloudOps Agent - Workflow Best Practices

## 📋 Table of Contents
- [Architecture Overview](#architecture-overview)
- [Phase 1: Issue Detection & Analysis](#phase-1-issue-detection--analysis)
- [Phase 2: User Review & Approval](#phase-2-user-review--approval)
- [Phase 3: Agent Execution](#phase-3-agent-execution)
- [Implementation Recommendations](#implementation-recommendations)
- [Security Best Practices](#security-best-practices)
- [Monitoring & Observability](#monitoring--observability)

---

## 🏗️ Architecture Overview

### Complete Workflow Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  Phase 1: Detection & Analysis                          │
├─────────────────────────────────────────────────────────┤
│  1. Monitor Lambda detects issue                        │
│  2. Invoke Agent for analysis                           │
│  3. Store full analysis in S3                           │
│  4. Store alert metadata in DynamoDB                    │
│     - alert_id, domain, timestamp                       │
│     - s3_analysis_url                                   │
│     - approval_status: "pending"                        │
│     - agent_session_id (for context retention)          │
│  5. Send notifications (Teams/Slack/Email)              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 2: User Review (Interactive)                     │
├─────────────────────────────────────────────────────────┤
│  Option A: Teams Adaptive Card Buttons                  │
│    - "View Full Analysis" → Opens S3 report             │
│    - "Execute Suggestions" → Triggers approval workflow │
│                                                         │
│  Option B: API Gateway + Web UI (Recommended)           │
│    - Teams button → API Gateway URL with alert_id       │
│    - Simple React/HTML page showing:                    │
│      • Full analysis (from S3)                          │
│      • Proposed actions                                 │
│      • Approve/Reject buttons                           │
│      • Comment field for justification                  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 3: Approval Processing                           │
├─────────────────────────────────────────────────────────┤
│  1. User clicks "Approve" in Teams or Web UI            │
│  2. API Gateway → Lambda (Approval Handler)             │
│  3. Update DynamoDB:                                    │
│     - approval_status: "approved"                       │
│     - approved_by: user_email                           │
│     - approved_at: timestamp                            │
│  4. Trigger execution Lambda via EventBridge/SNS        │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 4: Agent Execution with Context                  │
├─────────────────────────────────────────────────────────┤
│  1. Execution Lambda retrieves from DynamoDB:           │
│     - Original analysis from S3                         │
│     - Agent session_id (for context continuity)         │
│  2. Invoke Agent with execution prompt:                 │
│     "Your previous analysis (session: {session_id})     │
│      has been approved. Execute the recommended         │
│      actions: [include original analysis]"              │
│  3. Agent executes with AWS SDK calls:                  │
│     - Route53 changes                                   │
│     - CloudFront updates                                │
│     - Security group modifications                      │
│     - etc.                                              │
│  4. Log all actions to S3 + DynamoDB                    │
│  5. Send completion notification to Teams               │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Phase 1: Issue Detection & Analysis

### Current Implementation (Good Foundation)
✅ Lambda ping monitor with EventBridge scheduled trigger  
✅ Agent invocation with comprehensive prompt  
✅ S3 storage for full analysis  
✅ Multi-channel notifications (Teams/Slack/Email)

### Recommended Enhancements

#### 1. Multiple Trigger Sources
```python
# Support various issue detection methods
TRIGGER_SOURCES = {
    'scheduled_monitor': 'EventBridge Rule (5-minute intervals)',
    'cloudwatch_alarm': 'Metric-based alerts (CPU, Memory, Errors)',
    'manual_trigger': 'On-demand investigation',
    'sns_topic': 'Integration with other AWS services'
}
```

#### 2. Context-Rich Analysis Storage

**DynamoDB Schema:**
```python
{
    'alert_id': 'string',           # Partition key (UUID)
    'timestamp': 'string',          # Sort key (ISO 8601)
    'domain': 'string',             # Monitored resource
    'issue_type': 'string',         # 'dns_failure', 'http_error', 'performance'
    'error_details': 'string',      # Original error message
    
    # Agent Context
    'agent_session_id': 'string',   # For context continuity
    'agent_analysis': 'string',     # Summarized analysis
    's3_analysis_url': 'string',    # Full analysis location
    's3_analysis_key': 'string',    # S3 object key
    
    # Workflow State
    'approval_status': 'string',    # 'pending', 'approved', 'rejected', 'executed'
    'approved_by': 'string',        # User email/ID
    'approved_at': 'string',        # Approval timestamp
    'rejection_reason': 'string',   # Optional
    
    # Execution Tracking
    'execution_status': 'string',   # 'not_started', 'in_progress', 'completed', 'failed'
    'execution_log_url': 'string',  # Execution results
    'executed_at': 'string',        # Execution timestamp
    'execution_duration': 'number', # Seconds
    
    # Metadata
    'severity': 'string',           # 'critical', 'high', 'medium', 'low'
    'affected_services': ['list'],  # AWS services involved
    'estimated_impact': 'string',   # Business impact description
    
    # Auto-cleanup
    'ttl': 'number'                 # Unix timestamp (7 days)
}
```

#### 3. Enhanced Agent Prompt Structure

```python
def construct_analysis_prompt(domain, timestamp, error_details, context=None):
    """
    Create comprehensive analysis prompt with structured output requirements
    """
    prompt = f"""URGENT: Domain monitoring alert requires immediate analysis.

**Incident Details:**
- Domain: {domain}
- Status: UNREACHABLE
- Timestamp: {timestamp}
- Error: {error_details}

**Infrastructure Context:**
This website uses the following AWS services:
1. Amazon Route 53 for DNS management
2. Amazon CloudFront as the Content Delivery Network (CDN)
3. AWS Certificate Manager (ACM) for SSL/TLS certificates
4. Amazon S3 for static website hosting
5. AWS WAF for web application security

**Analysis Requirements:**

1. **Executive Summary** (First 200 words)
   - Root cause in one sentence
   - Immediate impact assessment
   - Estimated time to resolve

2. **Detailed Investigation**
   - Check AWS service health status
   - Verify Route 53 DNS records and hosted zones
   - Validate CloudFront distribution configuration
   - Review ACM certificate status
   - Check S3 bucket configuration and permissions
   - Analyze CloudTrail for recent changes
   - Review CloudWatch logs and metrics

3. **Root Cause Analysis**
   - Primary issue identification
   - Contributing factors
   - Timeline of events

4. **Critical Findings** (Table format)
   - Component status (OK/WARNING/CRITICAL)
   - Specific issues found

5. **Immediate Actions Required** (Numbered list)
   - Specific AWS CLI/SDK commands to execute
   - Order of execution (dependencies)
   - Expected outcome for each action
   - Rollback steps if needed

6. **Prevention Recommendations**
   - Long-term fixes
   - Monitoring improvements
   - Architecture changes

**Output Format:** Use markdown with clear sections and tables.
**CRITICAL:** Ensure "IMMEDIATE ACTIONS REQUIRED" section contains executable steps.
"""
    return prompt
```

---

## 🔍 Phase 2: User Review & Approval

### Notification Strategy

#### Multi-Channel Approach (Recommended)

**1. Microsoft Teams (Primary - Interactive)** ✅ Currently Implemented
- Adaptive Card with summarized analysis
- Action buttons for approval workflow
- Real-time interaction

**2. Email (Secondary - Archival)**
- Summary + S3 link
- Audit trail for compliance
- Accessible to non-Teams users

**3. Slack (Optional - Team Collaboration)**
- Block Kit format
- Similar interactive capabilities

### Approval Workflow Options

#### Option A: Direct Teams Button Approval (Simple)

**Pros:**
- Minimal infrastructure
- Fast approval (one click)
- No additional UI needed

**Cons:**
- Limited approval context
- No detailed review capability
- Harder to implement approval logic with webhook callbacks

**Implementation:**
```python
# In send_teams_notification function
approval_webhook_url = f"{API_GATEWAY_URL}/approve"

actions.append({
    "type": "Action.Submit",
    "title": "✅ Approve & Execute",
    "data": {
        "action": "approve",
        "alert_id": alert_id,
        "approved_by": "${user_email}"  # Teams provides this
    }
})
```

#### Option B: Web-Based Approval Portal (Recommended)

**Pros:**
- Detailed analysis review
- Multiple approver support
- Audit logging built-in
- Can show diff/preview of changes
- Support for comments/justification

**Cons:**
- Requires API Gateway + hosting
- More complex implementation

**Architecture:**
```
Teams Button → API Gateway + Lambda (Auth)
            → Generate pre-signed S3 URL
            → Render approval page with:
              - Full analysis from S3
              - Proposed changes highlighted
              - Approve/Reject buttons
              - Comment field
            → Submit → Lambda (Update DynamoDB)
            → Trigger Execution Lambda
```

**Simple HTML Approval Page:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>CloudOps Alert Approval</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: #ff6b6b; color: white; padding: 20px; border-radius: 8px; }
        .analysis { background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; }
        .actions { background: #e3f2fd; padding: 15px; border-radius: 8px; }
        .btn { padding: 12px 24px; margin: 5px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        .btn-approve { background: #4caf50; color: white; }
        .btn-reject { background: #f44336; color: white; }
        pre { background: #2d2d2d; color: #f8f8f2; padding: 15px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚠️ CloudOps Alert: ${domain}</h1>
        <p>Alert ID: ${alert_id} | Timestamp: ${timestamp}</p>
    </div>
    
    <div class="analysis">
        <h2>AI Agent Analysis</h2>
        <div id="analysis-content">${analysis_content}</div>
    </div>
    
    <div class="actions">
        <h3>Review and Approve</h3>
        <p>Please review the analysis above and approve execution of recommended actions.</p>
        <textarea id="approval-comment" placeholder="Add comments or justification (optional)" rows="3"></textarea>
        <br><br>
        <button class="btn btn-approve" onclick="submitApproval('approve')">✅ Approve & Execute</button>
        <button class="btn btn-reject" onclick="submitApproval('reject')">❌ Reject</button>
    </div>
    
    <script>
        function submitApproval(action) {
            const comment = document.getElementById('approval-comment').value;
            fetch('${API_GATEWAY_URL}/approval', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    alert_id: '${alert_id}',
                    action: action,
                    comment: comment,
                    approved_by: '${user_email}'
                })
            }).then(response => {
                if (response.ok) {
                    document.body.innerHTML = '<div class="header"><h1>✅ Action Recorded</h1><p>Your decision has been submitted.</p></div>';
                }
            });
        }
    </script>
</body>
</html>
```

### Approval Handler Lambda

**File:** `src/ops/lambda_approval_handler.py`

```python
import boto3
import json
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_ALERTS_TABLE'])
sns = boto3.client('sns')

def lambda_handler(event, context):
    """
    Handle approval/rejection actions from users
    Can be triggered via:
    - API Gateway (web approval page)
    - Teams webhook callback
    - Direct Lambda invocation
    """
    # Parse request
    if 'body' in event:
        body = json.loads(event['body'])
    else:
        body = event
    
    alert_id = body['alert_id']
    action = body['action']  # 'approve' or 'reject'
    approved_by = body.get('approved_by', 'unknown')
    comment = body.get('comment', '')
    
    # Retrieve alert data
    response = table.get_item(Key={'alert_id': alert_id})
    if 'Item' not in response:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Alert not found'})
        }
    
    alert_data = response['Item']
    
    # Check if already processed
    if alert_data['approval_status'] != 'pending':
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': f"Alert already {alert_data['approval_status']}"
            })
        }
    
    # Update approval status
    if action == 'approve':
        table.update_item(
            Key={'alert_id': alert_id},
            UpdateExpression='''
                SET approval_status = :status,
                    approved_by = :user,
                    approved_at = :time,
                    approval_comment = :comment
            ''',
            ExpressionAttributeValues={
                ':status': 'approved',
                ':user': approved_by,
                ':time': datetime.now().isoformat(),
                ':comment': comment
            }
        )
        
        # Trigger execution Lambda
        sns.publish(
            TopicArn=os.environ['EXECUTION_TRIGGER_SNS'],
            Subject=f'Execute Alert {alert_id}',
            Message=json.dumps({
                'alert_id': alert_id,
                'approved_by': approved_by
            })
        )
        
        # Send notification
        send_approval_notification(alert_data, approved_by, 'approved')
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Approval recorded. Execution triggered.',
                'alert_id': alert_id
            })
        }
    
    elif action == 'reject':
        table.update_item(
            Key={'alert_id': alert_id},
            UpdateExpression='''
                SET approval_status = :status,
                    rejected_by = :user,
                    rejected_at = :time,
                    rejection_reason = :reason
            ''',
            ExpressionAttributeValues={
                ':status': 'rejected',
                ':user': approved_by,
                ':time': datetime.now().isoformat(),
                ':reason': comment
            }
        )
        
        send_approval_notification(alert_data, approved_by, 'rejected')
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Rejection recorded.',
                'alert_id': alert_id
            })
        }
    
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid action'})
        }


def send_approval_notification(alert_data, user, decision):
    """Send notification about approval decision"""
    # Implementation similar to send_teams_notification
    pass
```

---

## 🚀 Phase 3: Agent Execution

### Context Retention Strategy

#### Method 1: Session-Based (Recommended for Bedrock Agents)

**Pros:**
- Native support in Bedrock Agent Runtime
- Agent maintains conversation context
- More natural for complex multi-step operations

**Implementation:**
```python
# During initial analysis (Phase 1)
session_id = str(uuid.uuid4())
agent_response = invoke_agent_for_analysis(
    domain=domain,
    timestamp=timestamp,
    error_details=error_details,
    session_id=session_id  # Create new session
)

# Store session_id in DynamoDB
dynamodb.put_item({
    'alert_id': alert_id,
    'agent_session_id': session_id,
    's3_analysis_url': s3_url
})

# During execution (Phase 4)
stored_data = dynamodb.get_item(Key={'alert_id': alert_id})
execution_prompt = f"""
You previously analyzed alert {alert_id} in this session.
Your analysis has been APPROVED by {approved_by}.

Execute the immediate actions you recommended.
Report progress for each step.
"""

# Reuse same session_id for context continuity
execution_result = invoke_agent(
    execution_prompt,
    session_id=stored_data['agent_session_id']  # Same session
)
```

#### Method 2: Analysis-Embedded (Simpler, More Reliable)

**Pros:**
- No dependency on session state
- More reliable for long delays between analysis and execution
- Easier to debug and test

**Implementation:**
```python
# Retrieve full analysis from S3
s3_client = boto3.client('s3')
analysis_obj = s3_client.get_object(
    Bucket=bucket,
    Key=alert_data['s3_analysis_key']
)
full_analysis = analysis_obj['Body'].read().decode('utf-8')

# Include full context in execution prompt
execution_prompt = f"""
EXECUTION PHASE - Your previous analysis has been APPROVED.

Original Alert ID: {alert_id}
Domain: {alert_data['domain']}
Approved by: {approved_by}
Approval timestamp: {approved_at}

=== YOUR PREVIOUS ANALYSIS ===
{full_analysis}
================================

TASK: Execute the "IMMEDIATE ACTIONS REQUIRED" section from your analysis above.

For each action:
1. State what you're about to do
2. Execute the AWS SDK call
3. Report the result
4. Confirm success or report errors

Use the AWS tools available to you. Proceed with execution now.
"""

execution_result = invoke_agent_for_execution(execution_prompt)
```

### Execution Lambda Implementation

**File:** `src/ops/lambda_execution_handler.py`

```python
import boto3
import json
import os
from datetime import datetime
from src.ops.lambda_ping_monitor import invoke_agent_for_analysis

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
table = dynamodb.Table(os.environ['DYNAMODB_ALERTS_TABLE'])

def lambda_handler(event, context):
    """
    Execute agent recommendations after approval
    Triggered by SNS from approval handler
    """
    # Parse SNS message
    if 'Records' in event:
        message = json.loads(event['Records'][0]['Sns']['Message'])
    else:
        message = event
    
    alert_id = message['alert_id']
    approved_by = message.get('approved_by', 'unknown')
    
    print(f"Executing remediation for alert {alert_id}")
    
    # 1. Retrieve alert data from DynamoDB
    response = table.get_item(Key={'alert_id': alert_id})
    alert_data = response['Item']
    
    # Update execution status to in_progress
    table.update_item(
        Key={'alert_id': alert_id},
        UpdateExpression='SET execution_status = :status',
        ExpressionAttributeValues={':status': 'in_progress'}
    )
    
    # 2. Retrieve full analysis from S3
    analysis_obj = s3_client.get_object(
        Bucket=os.environ['S3_ANALYSIS_BUCKET'],
        Key=alert_data['s3_analysis_key']
    )
    full_analysis = analysis_obj['Body'].read().decode('utf-8')
    
    # 3. Construct execution prompt with full context
    execution_prompt = construct_execution_prompt(
        alert_data,
        full_analysis,
        approved_by
    )
    
    # 4. Invoke agent for execution
    start_time = datetime.now()
    
    try:
        # Option A: Reuse session for context
        execution_result = invoke_agent_with_context(
            execution_prompt,
            session_id=alert_data.get('agent_session_id')
        )
        
        execution_status = 'completed'
        
    except Exception as e:
        print(f"Execution failed: {e}")
        execution_result = f"Execution failed: {str(e)}"
        execution_status = 'failed'
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # 5. Upload execution log to S3
    execution_log_url = upload_execution_log_to_s3(
        alert_id,
        alert_data['domain'],
        execution_result,
        alert_data,
        approved_by
    )
    
    # 6. Update DynamoDB with results
    table.update_item(
        Key={'alert_id': alert_id},
        UpdateExpression='''
            SET execution_status = :status,
                execution_log_url = :url,
                executed_at = :time,
                execution_duration = :duration
        ''',
        ExpressionAttributeValues={
            ':status': execution_status,
            ':url': execution_log_url,
            ':time': end_time.isoformat(),
            ':duration': int(duration)
        }
    )
    
    # 7. Send completion notification
    send_execution_notification(
        alert_data['domain'],
        execution_status,
        execution_log_url,
        duration,
        approved_by
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'alert_id': alert_id,
            'execution_status': execution_status,
            'duration': duration,
            'log_url': execution_log_url
        })
    }


def construct_execution_prompt(alert_data, full_analysis, approved_by):
    """Construct comprehensive execution prompt"""
    return f"""
EXECUTION PHASE - APPROVED REMEDIATION

**Alert Information:**
- Alert ID: {alert_data['alert_id']}
- Domain: {alert_data['domain']}
- Issue Type: {alert_data.get('issue_type', 'unknown')}
- Original Timestamp: {alert_data['timestamp']}

**Approval Details:**
- Approved by: {approved_by}
- Approval time: {alert_data.get('approved_at', 'just now')}
- Status: AUTHORIZED TO EXECUTE

**Your Previous Analysis:**
{full_analysis}

**EXECUTION INSTRUCTIONS:**

You are now authorized to execute the remediation actions you recommended.

1. **Verify Current State**
   - Re-check the issue still exists
   - Confirm no other changes were made
   - Validate it's safe to proceed

2. **Execute Immediate Actions**
   - Follow the "IMMEDIATE ACTIONS REQUIRED" from your analysis
   - Execute each action step-by-step
   - Use AWS SDK tools available to you

3. **Report Progress**
   - For each action, state:
     * What you're doing
     * The AWS API call being made
     * The result/response
     * Success confirmation or error details

4. **Validation**
   - After all actions, verify the issue is resolved
   - Test the domain/service is now working
   - Report final status

5. **Rollback Plan**
   - If any action fails, state what rollback is needed
   - Do not proceed if critical errors occur

**IMPORTANT:**
- Be precise about what AWS resources you're modifying
- Log all API calls and responses
- If uncertain, ask for clarification before proceeding

Begin execution now.
"""


def invoke_agent_with_context(prompt, session_id=None):
    """Invoke agent with optional session context"""
    # Implementation similar to invoke_agent_for_analysis
    # but with execution-specific handling
    pass


def upload_execution_log_to_s3(alert_id, domain, execution_result, 
                                alert_data, approved_by):
    """Upload detailed execution log to S3"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H-%M-%S")
    filename = f"executions/{date_str}/{domain}/{time_str}-{alert_id}.md"
    
    markdown_content = f"""# Execution Log - {domain}

## Execution Summary

**Alert ID:** {alert_id}  
**Domain:** {domain}  
**Executed At:** {datetime.now().isoformat()}  
**Approved By:** {approved_by}  
**Original Issue:** {alert_data.get('error_details', 'N/A')}

---

## Original Analysis

[View Full Analysis]({alert_data.get('s3_analysis_url', 'N/A')})

**Summary:** {alert_data.get('agent_analysis', 'N/A')[:500]}...

---

## Execution Results

{execution_result}

---

## Metadata

- Alert Timestamp: {alert_data['timestamp']}
- Approval Timestamp: {alert_data.get('approved_at', 'N/A')}
- Execution ID: {alert_id}

*Generated by AWS CloudOps Agent - Execution Phase*
"""
    
    s3_client.put_object(
        Bucket=os.environ['S3_ANALYSIS_BUCKET'],
        Key=filename,
        Body=markdown_content.encode('utf-8'),
        ContentType='text/markdown',
        Metadata={
            'alert-id': alert_id,
            'domain': domain,
            'approved-by': approved_by,
            'phase': 'execution'
        }
    )
    
    region = os.environ.get('AWS_REGION', 'ap-southeast-1')
    s3_url = f"https://{os.environ['S3_ANALYSIS_BUCKET']}.s3.{region}.amazonaws.com/{filename}"
    
    print(f"Execution log uploaded: {s3_url}")
    return s3_url


def send_execution_notification(domain, status, log_url, duration, approved_by):
    """Send Teams/Slack notification about execution results"""
    # Implementation similar to send_teams_notification
    # but focused on execution results
    pass
```

---

## 💡 Implementation Recommendations

### Immediate (Phase 1 - Current Sprint)
✅ **Already Implemented:**
- Lambda ping monitor
- Agent invocation
- S3 analysis storage
- Teams/Slack notifications with summaries

🔨 **To Add:**
1. DynamoDB table for workflow tracking
2. Store `agent_session_id` with each alert
3. Enhanced metadata (severity, affected services)

### Short-term (Phase 2 - Next Sprint)
1. **Approval Handler Lambda**
   - Create `lambda_approval_handler.py`
   - Deploy API Gateway endpoint
   - Update Teams buttons to call approval API

2. **Simple Approval Web Page**
   - HTML page hosted on S3 + CloudFront
   - Display full analysis
   - Approve/Reject buttons
   - Comments field

3. **Enhanced Notifications**
   - Add approval status updates
   - Show who approved/rejected
   - Include approval comments

### Long-term (Phase 3 - Production Ready)
1. **Execution Lambda**
   - Create `lambda_execution_handler.py`
   - Implement context retention
   - Add rollback capability

2. **Step Functions Orchestration**
   - Replace direct Lambda triggers
   - Add timeout handling
   - Implement retry logic
   - Support for multi-stage approvals

3. **Advanced Features**
   - Multi-level approvals for critical changes
   - Approval delegation
   - Scheduled execution windows
   - Impact assessment scoring
   - Change advisory board (CAB) integration

---

## 🔒 Security Best Practices

### 1. Access Control

**IAM Roles & Policies:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MonitorLambdaReadOnly",
      "Effect": "Allow",
      "Action": [
        "route53:Get*",
        "route53:List*",
        "cloudfront:Get*",
        "cloudfront:List*",
        "s3:GetObject",
        "s3:ListBucket",
        "cloudwatch:Get*",
        "cloudwatch:Describe*",
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ExecutionLambdaWriteAccess",
      "Effect": "Allow",
      "Action": [
        "route53:ChangeResourceRecordSets",
        "cloudfront:UpdateDistribution",
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": [
        "arn:aws:route53:::hostedzone/*",
        "arn:aws:cloudfront::*:distribution/*",
        "arn:aws:s3:::your-bucket/*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "ap-southeast-1"
        }
      }
    }
  ]
}
```

### 2. Approval Security

**Authentication:**
- Cognito User Pools for approval page
- Teams/Slack user identity validation
- API Gateway authorizers

**Authorization:**
```python
APPROVAL_PERMISSIONS = {
    'critical': ['admin', 'ops-lead'],
    'high': ['admin', 'ops-lead', 'senior-engineer'],
    'medium': ['admin', 'ops-lead', 'senior-engineer', 'engineer'],
    'low': ['*']  # Anyone authenticated
}

def check_approval_permission(user_role, alert_severity):
    """Verify user has permission to approve alert"""
    allowed_roles = APPROVAL_PERMISSIONS.get(alert_severity, [])
    return user_role in allowed_roles or '*' in allowed_roles
```

### 3. Execution Safety

**Pre-execution Checks:**
```python
def pre_execution_validation(alert_data):
    """Safety checks before execution"""
    checks = {
        'approval_valid': check_approval_not_expired(alert_data),
        'no_conflicts': check_no_concurrent_changes(alert_data),
        'maintenance_window': check_maintenance_window(),
        'issue_still_exists': verify_issue_current(alert_data),
        'resources_available': check_resource_availability(alert_data)
    }
    
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        raise ExecutionBlockedException(f"Pre-checks failed: {failed}")
    
    return True
```

**Rate Limiting:**
```python
# Limit executions per time window
MAX_EXECUTIONS_PER_HOUR = 10
MAX_CONCURRENT_EXECUTIONS = 3

def check_execution_limits():
    """Prevent execution storms"""
    # Check DynamoDB for recent executions
    recent = query_recent_executions(hours=1)
    if len(recent) >= MAX_EXECUTIONS_PER_HOUR:
        raise RateLimitException("Too many executions in past hour")
    
    in_progress = query_in_progress_executions()
    if len(in_progress) >= MAX_CONCURRENT_EXECUTIONS:
        raise RateLimitException("Too many concurrent executions")
```

### 4. Audit Trail

**Comprehensive Logging:**
```python
def audit_log(event_type, alert_id, user, action, result):
    """Log all workflow events"""
    cloudwatch_logs = boto3.client('logs')
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,  # 'detection', 'analysis', 'approval', 'execution'
        'alert_id': alert_id,
        'user': user,
        'action': action,
        'result': result,
        'ip_address': get_source_ip(),
        'user_agent': get_user_agent()
    }
    
    cloudwatch_logs.put_log_events(
        logGroupName='/aws/cloudops-agent/audit',
        logStreamName=datetime.now().strftime('%Y-%m-%d'),
        logEvents=[{
            'timestamp': int(datetime.now().timestamp() * 1000),
            'message': json.dumps(log_entry)
        }]
    )
```

### 5. Secrets Management

```python
# Use AWS Secrets Manager for sensitive data
def get_secret(secret_name):
    """Retrieve secrets securely"""
    secrets_client = boto3.client('secretsmanager')
    response = secrets_client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Store in environment (reference, not value)
os.environ['COGNITO_CLIENT_SECRET_ARN'] = 'arn:aws:secretsmanager:...'

# Retrieve at runtime
cognito_secret = get_secret(os.environ['COGNITO_CLIENT_SECRET_ARN'])
```

---

## 📊 Monitoring & Observability

### CloudWatch Dashboards

**Key Metrics to Track:**
```python
CLOUDWATCH_METRICS = {
    'Detection': [
        'AlertsGenerated',
        'DetectionLatency',
        'FalsePositiveRate'
    ],
    'Analysis': [
        'AgentInvocationCount',
        'AgentResponseTime',
        'AgentTokensUsed',
        'AgentErrorRate'
    ],
    'Approval': [
        'PendingApprovals',
        'ApprovalLatency',
        'ApprovalRate',
        'RejectionRate'
    ],
    'Execution': [
        'ExecutionsTriggered',
        'ExecutionSuccessRate',
        'ExecutionDuration',
        'ExecutionErrors'
    ]
}
```

### CloudWatch Alarms

```python
# Critical workflow failures
ALARMS = [
    {
        'name': 'HighAgentErrorRate',
        'metric': 'AgentErrorRate',
        'threshold': 20,  # percent
        'period': 300,
        'evaluation_periods': 2
    },
    {
        'name': 'ExecutionFailures',
        'metric': 'ExecutionErrors',
        'threshold': 3,
        'period': 3600,
        'evaluation_periods': 1
    },
    {
        'name': 'ApprovalBacklog',
        'metric': 'PendingApprovals',
        'threshold': 10,
        'period': 1800,
        'evaluation_periods': 1
    }
]
```

### X-Ray Tracing

```python
import aws_xray_sdk
from aws_xray_sdk.core import xray_recorder

@xray_recorder.capture('analyze_domain_issue')
def lambda_handler(event, context):
    """Traced Lambda function"""
    
    with xray_recorder.capture('invoke_agent'):
        agent_response = invoke_agent_for_analysis(...)
    
    with xray_recorder.capture('upload_to_s3'):
        s3_url = upload_analysis_to_s3(...)
    
    with xray_recorder.capture('send_notifications'):
        send_teams_notification(...)
```

### Cost Tracking

```python
def estimate_cost(alert_data, execution_result):
    """Track costs per alert"""
    costs = {
        'bedrock_agent_tokens': calculate_token_cost(
            alert_data.get('agent_tokens_used', 0)
        ),
        'lambda_invocations': 0.0002 * 3,  # Monitor + Approval + Execution
        's3_storage': 0.023 / 1000 / 30,  # Per GB per day
        'dynamodb_writes': 0.000001 * 5,  # 5 write operations
        'api_gateway': 0.000001 * 2  # 2 API calls
    }
    
    total = sum(costs.values())
    
    # Log to CloudWatch for cost analysis
    cloudwatch = boto3.client('cloudwatch')
    cloudwatch.put_metric_data(
        Namespace='CloudOpsAgent/Costs',
        MetricData=[{
            'MetricName': 'CostPerAlert',
            'Value': total,
            'Unit': 'None',
            'Dimensions': [
                {'Name': 'AlertType', 'Value': alert_data['issue_type']}
            ]
        }]
    )
    
    return total
```

---

## 🎯 Success Metrics

### Key Performance Indicators (KPIs)

**Operational Metrics:**
- **Mean Time to Detection (MTTD):** < 5 minutes
- **Mean Time to Analysis (MTTA):** < 2 minutes
- **Mean Time to Approval (MTTAp):** < 15 minutes
- **Mean Time to Resolution (MTTR):** < 30 minutes
- **False Positive Rate:** < 5%
- **Execution Success Rate:** > 95%

**Business Metrics:**
- **Incident Cost Reduction:** 60% reduction in manual effort
- **Availability Improvement:** 99.9% → 99.95%
- **Customer Impact:** Reduced downtime by 70%

---

## 📚 Additional Resources

### Related Documentation
- [Lambda Ping Monitor](./LAMBDA_PING_MONITOR.md)
- [Cognito Authentication Setup](./COGNITO_AUTH_SETUP.md)
- [Deployment Commands](./DEPLOYMENT_COMMANDS.md)
- [Slack Approval Workflow](./FEATURE_SLACK_APPROVAL.md)

### AWS Service Documentation
- [AWS Bedrock Agent Runtime API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_InvokeAgent.html)
- [API Gateway Lambda Authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html)
- [Step Functions for Orchestration](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
- [DynamoDB Streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html)

---

## 🔄 Version History

- **v1.0** (2025-12-02): Initial best practices documentation
  - Phase 1-4 workflow architecture
  - Security recommendations
  - Monitoring strategies

---

*This document is maintained by the CloudOps team. Last updated: December 2, 2025*
