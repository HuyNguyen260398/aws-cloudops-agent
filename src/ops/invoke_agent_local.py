#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import uuid
import requests
import json


# ============================================================================
# CONFIGURATION
# ============================================================================

# Local agent endpoint
LOCAL_AGENT_URL = "http://localhost:8080/invocations"

print(f"\n🤖 AWS CloudOps Agent - Local Testing Mode")
print(f"🔗 Endpoint: {LOCAL_AGENT_URL}")
print("\nType 'exit', 'end', or 'bye' to quit")
print("Type 'new' to start a new session\n")
print("=" * 50)

# ============================================================================
# CHAT LOOP
# ============================================================================

session_id = str(uuid.uuid4())
print(f"📋 Session ID: {session_id}")

while True:
    # Get user input
    user_prompt = input("\n💬 You: ").strip()

    if not user_prompt:
        continue

    # Check for special commands
    if user_prompt.lower() in ["exit", "end", "bye"]:
        print("\n👋 Goodbye!")
        break

    if user_prompt.lower() == "new":
        session_id = str(uuid.uuid4())
        print(f"📋 New session started: {session_id}")
        continue

    # Set up headers
    headers = {
        "Content-Type": "application/json",
    }

    # Prepare payload
    payload = {
        "prompt": user_prompt,
        "session_id": session_id,
        "actor_id": "user",
    }

    print("\r🤖 Agent: ⏳", end="", flush=True)

    try:
        # Invoke the local agent (streaming response)
        response = requests.post(
            LOCAL_AGENT_URL,
            headers=headers,
            data=json.dumps(payload),
            stream=True,
            timeout=300,  # 5 minute timeout for long operations
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

                            # Handle different event types
                            event_type = data_json.get("type", "")

                            if event_type == "text_delta":
                                # Regular text output
                                print(data_json.get("content", ""), end="", flush=True)
                            elif event_type == "text":
                                # Full text output
                                print(data_json.get("text", ""), end="", flush=True)
                            elif event_type == "handoff_required":
                                # Agent requires confirmation
                                print(
                                    f"\n⚠️ {data_json.get('message', 'Confirmation required')}",
                                    end="",
                                    flush=True,
                                )
                            elif event_type == "error":
                                # Error message
                                print(
                                    f"\n❌ Error: {data_json.get('message', 'Unknown error')}",
                                    end="",
                                    flush=True,
                                )

                        except json.JSONDecodeError:
                            # Skip non-JSON lines
                            pass
        else:
            print(f"❌ Error (Status {response.status_code})")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2))
            except:
                print(response.text[:500])

    except requests.exceptions.Timeout:
        print("\r🤖 Agent: ❌ Request timed out (exceeded 5 minutes)")
    except requests.exceptions.ConnectionError:
        print("\r🤖 Agent: ❌ Connection failed - Is the local agent running?")
        print(f"   Make sure the agent is started at {LOCAL_AGENT_URL}")
    except requests.exceptions.RequestException as e:
        print(f"\r🤖 Agent: ❌ Request failed: {e}")
    except Exception as e:
        print(f"\r🤖 Agent: ❌ Unexpected error: {e}")

    print("\n" + "=" * 50)
