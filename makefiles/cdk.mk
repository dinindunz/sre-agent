# ==============================================================================
# CDK Deployment Commands
# ==============================================================================

deploy: format lint
	@echo "Deploying SRE Agent stack (ENV=$(ENV))..."
	cdk deploy --context env=$(ENV) --require-approval never --exclusively SREAgentStack-$(ENV)

diff: format lint
	@echo "Showing changes for SRE Agent stack (ENV=$(ENV))..."
	cdk diff --context env=$(ENV) --exclusively SREAgentStack-$(ENV)

destroy:
	@echo "Destroying SRE Agent stack (ENV=$(ENV))..."
	cdk destroy --context env=$(ENV) --exclusively SREAgentStack-$(ENV)
