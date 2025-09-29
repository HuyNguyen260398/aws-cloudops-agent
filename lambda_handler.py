"""
AWS CloudOps Agent Lambda Handler
Serverless deployment for the AWS CloudOps Agent
"""
import json
import logging
from typing import Dict, Any
from src.minimal_lambda_aws_cloudops_agent import MinimalLambdaAwsCloudOpsAgent

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global agent instance for container reuse
agent = None

def initialize_agent():
    """Initialize the agent if not already initialized"""
    global agent
    if agent is None:
        try:
            agent = MinimalLambdaAwsCloudOpsAgent()
            logger.info("AWS CloudOps Agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {str(e)}")
            raise e
    return agent

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for AWS CloudOps Agent
    
    Expected event format:
    {
        "question": "Your AWS question here",
        "session_id": "optional-session-identifier"
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "response": "Agent response",
            "session_id": "session-identifier"
        }
    }
    """
    try:
        # Initialize agent
        cloudops_agent = initialize_agent()
        
        # Parse the event
        if isinstance(event.get('body'), str):
            # API Gateway format
            body = json.loads(event['body'])
        else:
            # Direct invocation format
            body = event
        
        question = body.get('question', '')
        session_id = body.get('session_id', context.aws_request_id)
        
        if not question:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required field: question',
                    'session_id': session_id
                })
            }
        
        logger.info(f"Processing question for session {session_id}: {question[:100]}...")
        
        # Get response from agent
        response = cloudops_agent.chat(question)
        
        logger.info(f"Generated response for session {session_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'response': response,
                'session_id': session_id,
                'timestamp': context.aws_request_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}',
                'session_id': body.get('session_id', context.aws_request_id) if 'body' in locals() else context.aws_request_id
            })
        }

def health_check_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Simple health check handler
    """
    try:
        # Try to initialize agent to verify all dependencies are working
        initialize_agent()
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'status': 'healthy',
                'message': 'AWS CloudOps Agent is running',
                'timestamp': context.aws_request_id
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': context.aws_request_id
            })
        }