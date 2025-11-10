#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import uuid
import requests
import urllib.parse
import json
import os
import sys
import getpass


# Add project root to path
src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_root)

from utils.config_manager import AgentCoreConfigManager
from components.auth import get_cognito_jwt_token

# ============================================================================
# CONFIGURATION
# ============================================================================

config_manager = AgentCoreConfigManager()
merged_config = config_manager.get_merged_config()
base_config = config_manager.get_base_settings()
cognito_config = config_manager.get_basic_auth_settings()

# Get runtime ARN and region
runtime_arn = merged_config.get("runtime", {}).get("p_agent", {}).get("arn", "")
region = base_config.get("aws", {}).get("region", "")

if not runtime_arn:
    print("❌ Runtime ARN not found in config. Please deploy the runtime first.")
    sys.exit(1)

# Get Cognito configuration
cognito_pool_id = cognito_config.get("pool_id", "")
cognito_client_id = cognito_config.get("client_id", "")
cognito_discovery_url = cognito_config.get("discovery_url", "")

if not all([cognito_pool_id, cognito_client_id, cognito_discovery_url]):
    print("❌ Missing Cognito configuration. Required:")
    print(f"   - pool_id: {cognito_pool_id or 'MISSING'}")
    print(f"   - client_id: {cognito_client_id or 'MISSING'}")
    print(f"   - discovery_url: {cognito_discovery_url or 'MISSING'}")
    sys.exit(1)

print(f"\n📋 Cognito Configuration:")
print(f"   Pool ID: {cognito_pool_id}")
print(f"   Client ID: {cognito_client_id}")
print(f"   Discovery URL: {cognito_discovery_url}")
print()

# Prompt user for credentials
print("🔐 AWS Cognito Authentication")
print("=" * 50)
cognito_username = input("Username: ").strip()
cognito_password = getpass.getpass("Password: ")

if not cognito_username or not cognito_password:
    print("❌ Username and password are required")
    sys.exit(1)

# ============================================================================
# GET JWT TOKEN
# ============================================================================

print("🔐 Authenticating with AWS Cognito...")
jwt_token = get_cognito_jwt_token(cognito_username, cognito_password, cognito_client_id)

if not jwt_token:
    print("❌ Failed to obtain JWT token")
    sys.exit(1)

print("✅ JWT token obtained successfully")

# ============================================================================
# INVOKE AGENT WITH JWT TOKEN
# ============================================================================

# URL encode the agent ARN
escaped_agent_arn = urllib.parse.quote(runtime_arn, safe="")

# Construct the endpoint URL
url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"

print(f"\n🤖 AWS CloudOps Agent - JWT Auth Mode")
print(f"🏷️  Runtime ARN: {runtime_arn}")
print(f"👤 User: {cognito_username}")
print(f"\n⚠️  Note: Runtime must be configured with JWT authorizer")
print(f"   Discovery URL: {cognito_discovery_url}")
print("\nType 'exit', 'end', or 'bye' to quit\n")
print("=" * 50)

# Chat loop
session_id = str(uuid.uuid4())

while True:
    # Get user input
    user_prompt = input("\n💬 You: ").strip()

    if not user_prompt:
        continue

    # Check for exit commands
    if user_prompt.lower() in ["exit", "end", "bye"]:
        print("\n👋 Goodbye!")
        break

    # Set up headers with JWT token
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }

    # Prepare payload
    payload = {
        "prompt": user_prompt,
        "session_id": session_id,
        "actor_id": cognito_username,
    }

    print("\r🤖 Agent: ⏳", end="", flush=True)

    try:
        # Invoke the agent with JWT token (streaming response)
        response = requests.post(
            url, headers=headers, data=json.dumps(payload), stream=True
        )

        print("\r🤖 Agent: ", end="", flush=True)

        # Handle response
        if response.status_code == 200:
            # Handle streaming response (SSE format)
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    if decoded_line.startswith("data: "):
                        data_content = decoded_line[6:]  # Remove 'data: ' prefix
                        try:
                            data_json = json.loads(data_content)
                            # Only print text_delta content for clean output
                            if data_json.get("type") == "text_delta":
                                print(data_json.get("content", ""), end="", flush=True)
                        except json.JSONDecodeError:
                            pass  # Skip non-JSON lines
        elif response.status_code == 401:
            print("❌ Authentication failed. Token may be expired.")
            print("Please restart the script to get a new token.")
            break
        else:
            print(f"❌ Error (Status {response.status_code})")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2))
                if response.status_code == 400 and "DiscoveryUrl" in response.text:
                    print("\n💡 Hint: Runtime needs JWT authorizer configuration.")
                    print(f"   Expected Discovery URL: {cognito_discovery_url}")
            except:
                print(response.text[:500])
                if "DiscoveryUrl" in response.text:
                    print("\n💡 Hint: Runtime needs JWT authorizer configuration.")
                    print(f"   Expected Discovery URL: {cognito_discovery_url}")

    except requests.exceptions.Timeout:
        print("\r🤖 Agent: ❌ Request timed out")
    except requests.exceptions.RequestException as e:
        print(f"\r🤖 Agent: ❌ Request failed: {e}")
    except Exception as e:
        print(f"\r🤖 Agent: ❌ Unexpected error: {e}")

    print("\n" + "=" * 50)
