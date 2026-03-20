import os

import aws_cdk as cdk
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_ssm as ssm
from aws_cdk.aws_bedrock_agentcore_alpha import (
    AgentRuntimeArtifact,
    ProtocolType,
    Runtime,
    RuntimeAuthorizerConfiguration,
    RuntimeNetworkConfiguration,
)
from cdk_ecr_deployment import DockerImageName, ECRDeployment
from constructs import Construct

from ..utils import to_kebab_case, to_snake_case
from .cognito import UserPoolConstruct


class RuntimeConstruct(Construct):
    """AgentCore runtime with execution role, ECR repository, container artifact, and SSM ARN parameter.

    Optionally configures X-Ray observability using CloudWatch Logs delivery.

    Example:
        runtime = RuntimeConstruct(
            self, "AgentRuntime",
            runtime_name="agent",
            asset_path="src/agent",
            protocol=ProtocolType.MCP,
            auth_pool=user_pool,
            environment_variables={"MEMORY_ID": memory.memory_id},
            enable_observability=True
        )
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        runtime_name: str,
        asset_path: str,
        protocol: ProtocolType,
        auth_pool: UserPoolConstruct,
        environment_variables: dict[str, str] | None = None,
        enable_observability: bool = False,
        model_id: str | None = None,
    ) -> None:
        """Create an AgentCore runtime with container deployment.

        Args:
            scope: CDK construct scope
            id: Construct ID
            runtime_name: Name for the runtime (will be prefixed with stack name)
            asset_path: Path to Docker context directory
            protocol: Protocol type (MCP, HTTP, or A2A)
            auth_pool: Cognito user pool for JWT authorisation
            environment_variables: Environment variables for the container
            enable_observability: Enable X-Ray tracing via CloudWatch Logs delivery
            model_id: Optional Bedrock model ID to grant invocation permissions for

        Example:
            RuntimeConstruct(
                self, "CalculatorRuntime",
                runtime_name="calculator",
                asset_path="src/mcp/calculator",
                protocol=ProtocolType.MCP,
                auth_pool=user_pool,
                model_id="au.anthropic.claude-sonnet-4-5-20250929-v1:0"
            )
        """
        super().__init__(scope, id)

        stack = cdk.Stack.of(self)
        stack_prefix = to_kebab_case(stack.stack_name)

        ssm_prefix = f"/{stack_prefix}"
        # Derive SSM key from construct id: "AgentRuntime" -> "agent-runtime-arn"
        ssm_param_key = f"{to_kebab_case(id)}-arn"

        # Runtime names only allow letters, numbers, and underscores - use snake_case
        prefixed_runtime_name = f"{to_snake_case(stack.stack_name)}_{to_snake_case(runtime_name)}"

        # Create a named ECR repository for this runtime
        repo_name = f"{stack_prefix}-{to_kebab_case(runtime_name)}"
        self._ecr_repo = ecr.Repository(
            self,
            "EcrRepo",
            repository_name=repo_name,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            empty_on_delete=True,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=5)],
        )

        # Build the Docker image (pushed to CDK bootstrap ECR during synth/deploy)
        # __file__ is src/cdk/constructs/runtime.py - ../.. resolves to src/
        # Build context is src/ to allow access to common/ shared utilities
        src_dir = os.path.join(os.path.dirname(__file__), "..", "..")
        docker_asset = ecr_assets.DockerImageAsset(
            self,
            "DockerAsset",
            directory=src_dir,
            file=os.path.join(asset_path, "Dockerfile"),
        )

        # Copy the built image into our named ECR repository
        image_deployment = ECRDeployment(
            self,
            "ImageDeployment",
            src=DockerImageName(docker_asset.image_uri),
            dest=DockerImageName(f"{self._ecr_repo.repository_uri}:{docker_asset.image_tag}"),
        )

        image_uri = f"{self._ecr_repo.repository_uri}:{docker_asset.image_tag}"
        artifact = AgentRuntimeArtifact.from_image_uri(image_uri)

        # Cognito authorizer uses the user pool discovery URL and client IDs
        cognito_discovery_url = (
            f"https://cognito-idp.{stack.region}.amazonaws.com"
            f"/{auth_pool.user_pool.user_pool_id}"
            "/.well-known/openid-configuration"
        )
        authorizer = RuntimeAuthorizerConfiguration.using_jwt(
            discovery_url=cognito_discovery_url,
            allowed_clients=[auth_pool.client.user_pool_client_id],
        )

        # Create the runtime
        self._runtime = Runtime(
            self,
            "Runtime",
            runtime_name=prefixed_runtime_name,
            agent_runtime_artifact=artifact,
            authorizer_configuration=authorizer,
            protocol_configuration=protocol,
            network_configuration=RuntimeNetworkConfiguration.using_public_network(),
            environment_variables=environment_variables or {},
            description=f"Runtime for {runtime_name}",
        )

        # Ensure the image is copied into our ECR repo before the Runtime is created
        self._runtime.node.add_dependency(image_deployment)

        # Grant the runtime execution role permission to pull from our ECR repo
        self._ecr_repo.grant_pull(self._runtime.role)

        # Add SSM/Secrets Manager permissions to the execution role
        self._runtime.role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{stack.region}:{stack.account}:parameter{ssm_prefix}/*"],
            )
        )
        self._runtime.role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{stack.region}:{stack.account}:secret:{stack_prefix}/*"
                ],
            )
        )

        # Extract runtime ARN and name from the L2 construct
        self._runtime_arn = self._runtime.agent_runtime_arn
        self._runtime_name = prefixed_runtime_name

        # Configure X-Ray observability if enabled
        if enable_observability:
            delivery_source = logs.CfnDeliverySource(
                self,
                "ObservabilitySource",
                name=f"{prefixed_runtime_name}_traces",
                log_type="TRACES",
                resource_arn=self._runtime_arn,
            )

            delivery_destination = logs.CfnDeliveryDestination(
                self,
                "ObservabilityDestination",
                name=f"{prefixed_runtime_name}_xray",
                delivery_destination_type="XRAY",
            )

            delivery = logs.CfnDelivery(
                self,
                "ObservabilityDelivery",
                delivery_source_name=delivery_source.name,
                delivery_destination_arn=delivery_destination.attr_arn,
            )
            delivery.add_dependency(delivery_source)
            delivery.add_dependency(delivery_destination)

        ssm.StringParameter(
            self,
            "ArnParam",
            parameter_name=f"{ssm_prefix}/{ssm_param_key}",
            string_value=self._runtime_arn,
        )

        # Build the MCP invocation endpoint with URL-encoded ARN
        if protocol == ProtocolType.MCP:
            escaped_arn = cdk.Fn.join(
                "%2F",
                cdk.Fn.split(
                    "/",
                    cdk.Fn.join(
                        "%3A",
                        cdk.Fn.split(":", self._runtime_arn),
                    ),
                ),
            )
            self._endpoint = f"https://bedrock-agentcore.{stack.region}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"
        else:
            self._endpoint = None

        # Grant Bedrock invocation permissions if model_id provided
        if model_id:
            # Cross-region inference profiles route across regions,
            # so foundation model resource uses wildcard region
            self._runtime.role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                        "bedrock:GetInferenceProfile",
                    ],
                    resources=[
                        "arn:aws:bedrock:*::foundation-model/*",
                        f"arn:aws:bedrock:{stack.region}:{stack.account}:inference-profile/*",
                    ],
                )
            )

    @property
    def runtime(self) -> Runtime:
        """The AgentCore runtime.

        Returns:
            The Runtime construct
        """
        return self._runtime

    @property
    def agent_runtime_arn(self) -> str:
        """The runtime ARN.

        Returns:
            The runtime ARN string
        """
        return self._runtime_arn

    @property
    def agent_runtime_name(self) -> str:
        """The runtime name.

        Returns:
            The runtime name string
        """
        return self._runtime_name

    @property
    def endpoint(self) -> str | None:
        """MCP invocation endpoint (only available for MCP protocol runtimes).

        Returns:
            HTTPS invocation URL with URL-encoded ARN, or None for non-MCP protocols
        """
        return self._endpoint

    @property
    def role(self) -> iam.IRole:
        """The runtime execution IAM role.

        Returns:
            IAM Role with permissions for Bedrock, SSM, and Secrets Manager
        """
        return self._runtime.role

    @property
    def ecr_repository(self) -> ecr.Repository:
        """The ECR repository for container images.

        Returns:
            ECR Repository with lifecycle policy (max 5 images)
        """
        return self._ecr_repo
