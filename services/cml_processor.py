import json

def extract_course_content(course_json):
    """
    Extracts key content-related information from the course JSON.
    """
    extracted_content = []
    extracted_content.append(f"**Course Title:** {course_json.get('title', 'N/A')}")
    extracted_content.append(f"**Description:** {course_json.get('description', 'N/A')}")
    extracted_content.append(f"**Goal:** {course_json.get('goal', 'N/A')}")

    # Extract learning objectives
    extracted_content.append("\n**Learning Objectives:**")
    for section in course_json.get("sections", []):
        for objective in section.get("learning_objectives", []):
            extracted_content.append(f"- {objective.get('objective_statement', 'N/A')}")

    # Extract transcripts
    extracted_content.append("\n**Transcripts:**")
    for section in course_json.get("sections", []):
        for learning_object in section.get("learning_objects", []):
            transcript = learning_object.get("content", {}).get("transcript", "").strip()
            if transcript:
                extracted_content.append(f"- **{learning_object.get('title', 'Unnamed Learning Object')}:** {transcript}")

    return "\n".join(extracted_content)