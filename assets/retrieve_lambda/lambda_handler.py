import os
import boto3
import json

# Lambda function to perform RAG query
def lambda_handler(event, context):
    kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
    region = os.environ.get('REGION')

    if not kb_id:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'KNOWLEDGE_BASE_ID not set.'})
        }

    # Parse query from API Gateway event
    try:
        body = json.loads(event.get('body', '{}'))
        query = body.get('query')
        max_results = body.get('max_results', 3)

        if not query:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Query parameter is required'})
            }
    except Exception as e:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Invalid request body: {str(e)}'})
        }

    client = boto3.client('bedrock-agent-runtime', region_name=region)

    try:
        # Call Bedrock Retrieve API
        response = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results
                }
            }
        )

        # Format results
        results = []
        for result in response.get('retrievalResults', []):
            results.append({
                'content': result['content']['text'],
                'score': result.get('score', 0),
                'location': result.get('location', {}),
                'metadata': result.get('metadata', {})
            })

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'query': query,
                'results': results,
                'count': len(results)
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': str(e)
            })
        }
