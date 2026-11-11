import os
import boto3
import json

# Lambda function to trigger indexing for Bedrock Knowledge Base
# Supports both direct invocation and S3 event triggers
def lambda_handler(event, context):
    kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
    region = os.environ.get('BEDROCK_REGION', "ap-southeast-2")

    if not kb_id:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'KNOWLEDGE_BASE_ID not set.'})
        }

    # Log the event for debugging
    print(f"Received event: {json.dumps(event)}")

    # Detect if this is an S3 event or direct invocation
    trigger_source = 'direct'
    uploaded_files = []

    if 'Records' in event:
        # S3 Event notification
        trigger_source = 's3_event'
        for record in event['Records']:
            if 's3' in record:
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']
                uploaded_files.append(f"s3://{bucket}/{key}")
        print(f"Triggered by S3 upload: {uploaded_files}")



    try:
        client = boto3.client('bedrock-agent', region_name=region)
        print("Bedrock client created successfully")
        
        # Get the first Data Source from the Knowledge Base
        print(f"Listing data sources for KB: {kb_id}")
        try:
            data_sources = client.list_data_sources(knowledgeBaseId=kb_id)
            print(f"Found {len(data_sources['dataSourceSummaries'])} data sources")
        except Exception as e:
            print(f"ERROR calling list_data_sources: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            raise e
        if not data_sources['dataSourceSummaries']:
            print("ERROR: No data sources found for Knowledge Base")
            raise Exception("No data sources found for Knowledge Base")

        data_source_id = data_sources['dataSourceSummaries'][0]['dataSourceId']

        # Start Ingestion Job
        response = client.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id
        )

        ingestion_job_id = response['ingestionJob']['ingestionJobId']

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Ingestion job started for KB {kb_id}',
                'triggerSource': trigger_source,
                'uploadedFiles': uploaded_files if uploaded_files else 'N/A',
                'knowledgeBaseId': kb_id,
                'dataSourceId': data_source_id,
                'ingestionJobId': ingestion_job_id
            })
        }
    except Exception as e:
        print(f"Error starting ingestion: {str(e)}")
        raise e
        # return {
        #     'statusCode': 500,
        #     'body': json.dumps({
        #         'error': str(e),
        #         'triggerSource': trigger_source,
        #         'uploadedFiles': uploaded_files if uploaded_files else 'N/A'
        #     })
        # }