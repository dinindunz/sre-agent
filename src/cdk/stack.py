import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_ssm as ssm

# TODO: Refactor to use aws_cdk once L2 constructs are available.
from aws_cdk.aws_bedrock_agentcore_alpha import ProtocolType
from constructs import Construct

from .config import SREAgentConfig
from .constructs import (
    DockerLambdaConstruct,
    RuntimeConstruct,
    UserPoolConstruct,
)
from .utils import DestroyLogGroups, to_kebab_case


class SREAgentStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: SREAgentConfig,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Store configuration for use throughout the stack
        self.config = config

        stack_prefix = to_kebab_case(self.stack_name)

        # Ensure all log groups in this stack are cleaned up on deletion
        cdk.Aspects.of(self).add(DestroyLogGroups())

        # ---------------------------------------------------------------
        # Cognito User Pools
        # ---------------------------------------------------------------

        # Agent Runtime User Pool - used for authentication to invoke the agent runtime.
        agent_auth = UserPoolConstruct(
            self,
            "AgentUserPool",
            name="agent",
            scope_description="Invoke agent runtime",
            access_token_validity=cdk.Duration.minutes(
                config.cognito.access_token_validity_minutes
            ),
        )

        # ---------------------------------------------------------------
        # AgentCore Runtime
        # ---------------------------------------------------------------

        # Placeholder secret - update with Jira API credentials after deployment
        jira_api_secret = secretsmanager.Secret(
            self,
            "JiraApiSecret",
            secret_name=f"{stack_prefix}/jira-api",
            description="Jira API credentials for the SRE agent to post comments",
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        agent_env_vars = {
            "REGION_NAME": self.region,
            "LOG_LEVEL": config.agent_runtime.log_level,
            "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED": str(
                config.agent_runtime.otel_logging_enabled
            ).lower(),
            "MODEL_ID": config.model.model_id,
            "MODEL_TEMPERATURE": str(config.model.model_temperature),
            "MODEL_MAX_TOKENS": str(config.model.model_max_tokens),
            "THINKING_BUDGET_TOKENS": str(config.model.thinking_budget_tokens),
            # OAuth token cache configuration
            "OAUTH_CACHE_BUFFER_PERCENT": str(config.cognito.oauth_cache.buffer_percent),
            "OAUTH_CACHE_BUFFER_MIN_SEC": str(config.cognito.oauth_cache.buffer_min_seconds),
            "OAUTH_CACHE_BUFFER_MAX_SEC": str(config.cognito.oauth_cache.buffer_max_seconds),
            # Jira API
            "JIRA_SECRET_NAME": jira_api_secret.secret_name,
        }

        agent_runtime = RuntimeConstruct(
            self,
            "AgentRuntime",
            runtime_name="agent",
            asset_path="agent",
            protocol=ProtocolType.HTTP,
            auth_pool=agent_auth,
            environment_variables=agent_env_vars,
            enable_observability=config.observability.enabled,
            model_id=config.model.model_id,
        )

        # Grant agent runtime permission to query CloudWatch Logs
        agent_runtime.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:DescribeLogGroups",
                    "logs:StartQuery",
                    "logs:GetQueryResults",
                ],
                resources=["*"],
            )
        )

        # ---------------------------------------------------------------
        # Jira Webhook - API Gateway + Lambda
        # ---------------------------------------------------------------

        # Placeholder secret - update with your Jira webhook shared secret after deployment
        jira_secret = secretsmanager.Secret(
            self,
            "JiraWebhookSecret",
            secret_name=f"{stack_prefix}/jira-webhook-secret",
            description="Jira webhook shared secret for HMAC-SHA256 signature validation",
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # Docker Lambda - ECR repo + image pipeline encapsulated in the construct
        jira_webhook = DockerLambdaConstruct(
            self,
            "JiraWebhook",
            function_name="jira-webhook",
            asset_path="jira_webhook",
            timeout=cdk.Duration.seconds(60),
            memory_size=256,
            environment={
                "REGION_NAME": self.region,
                "LOG_LEVEL": config.agent_runtime.log_level,
                "AGENT_RUNTIME_SSM_PARAM": f"/{stack_prefix}/agent-runtime-arn",
                "AGENT_COGNITO_SECRET_NAME": agent_auth.secret_name,
                "JIRA_SECRET_NAME": jira_secret.secret_name,
            },
        )

        # Grant Lambda read access to the secrets and SSM parameter it needs
        jira_secret.grant_read(jira_webhook.function)
        jira_webhook.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:{stack_prefix}/*"
                ],
            )
        )
        jira_webhook.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/{stack_prefix}/*"],
            )
        )
        jira_webhook.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cognito-idp:ListUsers"],
                resources=[agent_auth.user_pool.user_pool_arn],
            )
        )

        # API Gateway - receives Jira webhook POST requests.
        # Lambda proxy integration passes headers and body automatically.
        # The Lambda validates the signature, fires the AgentCore call with
        # stream=True (no body wait), and returns 202 to Jira.
        jira_api = apigateway.RestApi(
            self,
            "JiraWebhookApi",
            rest_api_name=f"{stack_prefix}-jira-webhook",
            description="Receives Jira webhook events and forwards to the SRE Agent",
            deploy_options=apigateway.StageOptions(stage_name="v1"),
        )

        webhook_resource = jira_api.root.add_resource("webhook")
        webhook_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(jira_webhook.function, proxy=True),
        )

        # Publish the webhook URL to SSM for easy retrieval
        ssm.StringParameter(
            self,
            "JiraWebhookUrlParam",
            parameter_name=f"/{stack_prefix}/jira-webhook-url",
            string_value=f"{jira_api.url}webhook",
            description="Jira webhook endpoint URL - configure this in your Jira project settings",
        )

        cdk.CfnOutput(
            self,
            "JiraWebhookUrl",
            value=f"{jira_api.url}webhook",
            description="Configure this URL in your Jira project webhook settings",
        )
