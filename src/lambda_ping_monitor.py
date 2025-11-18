
import socket
import boto3
from datetime import datetime

def lambda_handler(event, context):
    domain = "nghuy.link"
    
    try:
        # Test DNS resolution and connectivity
        socket.gethostbyname(domain)
        print(f"{domain} is reachable at {datetime.now()}")
        return {"statusCode": 200, "body": f"{domain} is healthy"}
        
    except socket.gaierror:
        # Domain unreachable - send email alert
        message = f"ALERT: {domain} is unreachable at {datetime.now()}"
        print(message)
        
        # Send SNS notification
        sns = boto3.client('sns')
        try:
            sns.publish(
                TopicArn='arn:aws:sns:us-east-1:ACCOUNT_ID:domain-alerts',
                Subject=f"Domain Alert: {domain} Down",
                Message=message
            )
            print("Email alert sent")
        except Exception as e:
            print(f"Failed to send email: {e}")
        
        return {"statusCode": 500, "body": message}