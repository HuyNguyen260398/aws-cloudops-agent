#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Knowledge Base retrieval tool
Tests both direct tool invocation and agent integration
"""

import os
import sys
import asyncio

# Add project root to path
src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_root)

from tools.kb_retrieval import retrieve_from_knowledge_base, quick_kb_search
from utils.config_manager import AgentCoreConfigManager
import utils.mylogger as mylogger

logger = mylogger.get_logger()


def test_direct_tool_call():
    """Test 1: Direct tool invocation"""
    print("\n" + "=" * 80)
    print("TEST 1: Direct Tool Invocation")
    print("=" * 80)

    # Set required environment variables
    config_manager = AgentCoreConfigManager()
    merged_config = config_manager.get_merged_config()

    # Get KB ID and region from config or environment
    kb_id = os.environ.get('KNOWLEDGE_BASE_ID') or \
            merged_config.get('knowledge_base', {}).get('id', '')

    bedrock_region = os.environ.get('BEDROCK_REGION', 'ap-southeast-2')

    if not kb_id:
        print("❌ KNOWLEDGE_BASE_ID not set!")
        print("Please set it using one of these methods:")
        print("  export KNOWLEDGE_BASE_ID='your-kb-id'")
        print("  or add it to your config file")
        return False

    print(f"✅ Knowledge Base ID: {kb_id}")
    print(f"✅ Bedrock Region: {bedrock_region}")

    # Set environment variables
    os.environ['KNOWLEDGE_BASE_ID'] = kb_id
    os.environ['BEDROCK_REGION'] = bedrock_region

    # Test queries
    test_queries = [
        "AWS Lambda",
        "S3 bucket configuration",
        "VPC networking"
    ]

    print("\n📝 Testing retrieve_from_knowledge_base:")
    print("-" * 80)

    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        result = retrieve_from_knowledge_base(query, max_results=2)
        print(result)
        print("-" * 80)

    print("\n📝 Testing quick_kb_search:")
    print("-" * 80)

    query = "AWS Lambda"
    print(f"\n🔍 Quick search: '{query}'")
    result = quick_kb_search(query)
    print(result)
    print("-" * 80)

    return True


async def test_agent_integration():
    """Test 2: Agent integration with KB tools"""
    print("\n" + "=" * 80)
    print("TEST 2: Agent Integration")
    print("=" * 80)

    from strands.models import BedrockModel
    from agents.aws_cloudops_agent import AwsCloudOpsAgent

    # Get model configuration
    config_manager = AgentCoreConfigManager()
    model_settings = config_manager.get_model_settings()

    print(f"✅ Model: {model_settings['model_id']}")

    # Create agent with KB tools
    tools = [
        retrieve_from_knowledge_base,
        quick_kb_search
    ]

    model = BedrockModel(**model_settings, streaming=False)
    agent = AwsCloudOpsAgent(model=model, tools=tools)

    # Test prompts that should trigger KB retrieval
    test_prompts = [
        "Search the knowledge base for information about AWS Lambda",
        "What documentation do we have about S3 buckets?",
    ]

    for prompt in test_prompts:
        print(f"\n💬 Prompt: {prompt}")
        print("-" * 80)

        try:
            response = await agent.run_async(prompt)
            print(f"🤖 Response: {response}")
            print("-" * 80)
        except Exception as e:
            print(f"❌ Error: {e}")
            print("-" * 80)

    return True


async def test_streaming_integration():
    """Test 3: Streaming agent integration"""
    print("\n" + "=" * 80)
    print("TEST 3: Streaming Agent Integration")
    print("=" * 80)

    from strands.models import BedrockModel
    from agents.aws_cloudops_agent import AwsCloudOpsAgent

    # Get model configuration
    config_manager = AgentCoreConfigManager()
    model_settings = config_manager.get_model_settings()

    # Create agent with KB tools
    tools = [
        retrieve_from_knowledge_base,
        quick_kb_search
    ]

    model = BedrockModel(**model_settings, streaming=True)
    agent = AwsCloudOpsAgent(model=model, tools=tools)

    prompt = "Quick search the knowledge base for AWS Lambda information"

    print(f"\n💬 Prompt: {prompt}")
    print("-" * 80)
    print("🤖 Agent (streaming): ", end="", flush=True)

    try:
        async for event in agent.stream_async(prompt):
            # Extract and print text content
            if isinstance(event, dict) and 'event' in event:
                inner_event = event['event']
                if 'contentBlockDelta' in inner_event:
                    delta = inner_event['contentBlockDelta'].get('delta', {})
                    if 'text' in delta:
                        print(delta['text'], end="", flush=True)

        print("\n" + "-" * 80)
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("-" * 80)
        return False


def main():
    """Main test runner"""
    print("\n🧪 Knowledge Base Retrieval Tool - Test Suite")
    print("=" * 80)

    # Check environment
    kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
    if not kb_id:
        print("\n⚠️  KNOWLEDGE_BASE_ID not set in environment")
        print("Attempting to load from config...")

    # Run tests
    results = []

    # Test 1: Direct tool call
    try:
        result = test_direct_tool_call()
        results.append(("Direct Tool Call", result))
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
        results.append(("Direct Tool Call", False))

    # Test 2: Agent integration (non-streaming)
    try:
        result = asyncio.run(test_agent_integration())
        results.append(("Agent Integration", result))
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
        results.append(("Agent Integration", False))

    # Test 3: Streaming integration
    try:
        result = asyncio.run(test_streaming_integration())
        results.append(("Streaming Integration", result))
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
        results.append(("Streaming Integration", False))

    # Print summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    print("=" * 80 + "\n")

    # Return exit code
    all_passed = all(result[1] for result in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
