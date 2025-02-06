from flask import Blueprint, request, jsonify
import os
from config.config import CML_FOLDER

load_cml_bp = Blueprint('load_cml', __name__)

@load_cml_bp.route('/load_cml', methods=['GET'])
def load_cml():
    file_name = request.args.get('file', '')

    if file_name and file_name in os.listdir(CML_FOLDER):
        with open(os.path.join(CML_FOLDER, file_name), 'r', encoding='utf-8') as file:
            return file.read()

    return jsonify({"error": "File not found"}), 404