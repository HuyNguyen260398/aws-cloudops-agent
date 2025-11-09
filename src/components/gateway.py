import json
import time
import requests
from typing import Dict, List, Optional, Union
import boto3
from botocore.exceptions import ClientError
from mcp.types import Tool as MCPTool
from strands.tools.mcp.mcp_client import MCPAgentTool

LAMBDA_EXECUTION_ROLE_POLICY = (
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)
LAMBDA_RUNTIME = "python3.12"
LAMBDA_HANDLER = "lambda_function_code.lambda_handler"
LAMBDA_PACKAGE_TYPE = "Zip"

IAM_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

# AgentCore Gateway IAM Role constants
GATEWAY_AGENTCORE_ROLE_NAME = "GatewaySearchAgentCoreRole"

GATEWAY_AGENTCORE_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

GATEWAY_AGENTCORE_POLICY_NAME = "BedrockAgentPolicy"


def _format_error_message(error: ClientError) -> str:
    """Format error message from ClientError."""
    return f"{error.response['Error']['Code']}-{error.response['Error']['Message']}"


def create_gateway_iam_role(
    lambda_arns: List[str],
    role_name: str = GATEWAY_AGENTCORE_ROLE_NAME,
    policy_name: str = GATEWAY_AGENTCORE_POLICY_NAME,
) -> Optional[str]:
    """Create IAM role for AgentCore Gateway with Lambda invoke permissions.

    Args:
        lambda_arns: List of Lambda function ARNs to grant invoke permissions
        role_name: Name for the IAM role
        policy_name: Name for the inline policy

    Returns:
        Role ARN string or None if creation fails
    """
    session = boto3.Session()
    region = session.region_name

    iam_client = boto3.client("iam", region_name=region)

    try:
        # Create the IAM role
        print(f"Creating IAM role: {role_name}")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(GATEWAY_AGENTCORE_TRUST_POLICY),
            Description="IAM role for AgentCore Gateway to invoke Lambda functions",
        )
        role_arn = response["Role"]["Arn"]

        # Create the inline policy document
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "InvokeFunction",
                    "Effect": "Allow",
                    "Action": "lambda:InvokeFunction",
                    "Resource": lambda_arns,
                }
            ],
        }

        # Attach the inline policy
        print(f"Attaching policy: {policy_name}")
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
        )

        print(f"Gateway IAM role created successfully: {role_arn}")
        return role_arn

    except ClientError as error:
        if error.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"IAM role {role_name} already exists. Retrieving existing role...")
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]

            # Update the policy if role exists
            try:
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "InvokeFunction",
                            "Effect": "Allow",
                            "Action": "lambda:InvokeFunction",
                            "Resource": lambda_arns,
                        }
                    ],
                }

                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document),
                )
                print(f"Updated policy for existing role: {role_arn}")

            except ClientError as policy_error:
                print(
                    f"Warning: Could not update policy: {_format_error_message(policy_error)}"
                )

            return role_arn
        else:
            error_message = _format_error_message(error)
            print(f"Error creating IAM role: {error_message}")
            return None
    except Exception as error:
        print(f"Unexpected error creating IAM role: {str(error)}")
        return None


def _create_or_get_lambda_function(
    lambda_client, function_name: str, role_arn: str, code: bytes
) -> str:
    """Create Lambda function or return existing function ARN."""
    try:
        print("Creating lambda function")
        response = lambda_client.create_function(
            FunctionName=function_name,
            Role=role_arn,
            Runtime=LAMBDA_RUNTIME,
            Handler=LAMBDA_HANDLER,
            Code={"ZipFile": code},
            Description="Lambda function example for Bedrock AgentCore Gateway",
            PackageType=LAMBDA_PACKAGE_TYPE,
        )
        return response["FunctionArn"]

    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceConflictException":
            response = lambda_client.get_function(FunctionName=function_name)
            lambda_arn = response["Configuration"]["FunctionArn"]
            print(
                f"AWS Lambda function {function_name} already exists. Using the same ARN {lambda_arn}"
            )
            return lambda_arn
        else:
            raise error


def _create_or_get_iam_role(iam_client, role_name: str) -> str:
    """Create IAM role or return existing role ARN."""
    try:
        print("Creating IAM role for lambda function")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(IAM_TRUST_POLICY),
            Description="IAM role to be assumed by lambda function",
        )
        role_arn = response["Role"]["Arn"]

        print("Attaching policy to the IAM role")
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=LAMBDA_EXECUTION_ROLE_POLICY,
        )

        print(f"Role '{role_name}' created successfully: {role_arn}")
        return role_arn

    except ClientError as error:
        if error.response["Error"]["Code"] == "EntityAlreadyExists":
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            print(f"IAM role {role_name} already exists. Using the same ARN {role_arn}")
            return role_arn
        else:
            raise error


def create_gateway_lambda(
    lambda_function_code_path: str, lambda_function_name: str
) -> Dict[str, Union[str, int]]:
    """Create AWS Lambda function with IAM role for AgentCore Gateway.

    Args:
        lambda_function_code_path: Path to the Lambda function code zip file
        lambda_function_name: Name for the Lambda function

    Returns:
        Dictionary with 'lambda_function_arn' and 'exit_code' keys
    """
    session = boto3.Session()
    region = session.region_name

    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    role_name = f"{lambda_function_name}_lambda_iamrole"

    print("Reading code from zip file")
    with open(lambda_function_code_path, "rb") as f:
        lambda_function_code = f.read()

    try:
        role_arn = _create_or_get_iam_role(iam_client, role_name)
        time.sleep(20)
        try:
            lambda_arn = _create_or_get_lambda_function(
                lambda_client, lambda_function_name, role_arn, lambda_function_code
            )
        except ClientError:
            lambda_arn = _create_or_get_lambda_function(
                lambda_client, lambda_function_name, role_arn, lambda_function_code
            )

        return {"lambda_function_arn": lambda_arn, "exit_code": 0}

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"Error: {error_message}")
        return {"lambda_function_arn": error_message, "exit_code": 1}
    except Exception as error:
        print(f"Unexpected error: {str(error)}")
        return {"lambda_function_arn": str(error), "exit_code": 1}


def _get_current_client():
    session = boto3.Session()
    region = session.region_name
    return boto3.client("bedrock-agentcore-control", region_name=region)


def read_apispec(json_file_path):
    try:
        # read json file and return contents as string
        with open(json_file_path, "r") as file:
            # Parse JSON to Python object
            api_spec = json.load(file)
            return api_spec

    except FileNotFoundError:
        return f"Error: File {json_file_path} not found"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


def list_gateways():
    agentcore_client = _get_current_client()
    response = agentcore_client.list_gateways()
    print(json.dumps(response, indent=2, default=str))
    return response


def create_gateway(
    gateway_name,
    gateway_desc,
    gateway_role_arn,
    cognito_client_id,
    cognito_discovery_url,
):
    # Use Cognito for Inbound OAuth to our Gateway
    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [cognito_client_id],
            "discoveryUrl": cognito_discovery_url,
        }
    }

    # Enable semantic search of tools
    search_config = {
        "mcp": {"searchType": "SEMANTIC", "supportedVersions": ["2025-03-26"]}
    }

    # Create the gateway
    agentcore_client = _get_current_client()
    response = agentcore_client.create_gateway(
        name=gateway_name,
        roleArn=gateway_role_arn,
        authorizerType="CUSTOM_JWT",
        description=gateway_desc,
        protocolType="MCP",
        authorizerConfiguration=auth_config,
        protocolConfiguration=search_config,
    )

    # print(json.dumps(response, indent=2, default=str))
    return response["gatewayId"]


def create_gateway_target(gateway_id, target_name, target_descr, lambda_arn, api_spec):
    # Add a Lambda target to the gateway
    agentcore_client = _get_current_client()
    response = agentcore_client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name=target_name,
        description=target_descr,
        targetConfiguration={
            "mcp": {
                "lambda": {
                    "lambdaArn": lambda_arn,
                    "toolSchema": {"inlinePayload": api_spec},
                }
            }
        },
        # Use IAM as credential provider
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ],
    )
    return response["targetId"]


def get_gateway_endpoint(gateway_id):
    agentcore_client = _get_current_client()
    response = agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
    gateway_url = response["gatewayUrl"]
    return gateway_url


# Helper functions that use jsonrpc to invoke MCP tools or list them
def invoke_gateway_tool(gateway_endpoint, jwt_token, tool_params):
    requestBody = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": tool_params,
    }
    response = requests.post(
        gateway_endpoint,
        json=requestBody,
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        },
    )

    return response.json()


# Utility function for using MCP's `tools/list` method for listing the MCP tools available from Gateway
def get_all_agent_tools_from_mcp_endpoint(gateway_endpoint, jwt_token, client):
    more_tools = True
    tools_count = 0
    tools_list = []

    requestBody = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    next_cursor = ""

    while more_tools:
        if tools_count == 0:
            requestBody["params"] = {}
        else:
            print(f"\nGetting next page of tools since a next cursor was returned\n")
            requestBody["params"] = {"cursor": next_cursor}

        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        }

        print(f"\n\nListing tools for gateway {gateway_endpoint}")

        response = requests.post(gateway_endpoint, json=requestBody, headers=headers)

        tools_json = response.json()
        tools_count += len(tools_json["result"]["tools"])

        for tool in tools_json["result"]["tools"]:
            mcp_tool = MCPTool(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["inputSchema"],
            )
            mcp_agent_tool = MCPAgentTool(mcp_tool, client)
            short_descr = tool["description"][0:40] + "..."
            print(f"adding tool '{mcp_agent_tool.tool_name}' - {short_descr}")
            tools_list.append(mcp_agent_tool)

        if "nextCursor" in tools_json["result"]:
            next_cursor = tools_json["result"]["nextCursor"]
            more_tools = True
        else:
            more_tools = False

    print(f"\nTotal tools found: {tools_count}\n")
    return tools_list


# Using Strands Agents list_tools_sync() with pagination
def get_all_mcp_tools_from_mcp_client(client):
    more_tools = True
    tools = []
    pagination_token = None
    while more_tools:
        tmp_tools = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(tmp_tools)
        if tmp_tools.pagination_token is None:
            more_tools = False
        else:
            more_tools = True
            pagination_token = tmp_tools.pagination_token
    return tools


# Using the built-in Gateway semantic search tool
def tool_search(gateway_endpoint, jwt_token, query):
    toolParams = {
        "name": "x_amz_bedrock_agentcore_search",
        "arguments": {"query": query},
    }
    toolResp = invoke_gateway_tool(
        gateway_endpoint=gateway_endpoint, jwt_token=jwt_token, tool_params=toolParams
    )
    tools = toolResp["result"]["structuredContent"]["tools"]
    return tools
