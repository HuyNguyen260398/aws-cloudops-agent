# JWT Agent Invocation - Issue Analysis & Resolution

## Issues Found

### 1. **Unicode Encoding Error (Windows)**
**Problem:** Emojis in print statements caused `UnicodeEncodeError` on Windows console
```
UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f510'
```

**Solution:** Added UTF-8 encoding configuration at the start of the script:
```python
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass
```

### 2. **Typo in Environment Variable**
**Problem:** Typo in `os.getenv()` call - extra comma in variable name
```python
cognito_password = os.getenv('COGNITO_PASSWORD,', PASSWORD)  # Wrong
```

**Solution:** Removed the comma:
```python
cognito_password = os.getenv('COGNITO_PASSWORD', PASSWORD)  # Correct
```

### 3. **Response Format Mismatch**
**Problem:** Agent returns **streaming SSE** (Server-Sent Events), not JSON
- Response header: `Content-Type: text/event-stream; charset=utf-8`
- Attempted to parse as JSON caused `JSONDecodeError`

**Solution:** Updated to handle streaming response:
```python
response = requests.post(url, headers=headers, json=payload, stream=True)

for line in response.iter_lines():
    if line:
        decoded_line = line.decode('utf-8')
        if decoded_line.startswith('data: '):
            data_content = decoded_line[6:]
            data_json = json.loads(data_content)
            if data_json.get('type') == 'text_delta':
                print(data_json.get('content', ''), end='', flush=True)
```

## Response Format

The agent returns SSE events with different types:
- `text_delta` - Actual response text (what we display)
- `event` - Internal agent events (metadata)

Example SSE line:
```json
data: {"content": "Hello", "type": "text_delta", "metadata": {...}}
```

## Test Results

✅ **JWT Authentication:** Successfully obtained token from Cognito
✅ **Agent Invocation:** Successfully invoked agent with Bearer token
✅ **Streaming Response:** Properly handled SSE streaming format
✅ **Response Display:** Clean text output without metadata noise

## Usage

```powershell
# Set credentials (optional, defaults provided)
$env:COGNITO_USERNAME="testuser"
$env:COGNITO_PASSWORD="MyPassword123!"

# Run the agent
uv run .\src\ops\invoke_agent_jwt.py
```

## Files Modified

1. `src/ops/invoke_agent_jwt.py` - Main JWT invoke script
2. `test_jwt_invoke.py` - Test script for debugging

## Key Learnings

1. Windows console requires explicit UTF-8 encoding for emojis
2. AgentCore returns streaming responses (SSE), not simple JSON
3. JWT token goes in `Authorization: Bearer {token}` header
4. Session ID is tracked via `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` header
5. Only `text_delta` events contain the actual response text
