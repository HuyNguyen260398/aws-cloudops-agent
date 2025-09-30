"""
Simple test Lambda handler to verify deployment works
"""
import json

def lambda_handler(event, context):
    """
    Simple test handler
    """
    try:
        message = event.get('message', 'Hello from AWS CloudOps Agent!')
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'response': f"✅ AWS CloudOps Agent deployed successfully! Your message: {message}",
                'timestamp': str(context.aws_request_id) if context else 'test',
                'status': 'deployed'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': f'Error: {str(e)}'
            })
        }