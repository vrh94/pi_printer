import os
import uuid
import logging

from flask import Flask, request, jsonify, render_template, abort
from werkzeug.utils import secure_filename

from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH, AUTO_DELETE_AFTER_PRINT
from printer import list_printers, print_file as do_print

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def safe_path(filename):
    """
    Resolve the absolute path for *filename* inside UPLOAD_FOLDER.
    Raises 400 if the resolved path escapes UPLOAD_FOLDER (path traversal guard).
    """
    resolved = os.path.realpath(os.path.join(UPLOAD_FOLDER, filename))
    if not resolved.startswith(os.path.realpath(UPLOAD_FOLDER) + os.sep):
        abort(400, description='Invalid filename')
    return resolved


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({
            'error': f'File type not allowed. Accepted types: {", ".join(sorted(ALLOWED_EXTENSIONS))}'
        }), 400

    original = secure_filename(file.filename)
    unique_name = f'{uuid.uuid4().hex[:8]}_{original}'
    dest = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(dest)

    size = os.path.getsize(dest)
    logger.info('Uploaded %s (%d bytes)', unique_name, size)
    return jsonify({'filename': unique_name, 'size': size}), 200


@app.route('/files', methods=['GET'])
def list_files():
    entries = []
    for name in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, name)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            entries.append({
                'name': name,
                'size': stat.st_size,
                'mtime': stat.st_mtime,
            })
    entries.sort(key=lambda e: e['mtime'], reverse=True)
    return jsonify(entries)


@app.route('/print/<path:filename>', methods=['POST'])
def print_route(filename):
    filename = secure_filename(filename)
    filepath = safe_path(filename)

    if not os.path.isfile(filepath):
        return jsonify({'error': 'File not found'}), 404

    body = request.get_json(silent=True) or {}
    printer_name = body.get('printer') or None
    page_from = body.get('page_from') or None
    page_to = body.get('page_to') or None

    success, message = do_print(filepath, printer_name, page_from, page_to)
    logger.info('Print %s -> success=%s msg=%s', filename, success, message)

    if success and AUTO_DELETE_AFTER_PRINT:
        try:
            os.remove(filepath)
        except OSError as exc:
            logger.warning('Auto-delete failed for %s: %s', filename, exc)

    return jsonify({'success': success, 'message': message}), 200 if success else 500


@app.route('/file/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    filename = secure_filename(filename)
    filepath = safe_path(filename)

    if not os.path.isfile(filepath):
        return jsonify({'error': 'File not found'}), 404

    os.remove(filepath)
    logger.info('Deleted %s', filename)
    return '', 204


@app.route('/printers', methods=['GET'])
def printers():
    return jsonify(list_printers())


@app.route('/jobs/cancel', methods=['POST'])
def cancel_jobs():
    import subprocess
    try:
        result = subprocess.run(['cancel', '-a'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 or 'no jobs' in (result.stderr or '').lower():
            return jsonify({'success': True, 'message': 'All print jobs cancelled'})
        return jsonify({'success': False, 'message': result.stderr.strip() or 'cancel failed'}), 500
    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'cancel command not found (CUPS not installed)'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'cancel timed out'}), 500


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum is 300 MB.'}), 413


@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': str(e.description)}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1200, debug=False)
