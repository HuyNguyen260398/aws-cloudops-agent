"""
RAG System using AWS DynamoDB for knowledge storage and retrieval
"""
import boto3
import json
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import numpy as np

class DynamoRAG:
    def __init__(self, table_name: str = "aws-cloudops-knowledge", aws_profile: str = "default"):
        self.table_name = table_name
        self.session = boto3.Session(profile_name=aws_profile)
        self.dynamodb = self.session.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
    def create_table(self):
        """Create DynamoDB table for knowledge storage"""
        try:
            self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
                AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
                BillingMode='PAY_PER_REQUEST'
            )
            print(f"✅ Created table: {self.table_name}")
        except Exception as e:
            if "already exists" in str(e):
                print(f"📋 Table {self.table_name} already exists")
            else:
                raise e
    
    def add_knowledge(self, content: str, category: str = "general", metadata: Dict = None):
        """Add knowledge to DynamoDB with embeddings"""
        embedding = self.encoder.encode(content).tolist()
        
        item = {
            'id': f"{category}_{hash(content)}",
            'content': content,
            'category': category,
            'embedding': embedding,
            'metadata': metadata or {}
        }
        
        self.table.put_item(Item=item)
    
    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search for relevant knowledge using semantic similarity"""
        query_embedding = self.encoder.encode(query)
        
        # Scan table (for production, use vector database like OpenSearch)
        response = self.table.scan()
        items = response['Items']
        
        # Calculate similarities
        similarities = []
        for item in items:
            item_embedding = np.array(item['embedding'])
            similarity = np.dot(query_embedding, item_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(item_embedding)
            )
            similarities.append((similarity, item))
        
        # Return top-k most similar items
        similarities.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in similarities[:top_k]]
    
    def get_context(self, query: str) -> str:
        """Get formatted context for the query"""
        results = self.search(query)
        if not results:
            return ""
        
        context = "📚 Relevant Knowledge:\n"
        for i, item in enumerate(results, 1):
            context += f"{i}. {item['content']}\n"
        
        return context