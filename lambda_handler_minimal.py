"""
AWS CloudOps Agent - Ultra Minimal Lambda Handler
Basic AWS operations without AI dependencies for testing
"""
import json
import logging
import boto3
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Ultra minimal Lambda handler for AWS CloudOps Agent
    """
    try:
        logger.info("Processing request")
        
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
        
        logger.info(f"Processing question: {question[:100]}...")
        
        # Basic AWS operations response
        try:
            ec2 = boto3.client('ec2')
            response = f"Hello! I'm the AWS CloudOps Agent. You asked: '{question}'. I can help with AWS operations. For example, you have access to AWS EC2 in region: {ec2.meta.region_name}"
        except Exception as e:
            response = f"Hello! I'm the AWS CloudOps Agent. You asked: '{question}'. I'm a basic version without AI capabilities, but I can perform AWS operations using boto3."
        
        logger.info("Generated response successfully")
        
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
                'timestamp': context.aws_request_id,
                'note': 'This is a basic version without AI capabilities. For full AI features, consider using larger instance types or container deployments.'
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
        logger.info("Health check requested")
        
        # Basic AWS connectivity test
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            account = identity.get('Account', 'unknown')
            health_status = 'healthy'
            details = f'AWS connected, Account: {account}'
        except Exception as e:
            health_status = 'degraded'
            details = f'AWS connection issue: {str(e)}'
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'status': health_status,
                'message': 'AWS CloudOps Agent (Basic Version)',
                'details': details,
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