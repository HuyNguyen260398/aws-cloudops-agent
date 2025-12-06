"""
Knowledge Base Retrieval Tool for AWS CloudOps Agent
Integrates Bedrock Knowledge Base retrieval capabilities
"""
import os
import boto3
from strands import tool
from typing import Optional
import utils.mylogger as mylogger

logger = mylogger.get_logger()


@tool(
    name="retrieve_from_knowledge_base",
    description="""Retrieve relevant documents from the AWS Bedrock Knowledge Base.
    Use this tool when you need to search for information in stored documentation,
    company knowledge, technical guides, or any other documents that have been ingested
    into the knowledge base. This is useful for answering questions based on specific
    documentation rather than general AWS knowledge."""
)
def retrieve_from_knowledge_base(
    query: str,
    max_results: int = 3
) -> str:
    """
    Retrieve relevant documents from Bedrock Knowledge Base

    Args:
        query: The search query to find relevant documents
        max_results: Maximum number of results to return (default: 3, max: 10)

    Returns:
        Formatted string containing retrieved documents with scores and sources
    """
    try:
        # Get configuration from environment
        kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
        region = os.environ.get('BEDROCK_REGION', 'ap-southeast-2')

        if not kb_id:
            logger.error("❌ KNOWLEDGE_BASE_ID environment variable not set")
            return "Error: Knowledge Base ID not configured. Please set KNOWLEDGE_BASE_ID environment variable."

        # Validate max_results
        max_results = min(max(1, max_results), 10)

        logger.info(f"🔍 Retrieving from KB: {kb_id} in {region}")
        logger.info(f"   Query: {query}")
        logger.info(f"   Max results: {max_results}")

        # Initialize Bedrock Agent Runtime client
        client = boto3.client('bedrock-agent-runtime', region_name=region)

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

        # Parse results
        retrieval_results = response.get('retrievalResults', [])

        if not retrieval_results:
            logger.info("ℹ️ No documents found matching the query")
            return f"No relevant documents found for query: '{query}'"

        logger.info(f"✅ Found {len(retrieval_results)} relevant documents")

        # Format results
        formatted_results = []
        formatted_results.append(f"📚 Retrieved {len(retrieval_results)} documents for: '{query}'\n")
        formatted_results.append("=" * 80)

        for idx, result in enumerate(retrieval_results, 1):
            content = result.get('content', {}).get('text', 'No content')
            score = result.get('score', 0)
            location = result.get('location', {})
            metadata = result.get('metadata', {})

            formatted_results.append(f"\n📄 Document {idx} (Relevance Score: {score:.4f})")
            formatted_results.append("-" * 80)

            # Add source information if available
            if location:
                s3_location = location.get('s3Location', {})
                if s3_location:
                    uri = s3_location.get('uri', '')
                    formatted_results.append(f"📍 Source: s3://{uri}")

            # Add metadata if available
            if metadata:
                formatted_results.append(f"🏷️  Metadata: {metadata}")

            # Add content
            formatted_results.append(f"\n📝 Content:\n{content}")
            formatted_results.append("")

        result_text = "\n".join(formatted_results)
        logger.info(f"✅ KB retrieval completed successfully")
        return result_text

    except Exception as e:
        error_msg = f"❌ Knowledge Base retrieval failed: {str(e)}"
        logger.error(error_msg)
        return f"Error retrieving from Knowledge Base: {str(e)}"


# Optional: Add a simplified version for quick lookups
@tool(
    name="quick_kb_search",
    description="Quickly search the Knowledge Base for a specific term or concept. Returns top result only."
)
def quick_kb_search(query: str) -> str:
    """
    Quick search in Knowledge Base - returns only the top result

    Args:
        query: The search query

    Returns:
        Top matching document content
    """
    try:
        kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
        region = os.environ.get('BEDROCK_REGION', 'ap-southeast-2')

        if not kb_id:
            return "Error: Knowledge Base ID not configured."

        logger.info(f"🔍 Quick KB search: {query}")

        client = boto3.client('bedrock-agent-runtime', region_name=region)

        response = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 1
                }
            }
        )

        results = response.get('retrievalResults', [])

        if not results:
            return f"No documents found for: '{query}'"

        top_result = results[0]
        content = top_result.get('content', {}).get('text', 'No content')
        score = top_result.get('score', 0)

        return f"📄 Top result (score: {score:.4f}):\n\n{content}"

    except Exception as e:
        logger.error(f"❌ Quick KB search failed: {str(e)}")
        return f"Error: {str(e)}"
