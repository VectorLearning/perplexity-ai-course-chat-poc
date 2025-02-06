import json
import boto3
from openai import OpenAI
from config.config import AWS_REGION, BEDROCK_MODEL_ID, PERPLEXITY_API_KEY

def call_claude(cml_content):
    """
    Calls Anthropic Claude 3.5 Sonnet via AWS Bedrock with course content.
    """
    try:
        client = boto3.client('bedrock-runtime', region_name=AWS_REGION)

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 5000,
            "system": "Convert the eLearning course into an exhaustive list of facts.",
            "messages": [{"role": "user", "content": cml_content}]
        }

        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json"
        )

        response_body = response['body'].read().decode("utf-8")
        result_json = json.loads(response_body)
        return "\n".join([item["text"] for item in result_json.get("content", []) if item.get("type") == "text"])

    except Exception as e:
        return f"Error: {str(e)}"

def call_perplexity(fact_list, question):
    """
    Calls Perplexity.ai Sonar-Pro to analyze course facts.
    """
    try:
        perplexity_client = OpenAI(api_key=PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai")

        messages = [
            {"role": "system", "content": "I will give you a list of facts from an eLearning course. Search the internet to answer the question."},
            {"role": "user", "content": fact_list + "\n\nQuestion: " + question}
        ]

        response = perplexity_client.chat.completions.create(model="sonar-pro", messages=messages)

        if response.choices:
            return response.choices[0].message.content, "\n".join(response.citations) if hasattr(response, "citations") else "No citations available."
        
        return "No response received.", "No citations available."

    except Exception as e:
        return f"Error: {str(e)}", "No citations available."