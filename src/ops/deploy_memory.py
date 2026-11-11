#!/usr/bin/env python3

# ============================================================================
# IMPORTS
# ============================================================================

import boto3
import time
import sys
import os

# ============================================================================
# CONFIGURATION
# ============================================================================

# Add project root to path for shared config manager
src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_root)

from utils.config_manager import AgentCoreConfigManager

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def update_config_with_memory_arn(config_manager, memory_arn, memory_id):
    """Update dynamic configuration with memory ARN"""
    print(f"\n📝 Updating dynamic configuration with memory ARN...")
    try:
        updates = {"memory": {"arn": memory_arn, "id": memory_id}}
        config_manager.update_dynamic_config(updates)
        print("   ✅ Dynamic config updated with memory ARN")
    except Exception as config_error:
        print(f"   ⚠️  Error updating config: {config_error}")


# Initialize configuration manager
config_manager = AgentCoreConfigManager()

# Get configuration values
base_config = config_manager.get_base_settings()
merged_config = config_manager.get_merged_config()

# Extract configuration values
REGION = base_config["aws"]["region"]
ROLE_ARN = base_config["runtime"]["role_arn"]
MEMORY_ID = merged_config.get("memory", {}).get("id", "")
MEMORY_NAME = base_config.get("memory", {}).get("name", "aws-cloudops-agent-memory")
MEMORY_DESCRIPTION = base_config.get("memory", {}).get(
    "description", "AWS CloudOps Agent conversation memory storage"
)
MEMORY_EVENT_EXPIRY_DAYS = base_config.get("memory", {}).get("event_expiry_days", 30)

print("🧠 Creating or updating AgentCore Memory for AWS CloudOps agent...")
print(f"   📝 Name: {MEMORY_NAME}")
print(f"   🔐 Role: {ROLE_ARN}")

control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)

# Check if memory already exists
memory_exists = False
existing_memory_arn = None
existing_memory_id = None

try:
    memories_response = control_client.list_memories()
    for memory in memories_response.get("memories", []):
        if memory.get("id") == MEMORY_ID:
            memory_exists = True
            existing_memory_arn = memory.get("arn")
            existing_memory_id = memory.get("id")
            print(f"✅ Found existing memory: {existing_memory_arn}")
            break
except Exception as e:
    print(f"⚠️  Error checking existing memories: {e}")

try:
    if memory_exists and existing_memory_arn:
        print(f"\n✅ Memory already exists, using existing memory")
        update_config_with_memory_arn(config_manager, existing_memory_arn)

        print(f"\n🎉 AWS CloudOps Agent Memory Ready!")
        print(f"🏷️  Memory ARN: {existing_memory_arn}")
        print(f"🆔 Memory ID: {existing_memory_id}")
    else:
        print(f"\n🆕 Creating new memory...")

        response = control_client.create_memory(
            name=MEMORY_NAME,
            description=MEMORY_DESCRIPTION,
            memoryExecutionRoleArn=ROLE_ARN,
            eventExpiryDuration=MEMORY_EVENT_EXPIRY_DAYS,
        )

        memory_arn = response["memory"]["arn"]
        memory_id = response["memory"]["id"]

        print(f"✅ AWS CloudOps Agent Memory created!")
        print(f"🏷️  ARN: {memory_arn}")
        print(f"🆔 Memory ID: {memory_id}")

        print(f"\n⏳ Waiting for memory to be READY...")
        max_wait = 300  # 5 minutes
        wait_time = 0

        while wait_time < max_wait:
            try:
                status_response = control_client.get_memory(memoryId=memory_id)
                status = status_response.get("memory").get("status")
                print(f"   📊 Status: {status} ({wait_time}s)")

                if status == "ACTIVE":
                    print(f"✅ Memory is ACTIVE!")
                    update_config_with_memory_arn(config_manager, memory_arn, memory_id)
                    break
                elif status in ["FAILED", "DELETING"]:
                    print(f"❌ Memory creation failed with status: {status}")
                    break

                time.sleep(10)
                wait_time += 10

            except Exception as e:
                print(f"❌ Error checking status: {e}")
                break

        if wait_time >= max_wait:
            print(f"⚠️  Memory creation taking longer than expected")

        print(f"\n🧪 Memory ready for use:")
        print(f"   ARN: {memory_arn}")
        print(f"   ID: {memory_id}")

except Exception as e:
    print(f"❌ Error creating/updating memory: {e}")
    sys.exit(1)
