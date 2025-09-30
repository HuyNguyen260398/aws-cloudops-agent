"""
AWS Lambda handler for the CloudOps Agent
"""
import json
import os
import sys
from typing import Dict, Any

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lambda_aws_cloudops_agent import LambdaAwsCloudOpsAgent

# Initialize the agent once (outside the handler for better performance)
agent = None

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function
    
    Expected event format:
    {
        "message": "Your AWS question here",
        "aws_profile": "default" (optional)
    }
    """
    global agent
    
    try:
        # Initialize agent if not already done
        if agent is None:
            aws_profile = event.get('aws_profile', 'default')
            agent = LambdaAwsCloudOpsAgent(aws_profile=aws_profile)
        
        # Extract message from event
        message = event.get('message', '')
        if not message:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'error': 'Missing required field: message'
                })
            }
        
        # Process the message
        response = agent.chat(message)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'response': response,
                'message': message
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}'
            })
        }

def api_gateway_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    API Gateway specific handler that handles HTTP requests
    """
    try:
        # Parse the request body
        if 'body' in event:
            body = json.loads(event['body']) if event['body'] else {}
        else:
            body = event
        
        # Call the main lambda handler
        result = lambda_handler(body, context)
        
        # Ensure CORS headers are included
        result['headers'].update({
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS'
        })
        
        return result
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'API Gateway handler error: {str(e)}'
            })
        }