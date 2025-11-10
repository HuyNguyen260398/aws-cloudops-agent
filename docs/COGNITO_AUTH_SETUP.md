# Cognito Authentication Setup

## Overview
The agent uses AWS Cognito for JWT token authentication when connecting to the AgentCore Gateway.

## Configuration

### 1. Update static-config.yaml
Ensure your `config/static-config.yaml` has the Cognito configuration:

```yaml
auth:
  cognito_idp:
    pool_id: "ap-southeast-1_jjG5DkVCy"
    client_id: "40ede8sr0l0bs37hps0lbgvr8p"
    discovery_url: "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_jjG5DkVCy/.well-known/openid-configuration"
```

### 2. Set Environment Variables
For security, credentials should be set as environment variables:

**Windows (PowerShell):**
```powershell
$env:COGNITO_USERNAME = "your-username"
$env:COGNITO_PASSWORD = "your-password"
$env:COGNITO_CLIENT_ID = "40ede8sr0l0bs37hps0lbgvr8p"
$env:AWS_REGION = "ap-southeast-1"
```

**Windows (CMD):**
```cmd
set COGNITO_USERNAME=your-username
set COGNITO_PASSWORD=your-password
set COGNITO_CLIENT_ID=40ede8sr0l0bs37hps0lbgvr8p
set AWS_REGION=ap-southeast-1
```

**Linux/Mac:**
```bash
export COGNITO_USERNAME="your-username"
export COGNITO_PASSWORD="your-password"
export COGNITO_CLIENT_ID="40ede8sr0l0bs37hps0lbgvr8p"
export AWS_REGION="ap-southeast-1"
```

## How It Works

1. **Token Retrieval**: When the agent starts, it checks for gateway URL and authentication
2. **Cognito Auth**: If gateway is configured, it gets JWT token from Cognito using USER_PASSWORD_AUTH flow
3. **Gateway Connection**: Token is used in Authorization header to authenticate with AgentCore Gateway
4. **Tool Discovery**: Once authenticated, agent discovers and uses MCP tools from gateway
5. **Fallback**: If authentication fails, agent falls back to local tools

## Testing

Run the agent and check logs:
```bash
uv run src\agent_runtime.py
```

Look for these log messages:
- ✅ Successfully obtained Cognito JWT token
- ✅ OAuth initialized
- 🛠️ Streaming with X MCP tools + local tools

## Troubleshooting

**No token obtained:**
- Verify environment variables are set
- Check Cognito user pool and client configuration
- Ensure user exists and password is correct

**Gateway connection fails:**
- Verify gateway URL in config
- Check token is valid (not expired)
- Ensure gateway accepts Cognito tokens

**Falls back to local tools:**
- Check if gateway URL is configured
- Verify authentication succeeded
- Review agent logs for specific errors
