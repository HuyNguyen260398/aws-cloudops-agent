import boto3
from botocore.exceptions import ClientError
from boto3.session import Session
import os
from typing import Optional

import utils.mylogger as mylogger

logger = mylogger.get_logger()

# Global variables for OAuth state
_oauth_initialized = False
_token_getter = None

# ============================================================================
# COGNITO JWT TOKEN HELPER
# ============================================================================


def setup_cognito_user_pool(pool_name, username, password, temp_password):
    boto_session = Session()
    region = boto_session.region_name
    # Initialize Cognito client
    cognito_client = boto3.client("cognito-idp", region_name=region)
    try:
        # Create User Pool
        user_pool_response = cognito_client.create_user_pool(
            PoolName=pool_name, Policies={"PasswordPolicy": {"MinimumLength": 8}}
        )
        pool_id = user_pool_response["UserPool"]["Id"]
        # Create App Client
        app_client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="MCPServerPoolClient",
            GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        )
        client_id = app_client_response["UserPoolClient"]["ClientId"]
        # Create User
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            TemporaryPassword=temp_password,
            MessageAction="SUPPRESS",
        )
        # Set Permanent Password
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id, Username=username, Password=password, Permanent=True
        )
        # Authenticate User and get Access Token
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
        bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
        refresh_token = auth_response["AuthenticationResult"]["RefreshToken"]
        # Output the required values
        print(f"Pool id: {pool_id}")
        print(
            f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        )
        print(f"Client ID: {client_id}")
        print(f"Bearer Token: {bearer_token}")
        print(f"Refresh Token: {refresh_token}")

        # Return values if needed for further processing
        return {
            "pool_id": pool_id,
            "client_id": client_id,
            "bearer_token": bearer_token,
            "refresh_token": refresh_token,
            "discovery_url": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration",
        }
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_cognito_jwt_token(username, password, client_id, region=None):
    """Get JWT access token from AWS Cognito"""
    if not region:
        boto_session = Session()
        region = boto_session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
        return response["AuthenticationResult"]["AccessToken"]
    except ClientError as e:
        logger.error(f"❌ Error getting Cognito token: {e}")
        return None


def get_m2m_token() -> Optional[str]:
    """Get Machine-to-Machine token from Cognito using environment variables or config"""
    global _oauth_initialized, _token_getter

    if _oauth_initialized and _token_getter:
        logger.info(
            "✅ Authentication already initialized. Using cached Cognito JWT token"
        )
        return _token_getter()

    try:
        # Try environment variables first
        username = os.getenv("COGNITO_USERNAME")
        password = os.getenv("COGNITO_PASSWORD")
        client_id = os.getenv("COGNITO_CLIENT_ID")

        # If not in env, try config
        if not all([username, password, client_id]):
            from utils.config_manager import AgentCoreConfigManager

            config_manager = AgentCoreConfigManager()
            auth_config = config_manager.get_basic_auth_settings()
            base_config = config_manager.get_base_settings()

            client_id = auth_config.get("client_id", "")
            region = base_config.get("aws", {}).get("region", "")

            # Username and password should be in environment for security
            if not username or not password:
                logger.warning("⚠️ Cognito credentials not found in environment")
                return None

        if not all([username, password, client_id]):
            logger.warning("⚠️ Missing Cognito configuration")
            return None

        token = get_cognito_jwt_token(username, password, client_id, region)
        if token:
            logger.info("✅ Successfully obtained Cognito JWT token")
        return token

    except Exception as e:
        logger.error(f"❌ Failed to get M2M token: {e}")
        return None


# ============================================================================
# OAUTH SETUP
# ============================================================================


def setup_oauth() -> bool:
    """Set up OAuth/Cognito authentication"""
    global _oauth_initialized, _token_getter

    if _oauth_initialized:
        return True
    try:
        token = get_m2m_token()
        if token:
            logger.info("✅ Cognito authentication configured")
            _oauth_initialized = True
            _token_getter = lambda: token
            return True
        logger.warning("⚠️ Cognito authentication not available")
        return False
    except Exception as e:
        logger.error(f"❌ OAuth setup failed: {e}")
        return False


def is_oauth_available():
    """
    Check if OAuth functionality is available.

    Returns:
        bool: True if OAuth is available and initialized
    """
    return _oauth_initialized and _token_getter is not None
