from flask import Flask, render_template_string, request
import boto3
import json
from openai import OpenAI
import os
from dotenv import load_dotenv

app = Flask(__name__)

def extract_course_content(course_json):
    """
    Extracts key content-related information from the course JSON.

    Args:
        course_json (dict): The JSON object containing the course data.

    Returns:
        str: A formatted string containing the extracted course content.
    """
    extracted_content = []

    # Extract core course details
    extracted_content.append(f"**Course Title:** {course_json.get('title', 'N/A')}")
    extracted_content.append(f"**Description:** {course_json.get('description', 'N/A')}")
    extracted_content.append(f"**Goal:** {course_json.get('goal', 'N/A')}")

    # Extract learning objectives
    extracted_content.append("\n**Learning Objectives:**")
    for section in course_json.get("sections", []):
        for objective in section.get("learning_objectives", []):
            extracted_content.append(f"- {objective.get('objective_statement', 'N/A')}")

    # Extract and consolidate transcripts per learning object
    extracted_content.append("\n**Transcripts:**")
    for section in course_json.get("sections", []):
        for learning_object in section.get("learning_objects", []):
            content = learning_object.get("content", {})
            
            # Extract transcript if it exists
            transcript = content.get("transcript", "").strip()
            if transcript:
                extracted_content.append(f"- **{learning_object.get('title', 'Unnamed Learning Object')}:**")
                extracted_content.append(f"  {transcript}")

    return "\n".join(extracted_content)

# Path to folder containing JSON files
CML_FOLDER = "example_cmls"

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Chat with course and Perplexity.ai</title>
  <style>
    textarea { width: 100%; font-size: 1em; }
    label { font-weight: bold; }
    .container { width: 80%; margin: auto; max-width: 800px; }
    .button { margin-top: 10px; font-size: 1em; }
  </style>
  <script>
    function loadCMLContent() {
        var selectedFile = document.getElementById("file_selector").value;
        fetch('/load_cml?file=' + selectedFile)
            .then(response => response.text())
            .then(data => {
                document.getElementById("input_text").value = data;
            })
            .catch(error => console.error("Error loading file:", error));
    }
    function showStatus(message) {
      document.getElementById("status_message").innerText = message;
    }

    function prefillQuestion(question) {
        document.getElementById("question_text").value = question;
    }

    document.addEventListener("DOMContentLoaded", function() {
        document.querySelectorAll("form").forEach(form => {
            form.addEventListener("submit", function() {
                showStatus("Processing request, please wait...");
            });
        });
    });
  </script>
</head>
<body>
  <div class="container">
    <h1>Chat with course and Perplexity.ai</h1>
    
    <!-- Dropdown to select JSON file -->
    <label for="file_selector">Select a JSON file:</label>
    <select id="file_selector" onchange="loadCMLContent()">
      <option value="">-- Select a file --</option>
      {% for file in json_files %}
        <option value="{{ file }}">{{ file }}</option>
      {% endfor %}
    </select>

    <br><br>
    
    <div id="status_message" style="color: blue; font-weight: bold; margin-top: 10px;"></div>
    <!-- First form to submit user prompt -->
    <form method="post">
      <label for="input_text">Enter course CML:</label><br>
      <textarea id="input_text" name="input_text" rows="10" placeholder="Enter course CML here...">{{ input_text }}</textarea><br><br>
      <input class="button" type="submit" name="submit_initial" value="Submit course CML to Claude">
    </form>

    <br>

    <!-- Second form to submit edited LLM response -->
    <form method="post">
      <label for="edited_text">List of course facts (editable):</label><br>
      <textarea id="edited_text" name="edited_text" rows="10" placeholder="Claude's response will appear here...">{{ output_text }}</textarea><br><br>

      <!-- Question Pre-fill Buttons -->
      <button type="button" class="button" onclick="prefillQuestion('Check the course material for factual inaccurasies.')">Check for factual inaccuracies</button>
      <button type="button" class="button" onclick="prefillQuestion('Suggest new material that would be highly relevant for the course, but is not currently present.')">Suggest new material</button>
      <button type="button" class="button" onclick="prefillQuestion('Check the course material for any outdated material based on recent regulatory changes.')">Check for regulatory changes</button>

      <br><br>
      <label for="question_text">Question for Perplexity.ai (editable):</label><br>
      <textarea id="question_text" name="question_text" rows="3" placeholder="Enter your question here...">{{ question_text }}</textarea><br><br>

      <input class="button" type="submit" name="submit_edited" value="Submit list of course facts to Perplexity.ai">
    </form>

    <br>

    <label for="final_output">Perplexity.ai response:</label><br>
    <textarea id="final_output" rows="20" readonly placeholder="Perplexity.ai's response will appear here...">{{ final_output }}</textarea>

    <br><br>

    <label for="citations_output">Perplexity.ai Citations:</label><br>
    <textarea id="citations_output" rows="10" readonly placeholder="Citations from Perplexity.ai will appear here...">{{ citations_output }}</textarea>
  </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    input_text = request.form.get('input_text', '')  # Preserve input_text across requests
    output_text = request.form.get('edited_text', '')  # Preserve edited_text
    question_text = request.form.get('question_text', '')  # Preserve question_text
    final_output = ""
    citations_output = ""

    # Ensure JSON files list is always populated
    json_files = [f for f in os.listdir(CML_FOLDER) if f.endswith('.json')]

    if request.method == 'POST':
        client = boto3.client('bedrock-runtime', region_name='us-east-1')
        inference_profile_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

        # Handle first LLM call
        if 'submit_initial' in request.form:
            input_text = request.form.get('input_text', '')

            try:
                # Convert input JSON to a Python dictionary
                course_json = json.loads(input_text)

                # Extract key course content
                extracted_content = extract_course_content(course_json)

                payload = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 5000,
                    "system": "I will share with you an eLearning course. Convert it into an exhaustive list of facts. Don't summarize the facts and be sure to write the facts as they appear in this course, and NOT based on what you know yourself.",
                    "messages": [
                        {"role": "user", "content": extracted_content}
                    ]
                }

                response = client.invoke_model(
                    modelId=inference_profile_id,
                    body=json.dumps(payload),
                    contentType="application/json",
                    accept="application/json"
                )

                response_body = response['body'].read().decode("utf-8")
                result_json = json.loads(response_body)

                output_text = "\n".join([item["text"] for item in result_json.get("content", []) if item.get("type") == "text"])

            except Exception as e:
                output_text = f"An error occurred: {str(e)}"

        # Handle second LLM call using Perplexity Sonar-Pro
        elif 'submit_edited' in request.form:
            try:
                perplexity_client = OpenAI(api_key=os.getenv("PERPLEXITY_API_KEY"), base_url="https://api.perplexity.ai")

                messages = [
                    {
                        "role": "system",
                        "content": "I will give you a list of facts from an eLearning course. Search the internet to answer the question."
                    },
                    {
                        "role": "user",
                        "content": output_text + "\n\nQuestion: " + question_text
                    }
                ]

                response = perplexity_client.chat.completions.create(
                    model="sonar-pro",
                    messages=messages
                )

                # Extract response content
                if response.choices:
                    final_output = response.choices[0].message.content
                    citations = response.citations if hasattr(response, "citations") else []
                    citations_output = "\n".join(citations) if citations else "No citations available."

                else:
                    final_output = "No response received."
                    citations_output = "No citations available."

            except Exception as e:
                final_output = f"An error occurred: {str(e)}"
                citations_output = "No citations available."

    return render_template_string(
        HTML_TEMPLATE, 
        json_files=json_files,
        input_text=input_text, 
        output_text=output_text, 
        question_text=question_text, 
        final_output=final_output, 
        citations_output=citations_output,
        status_message=""  # Clears the status message when the response is received
    )

@app.route('/load_cml', methods=['GET'])
def load_cml():
    """Loads the selected JSON file and returns its contents."""
    file_name = request.args.get('file', '')

    if file_name and file_name in os.listdir(CML_FOLDER):
        file_path = os.path.join(CML_FOLDER, file_name)
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    
    return "Error: File not found", 404

if __name__ == '__main__':
    app.run(debug=True)