from flask import Flask, render_template_string, request, jsonify
import os
import json
import boto3
from openai import OpenAI
from dotenv import load_dotenv
import markdown  # For server-side Markdown conversion

load_dotenv()

app = Flask(__name__)

# Register a Jinja filter for Markdown conversion.
app.jinja_env.filters['md'] = lambda text: markdown.markdown(text or "")

# ------------------
# Configuration
# ------------------
CML_FOLDER = "example_cmls"  # Folder with JSON CML files
AWS_REGION = "us-east-1"
BEDROCK_MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# ------------------
# Initialize Clients
# ------------------
bedrock_client = boto3.client('bedrock-runtime', region_name=AWS_REGION)

# ------------------
# HTML Template
# ------------------
# (In a full project, move this to a separate file under /templates.)
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Course Transcript Checker</title>
    <!-- Include Bootstrap CSS and JS for collapsible panels and spinner styling -->
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.1/dist/umd/popper.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
    <style>
        .rendered-markdown {
            border: 1px solid #ced4da;
            padding: 10px;
            border-radius: 4px;
            background: #f8f9fa;
            margin-bottom: 10px;
        }
        .side-by-side {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }
        .side-by-side > div {
            flex: 1;
        }
        .btn-margin {
            margin-bottom: 10px;
        }
        .spinner-border {
            width: 1rem;
            height: 1rem;
            vertical-align: text-bottom;
            margin-left: 5px;
        }
    </style>
</head>
<body>
<div class="container mt-4">
    <h1>Course Transcript Checker</h1>
    
    <!-- Dropdown to select JSON file -->
    <div class="form-group">
        <label for="file_selector">Select a JSON file:</label>
        <select id="file_selector" class="form-control">
            <option value="">-- Select a file --</option>
            {% for file in json_files %}
                <option value="{{ file }}">{{ file }}</option>
            {% endfor %}
        </select>
        <button id="load_file_btn" class="btn btn-primary mt-2">
            Load CML
        </button>
    </div>
    
    <!-- Course Content rendered if a file is loaded -->
    <div id="course_content">
        {% if course_json %}
            <div id="accordion">
            {% for section in course_json.sections %}
                <div class="card">
                    <div class="card-header" id="headingSection{{ loop.index }}">
                        <h5 class="mb-0">
                            <button class="btn btn-link" data-toggle="collapse" data-target="#collapseSection{{ loop.index }}" aria-expanded="true" aria-controls="collapseSection{{ loop.index }}">
                                Section: {{ section.title if section.title else "Untitled Section" }}
                            </button>
                        </h5>
                    </div>
                    <div id="collapseSection{{ loop.index }}" class="collapse" aria-labelledby="headingSection{{ loop.index }}" data-parent="#accordion">
                        <div class="card-body">
                            <div id="accordionSection{{ loop.index }}">
                            {% for lo in section.learning_objects %}
                                <div class="card">
                                    <div class="card-header" id="headingLO{{ loop.index0 }}">
                                        <h5 class="mb-0">
                                            <button class="btn btn-link" data-toggle="collapse" data-target="#collapseLO{{ loop.index0 }}" aria-expanded="true" aria-controls="collapseLO{{ loop.index0 }}">
                                                Learning Object: {{ lo.title if lo.title else "Untitled Learning Object" }}
                                            </button>
                                        </h5>
                                    </div>
                                    <div id="collapseLO{{ loop.index0 }}" class="collapse" aria-labelledby="headingLO{{ loop.index0 }}" data-parent="#accordionSection{{ loop.index }}">
                                        <div class="card-body">
                                            <!-- Transcript Display (rendered Markdown, not editable) -->
                                            <div class="form-group">
                                                <label>Original Transcript</label>
                                                <div class="rendered-markdown original-transcript">
                                                    {{ lo.content.transcript | default('') | md | safe }}
                                                </div>
                                            </div>
                                            <div class="form-group">
                                                <label>Proposed Transcript</label>
                                                <div class="rendered-markdown proposed-transcript"></div>
                                            </div>
                                            
                                            <!-- Button to trigger check for inaccuracies -->
                                            <button class="btn btn-warning btn-check btn-margin">
                                                Check for inaccuracies
                                                <span class="spinner-border spinner-check" role="status" style="display:none;"></span>
                                            </button>
                                            
                                            <!-- Side-by-side display for Perplexity.ai response and citations -->
                                            <div class="row">
                                                <div class="col-md-7">
                                                    <label>Perplexity.ai Response</label>
                                                    <div class="rendered-markdown perplexity-response"></div>
                                                </div>
                                                <div class="col-md-5">
                                                    <label>Perplexity.ai Citations</label>
                                                    <div class="rendered-markdown perplexity-citations"></div>
                                                </div>
                                            </div>
                                            
                                            <!-- Placeholder for the highlight button -->
                                            <div class="highlight-container mt-2"></div>
                                        </div>
                                    </div>
                                </div>
                            {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>
            {% endfor %}
            </div>
        {% endif %}
    </div>
</div>

<script>
// When the user clicks "Load CML", redirect with the file name so that the server loads and renders the JSON.
document.getElementById('load_file_btn').addEventListener('click', function() {
    var selectedFile = document.getElementById('file_selector').value;
    if(selectedFile) {
        window.location.href = '/?file=' + selectedFile;
    }
});

// Utility function to process citations: prepend sequential numbers and make clickable links.
function processCitations(citationsText) {
    var lines = citationsText.split("\\n");
    var citationsHTML = "";
    var count = 1;
    lines.forEach(function(line) {
        line = line.trim();
        if(line !== "") {
            citationsHTML += '<a href="' + line + '" target="_blank">[' + count + '] ' + line + '</a><br>';
            count++;
        }
    });
    return citationsHTML;
}

// When "Check for inaccuracies" is clicked in a learning object panel:
document.addEventListener('click', function(e) {
    if(e.target && e.target.closest('.btn-check')) {
        var btn = e.target.closest('.btn-check');
        var container = btn.closest('.card-body');
        var originalDiv = container.querySelector('.original-transcript');
        var perplexityResponseDiv = container.querySelector('.perplexity-response');
        var perplexityCitationsDiv = container.querySelector('.perplexity-citations');
        var highlightContainer = container.querySelector('.highlight-container');
        var transcript = originalDiv.innerText;
        
        // Clear any prior responses and highlight buttons.
        perplexityResponseDiv.innerHTML = '';
        perplexityCitationsDiv.innerHTML = '';
        highlightContainer.innerHTML = '';
        
        // Show spinner.
        var spinner = btn.querySelector('.spinner-check');
        spinner.style.display = 'inline-block';
        
        // POST the transcript to /check_inaccuracies.
        fetch('/check_inaccuracies', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ transcript: transcript })
        })
        .then(response => response.json())
        .then(data => {
            // Insert returned HTML (already converted from Markdown on the server).
            perplexityResponseDiv.innerHTML = data.perplexity_response;
            // Process citations to add numbers and clickable links.
            perplexityCitationsDiv.innerHTML = processCitations(data.citations);
            // Hide spinner.
            spinner.style.display = 'none';
            // If response ends with "NO" (ignoring trailing whitespace), add the highlight button.
            if(data.perplexity_response.trim().endsWith("NO</p>") || data.perplexity_response.trim().endsWith("NO")) {
                var highlightBtn = document.createElement('button');
                highlightBtn.className = "btn btn-danger btn-highlight btn-margin";
                highlightBtn.innerHTML = 'Highlight offending content <span class="spinner-border spinner-highlight" role="status" style="display:none;"></span>';
                highlightContainer.appendChild(highlightBtn);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            spinner.style.display = 'none';
        });
    }
});

// When "Highlight offending content" is clicked:
document.addEventListener('click', function(e) {
    if(e.target && e.target.closest('.btn-highlight')) {
        var btn = e.target.closest('.btn-highlight');
        var container = btn.closest('.card-body');
        var originalDiv = container.querySelector('.original-transcript');
        var proposedDiv = container.querySelector('.proposed-transcript');
        var perplexityResponseDiv = container.querySelector('.perplexity-response');
        var transcript = originalDiv.innerText;
        var perplexityResponse = perplexityResponseDiv.innerText;
        
        // Show spinner.
        var spinner = btn.querySelector('.spinner-highlight');
        spinner.style.display = 'inline-block';
        
        // POST the transcript and perplexity.ai response to /highlight.
        fetch('/highlight', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ transcript: transcript, perplexity_response: perplexityResponse })
        })
        .then(response => response.json())
        .then(data => {
            // Update the transcript displays with returned HTML.
            originalDiv.innerHTML = data.original_transcript;
            proposedDiv.innerHTML = data.proposed_transcript;
            spinner.style.display = 'none';
        })
        .catch(error => {
            console.error('Error:', error);
            spinner.style.display = 'none';
        });
    }
});
</script>
</body>
</html>
"""

# ------------------
# Routes
# ------------------

@app.route('/', methods=['GET'])
def index():
    """Main route that lists available CML JSON files and (if a file is selected) renders the course content."""
    json_files = [f for f in os.listdir(CML_FOLDER) if f.endswith('.json')]
    course_json = None
    file_name = request.args.get('file', '')
    if file_name and file_name in os.listdir(CML_FOLDER):
        file_path = os.path.join(CML_FOLDER, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                course_json = json.load(f)
        except Exception as e:
            course_json = None
    return render_template_string(TEMPLATE, json_files=json_files, course_json=course_json)

@app.route('/check_inaccuracies', methods=['POST'])
def check_inaccuracies():
    """
    Receives a transcript, sends it to Claude to extract a master list of facts,
    then sends the facts to Perplexity.ai to check if the content is accurate.
    Perplexity.ai is asked to end its response with either "YES" or "NO" on a new line.
    The endpoint returns HTML for the response (Markdown converted server-side)
    and raw citations as newline-separated links.
    """
    data = request.get_json()
    transcript = data.get('transcript', '')
    
    # --- Step 1: Call Claude to get a master list of facts ---
    claude_payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2000,
        "temperature": 0,
        "system": "Convert the following transcript from an eLearning course into an exhaustive list of facts. Be concises, but do NOT summarize, provide commentary, or omit any details. List the facts exactly as they appear in the course.",
        "messages": [{"role": "user", "content": "Transcript:\n" + transcript}]
    }
    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(claude_payload),
            contentType="application/json",
            accept="application/json"
        )
        response_body = response['body'].read().decode("utf-8")
        result_json = json.loads(response_body)
        facts = "\n".join([item["text"] for item in result_json.get("content", []) if item.get("type") == "text"])

        print(facts + '\n\n')

    except Exception as e:
        return jsonify({"perplexity_response": markdown.markdown(f"Error in Claude call: {str(e)}"),
                        "citations": ""})
    
    # --- Step 2: Call Perplexity.ai to check accuracy ---
    try:
        perplexity_client = OpenAI(api_key=PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai")
        messages = [
            {
                "role": "user",
                "content": "Here is a list of facts:\n" + facts + "\n\n\n Report on if these are accurate and up-to-date with the most recent regulations. Most importantly, if something is inaccurate, specifically state what is wrong and what the correct information is. Be specific and give details. If all of the facts are accurate, end your response with 'YES'. Otherwise, if at least one of the facts is outdated or wrong, end your response with 'NO'. Always end your response with either 'YES' or 'NO' on a new line."
            }
        ]
        perplexity_response_obj = perplexity_client.chat.completions.create(
            model="sonar-pro",
            temperature=0,
            messages=messages
        )
        if perplexity_response_obj.choices:
            perplexity_response = perplexity_response_obj.choices[0].message.content
            
            # Convert the response Markdown to HTML.
            perplexity_response_html = markdown.markdown(perplexity_response)
            # Assume citations come as a list of URLs.
            citations = ""
            if hasattr(perplexity_response_obj, "citations") and perplexity_response_obj.citations:
                citations = "\n".join(perplexity_response_obj.citations)
        else:
            perplexity_response_html = markdown.markdown("No response received.")
            citations = ""
    except Exception as e:
        perplexity_response_html = markdown.markdown(f"Error in perplexity.ai call: {str(e)}")
        citations = ""
    
    return jsonify({"perplexity_response": perplexity_response_html, "citations": citations})

@app.route('/highlight', methods=['POST'])
def highlight():
    """
    Receives a transcript and the Perplexity.ai response.
    Calls Claude to produce (a) a version of the transcript with offending sentences highlighted in red (Markdown)
    and (b) a corrected transcript with changes highlighted in green.
    Claude is asked to format its answer as JSON. The returned Markdown is converted to HTML.
    """
    data = request.get_json()
    transcript = data.get('transcript', '')
    perplexity_response = data.get('perplexity_response', '')
    
    claude_payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 3000,
        "temperature": 0,
        "system": (
            "Given the following transcript and an analysis of any factual inaccuracies that may be present, "
            "highlight any incorrect or outdated sentence(s) in bold using Markdown, "
            "and rewrite the transcript correctly with the altered content also highlighted in bold. "
            "When rewriting the transcript, incorporate the correct facts from the analysis."
            "Format your answer as JSON with two keys: 'original_transcript' (the highlighted transcript) "
            "and 'proposed_transcript' (the corrected version)."
        ),
        "messages": [
            {"role": "user", "content": f"Transcript:\n{transcript}\n\nAnalysis:\n{perplexity_response}"}
        ]
    }
    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(claude_payload),
            contentType="application/json",
            accept="application/json"
        )
        response_body = response['body'].read().decode("utf-8")
        result_json = json.loads(response_body)
        claude_text = ""
        for item in result_json.get("content", []):
            if item.get("type") == "text":
                claude_text += item.get("text")
        parsed = json.loads(claude_text)
        original_transcript = parsed.get("original_transcript", transcript)
        proposed_transcript = parsed.get("proposed_transcript", "")
        # Convert the Markdown to HTML.
        original_transcript_html = markdown.markdown(original_transcript)
        proposed_transcript_html = markdown.markdown(proposed_transcript)
    except Exception as e:
        original_transcript_html = markdown.markdown(transcript)
        proposed_transcript_html = markdown.markdown(f"Error: {str(e)}")
    
    return jsonify({
        "original_transcript": original_transcript_html,
        "proposed_transcript": proposed_transcript_html
    })

@app.route('/load_cml', methods=['GET'])
def load_cml():
    """Returns the raw content of a selected JSON CML file."""
    file_name = request.args.get('file', '')
    if file_name and file_name in os.listdir(CML_FOLDER):
        file_path = os.path.join(CML_FOLDER, file_name)
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Error: File not found", 404

# ------------------
# Main
# ------------------
if __name__ == '__main__':
    app.run(debug=True)