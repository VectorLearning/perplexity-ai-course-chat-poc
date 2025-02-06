from flask import Blueprint, render_template, request
import os
import json
from config.config import CML_FOLDER
from services.llm_service import call_claude, call_perplexity
from services.cml_processor import extract_course_content

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    input_text = request.form.get('input_text', '')
    output_text = request.form.get('edited_text', '')
    question_text = request.form.get('question_text', '')
    final_output, citations_output = "", ""

    json_files = [f for f in os.listdir(CML_FOLDER) if f.endswith('.json')]

    if request.method == 'POST':
        if 'submit_initial' in request.form:
            try:
                course_json = json.loads(input_text)
                extracted_content = extract_course_content(course_json)
                output_text = call_claude(extracted_content)
            except Exception as e:
                output_text = f"An error occurred: {str(e)}"

        elif 'submit_edited' in request.form:
            final_output, citations_output = call_perplexity(output_text, question_text)

    return render_template('index.html', json_files=json_files, input_text=input_text, output_text=output_text, question_text=question_text, final_output=final_output, citations_output=citations_output)