import os

import aws_cdk as cdk
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_lambda as lambda_
from cdk_ecr_deployment import DockerImageName, ECRDeployment
from constructs import Construct

from ..utils import to_kebab_case


class DockerLambdaConstruct(Construct):
    """Docker-based Lambda function with a named ECR repository.

    Handles the full image pipeline: builds the Docker image via CDK assets,
    copies it into a named ECR repository, and creates the Lambda function.

    The build context is always ``src/`` so that shared code under ``common/``
    is accessible to the Dockerfile.

    Example:
        fn = DockerLambdaConstruct(
            self, "JiraWebhook",
            function_name="jira-webhook",
            asset_path="jira_webhook",
            environment={"REGION_NAME": self.region},
            timeout=cdk.Duration.seconds(60),
            memory_size=256,
        )
        fn.function.add_to_role_policy(...)
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        function_name: str,
        asset_path: str,
        environment: dict[str, str] | None = None,
        timeout: cdk.Duration | None = None,
        memory_size: int = 128,
    ) -> None:
        """Create a Docker Lambda with a named ECR repository.

        Args:
            scope: CDK construct scope
            id: Construct ID
            function_name: Short name for this Lambda (e.g. ``"jira-webhook"``)
            asset_path: Path to the directory containing the Dockerfile,
                relative to ``src/`` (e.g. ``"jira_webhook"``)
            environment: Environment variables for the Lambda function
            timeout: Lambda timeout (default: 30 seconds)
            memory_size: Lambda memory in MB (default: 128)
        """
        super().__init__(scope, id)

        stack = cdk.Stack.of(self)
        resource_name = to_kebab_case(f"{stack.stack_name}-{function_name}")

        # Named ECR repository for this Lambda's image
        self._ecr_repo = ecr.Repository(
            self,
            "EcrRepo",
            repository_name=resource_name,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            empty_on_delete=True,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=5)],
        )

        # Build Docker image - context is src/ for access to common/
        src_dir = os.path.join(os.path.dirname(__file__), "..", "..")
        docker_asset = ecr_assets.DockerImageAsset(
            self,
            "DockerAsset",
            directory=src_dir,
            file=os.path.join(asset_path, "Dockerfile"),
            platform=ecr_assets.Platform.LINUX_AMD64,
        )

        # Copy built image into the named ECR repository
        image_deployment = ECRDeployment(
            self,
            "ImageDeployment",
            src=DockerImageName(docker_asset.image_uri),
            dest=DockerImageName(f"{self._ecr_repo.repository_uri}:{docker_asset.image_tag}"),
        )

        # Lambda function using the image from the named ECR repository
        self._function = lambda_.DockerImageFunction(
            self,
            "Function",
            function_name=resource_name,
            code=lambda_.DockerImageCode.from_ecr(
                self._ecr_repo,
                tag_or_digest=docker_asset.image_tag,
            ),
            timeout=timeout or cdk.Duration.seconds(30),
            memory_size=memory_size,
            environment=environment or {},
        )

        # Ensure image is in ECR before Lambda is created
        self._function.node.add_dependency(image_deployment)

    @property
    def function(self) -> lambda_.DockerImageFunction:
        """The Lambda function.

        Returns:
            DockerImageFunction backed by the named ECR repository
        """
        return self._function

    @property
    def ecr_repository(self) -> ecr.Repository:
        """The named ECR repository holding the Lambda image.

        Returns:
            ECR Repository with lifecycle policy (max 5 images)
        """
        return self._ecr_repo
