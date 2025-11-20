resource "aws_opensearchserverless_security_policy" "encryption_policy" {
  name = "${var.project}-encrypt-policy"
  type = "encryption"
  
  # Using key default of AWS (AWSOwnedKey)
  policy = jsonencode({
    "Rules" : [
      {
        "ResourceType" : "collection",
        "Resource" : ["collection/${var.project}-kb-collection"] #static name
      }
    ],
    "AWSOwnedKey" : true
  })
}

resource "aws_opensearchserverless_security_policy" "network_policy" {
  name = "${var.project}-network-policy"
  type = "network"

  policy = jsonencode([
    {
      "Rules" : [
        {
          "ResourceType" : "collection",
          "Resource" : ["collection/${var.project}-kb-collection"]
        }
      ],
      "AllowFromPublic" : true
    }
  ])
}

# 3. OpenSearch Serverless Collection
resource "aws_opensearchserverless_collection" "rag_collection" {
  name = "${var.project}-kb-collection"
  type = "VECTORSEARCH"

  depends_on = [
    aws_opensearchserverless_security_policy.encryption_policy,
    aws_opensearchserverless_security_policy.network_policy
  ]
}

# 4. Access Policy
resource "aws_opensearchserverless_access_policy" "rag_data_access" {
  name = "${var.project}-kb-access"
  type = "data"

  policy = jsonencode([
    {
      Rules = [
        {
          Resource = [
            "collection/${var.project}-kb-collection"
          ]
          Permission = [
            "aoss:*"
          ]
          ResourceType = "collection"
        },
        {
          Resource = [
            "index/${var.project}-kb-collection/*"
          ]
          Permission = [
            "aoss:*"
          ]
          ResourceType = "index"
        }
      ]
      Principal = [
        aws_iam_role.kb_service_role.arn,
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
      ]
    }
  ])

  depends_on = [
    aws_opensearchserverless_collection.rag_collection,
    aws_iam_role.kb_service_role
  ]
}

# 5. Create OpenSearch Index
resource "null_resource" "create_index" {
  provisioner "local-exec" {
    command = <<-EOF
      set -e

      # Install opensearch-py and dependencies
      pip3 install --quiet --user opensearch-py boto3 requests requests-aws4auth

      # Wait for collection and access policies to be active and propagated
      echo "Waiting for OpenSearch collection and access policies to be fully active..."
      sleep 60

      python3 << 'PYTHON_SCRIPT'
import boto3
import time
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

region = '${var.region}'
host = '${aws_opensearchserverless_collection.rag_collection.collection_endpoint}'
host = host.replace('https://', '')

print(f"Connecting to OpenSearch at: {host}")

# Get AWS credentials
credentials = boto3.Session().get_credentials()
sts_client = boto3.client('sts', region_name=region)
caller_identity = sts_client.get_caller_identity()
print(f"Caller Identity ARN: {caller_identity['Arn']}")

awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    region,
    'aoss',
    session_token=credentials.token
)

# Retry logic for connection
max_retries = 3
retry_delay = 30

for attempt in range(max_retries):
    try:
        client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=300
        )

        index_name = 'rag-agent-index'

        # Check if index exists
        if client.indices.exists(index=index_name):
            print(f'Index {index_name} already exists')
            break

        # Create index
        index_body = {
            'settings': {
                'index': {
                    'knn': True,
                    'knn.algo_param.ef_search': 512
                }
            },
            'mappings': {
                'properties': {
                    'vector': {
                        'type': 'knn_vector',
                        'dimension': 1024,
                        'method': {
                            'name': 'hnsw',
                            'engine': 'faiss',
                            'parameters': {
                                'ef_construction': 512,
                                'm': 16
                            }
                        }
                    },
                    'text': {'type': 'text'},
                    'metadata': {'type': 'text'}
                }
            }
        }

        client.indices.create(index=index_name, body=index_body)
        print(f'Index {index_name} created successfully')
        break

    except Exception as e:
        if attempt < max_retries - 1:
            print(f'Attempt {attempt + 1} failed: {str(e)}')
            print(f'Waiting {retry_delay} seconds before retry...')
            time.sleep(retry_delay)
        else:
            print(f'Error after {max_retries} attempts: {str(e)}')
            raise
PYTHON_SCRIPT
    EOF
  }

  depends_on = [
    aws_opensearchserverless_collection.rag_collection,
    aws_opensearchserverless_access_policy.rag_data_access
  ]
}