import aws_cdk as cdk
from dotenv import load_dotenv

from src.cdk import SREAgentStack
from src.cdk.config import get_config_from_context

load_dotenv()

app = cdk.App()

# Load environment-specific configuration from config/{env}.yaml
config = get_config_from_context(app)

# SRE Agent Stack: Gateways, Runtimes, MCP Servers
agent_stack = SREAgentStack(
    app,
    f"SREAgentStack-{config.environment}",
    config=config,
)

app.synth()
