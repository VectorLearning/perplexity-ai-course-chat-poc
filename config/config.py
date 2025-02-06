import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# AWS & AI Model Configs
AWS_REGION = "us-east-1"
BEDROCK_MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Folder Paths
CML_FOLDER = "example_cmls"