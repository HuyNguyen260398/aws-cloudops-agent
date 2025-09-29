#!/usr/bin/env python3
"""
Test script for AWS CloudOps Agent Lambda deployment
Tests both health check and chat functionality
"""

import json
import requests
import sys
import argparse
from typing import Dict, Any

def test_health_endpoint(base_url: str) -> bool:
    """Test the health check endpoint"""
    health_url = f"{base_url}/health"
    
    try:
        print(f"🔍 Testing health endpoint: {health_url}")
        response = requests.get(health_url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Health check passed: {result.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def test_chat_endpoint(base_url: str, question: str) -> bool:
    """Test the chat endpoint with a question"""
    chat_url = f"{base_url}/chat"
    
    payload = {
        "question": question,
        "session_id": "test-session-123"
    }
    
    try:
        print(f"🔍 Testing chat endpoint: {chat_url}")
        print(f"💬 Question: {question}")
        
        response = requests.post(
            chat_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60  # Longer timeout for AI processing
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Chat response received:")
            print(f"📝 Response: {result.get('response', 'No response')[:200]}...")
            print(f"🆔 Session ID: {result.get('session_id', 'unknown')}")
            return True
        else:
            print(f"❌ Chat request failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Chat request error: {str(e)}")
        return False

def run_comprehensive_test(base_url: str) -> bool:
    """Run a comprehensive test suite"""
    print("🚀 AWS CloudOps Agent Lambda Test Suite")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Health check
    total_tests += 1
    if test_health_endpoint(base_url):
        tests_passed += 1
    
    print()
    
    # Test 2: Simple greeting
    total_tests += 1
    if test_chat_endpoint(base_url, "Hello, what can you help me with?"):
        tests_passed += 1
    
    print()
    
    # Test 3: AWS-specific question
    total_tests += 1
    if test_chat_endpoint(base_url, "What are the benefits of using Auto Scaling Groups?"):
        tests_passed += 1
    
    print()
    
    # Test results
    print("=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Your Lambda deployment is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please check your deployment.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test AWS CloudOps Agent Lambda deployment")
    parser.add_argument(
        "base_url", 
        help="Base URL of your API Gateway (e.g., https://abc123.execute-api.ap-southeast-1.amazonaws.com/prod)"
    )
    parser.add_argument(
        "--question", 
        default=None,
        help="Custom question to test (default: runs comprehensive test suite)"
    )
    parser.add_argument(
        "--health-only", 
        action="store_true",
        help="Only test the health endpoint"
    )
    
    args = parser.parse_args()
    
    # Ensure base URL doesn't end with slash
    base_url = args.base_url.rstrip('/')
    
    if args.health_only:
        success = test_health_endpoint(base_url)
    elif args.question:
        # Test health first, then custom question
        health_ok = test_health_endpoint(base_url)
        print()
        if health_ok:
            success = test_chat_endpoint(base_url, args.question)
        else:
            success = False
    else:
        # Run comprehensive test suite
        success = run_comprehensive_test(base_url)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()