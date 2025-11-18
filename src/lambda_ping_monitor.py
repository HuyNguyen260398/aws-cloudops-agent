import socket
import boto3
import json
import os
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def send_teams_notification(domain, status, timestamp):
    """Send notification to Microsoft Teams channel via webhook"""
    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")

    if not webhook_url:
        print("TEAMS_WEBHOOK_URL environment variable not set")
        return False

    # Create message card for Teams
    message_card = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": "FF0000" if status == "down" else "00FF00",
        "summary": f"Domain Alert: {domain}",
        "sections": [
            {
                "activityTitle": f"🚨 Domain Alert: {domain}",
                "activitySubtitle": timestamp,
                "facts": [
                    {"name": "Domain:", "value": domain},
                    {"name": "Status:", "value": status.upper()},
                    {"name": "Timestamp:", "value": timestamp},
                ],
                "markdown": True,
            }
        ],
    }

    try:
        req = Request(
            webhook_url,
            data=json.dumps(message_card).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        response = urlopen(req)
        print(f"Teams notification sent: {response.read().decode()}")
        return True
    except HTTPError as e:
        print(f"Failed to send Teams notification - HTTP Error: {e.code} {e.reason}")
        return False
    except URLError as e:
        print(f"Failed to send Teams notification - URL Error: {e.reason}")
        return False
    except Exception as e:
        print(f"Failed to send Teams notification: {e}")
        return False


def lambda_handler(event, context):
    domain = "nghuy.link"
    timestamp = str(datetime.now())

    try:
        # Test DNS resolution and connectivity
        socket.gethostbyname(domain)
        print(f"{domain} is reachable at {timestamp}")
        return {"statusCode": 200, "body": f"{domain} is healthy"}

    except socket.gaierror:
        # Domain unreachable - send alerts
        message = f"ALERT: {domain} is unreachable at {timestamp}"
        print(message)

        # Send SNS notification
        sns = boto3.client("sns")
        try:
            sns.publish(
                TopicArn="arn:aws:sns:us-east-1:ACCOUNT_ID:domain-alerts",
                Subject=f"Domain Alert: {domain} Down",
                Message=message,
            )
            print("Email alert sent")
        except Exception as e:
            print(f"Failed to send email: {e}")

        # Send Teams notification
        send_teams_notification(domain, "down", timestamp)

        return {"statusCode": 500, "body": message}
