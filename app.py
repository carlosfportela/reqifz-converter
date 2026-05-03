import os
import io
import uuid
import tempfile
import zipfile
import logging
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename

# Import the correct converter classes
from reqifz_converter import ReqIFZConverter
from reqifz_converter_v1_logic import ReqIFZConverterV1

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024  # 1GB max for multiple files

# In-memory storage for batches (in a real app, use a DB or Redis)
# batches[batch_id] = { 'dir': '/tmp/...', 'files': [ {id, original_name, output_filename, log} ] }
batches = {}

class MemoryLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []
    def emit(self, record):
        msg = self.format(record)
        self.logs.append(msg)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/convert_batch', methods=['POST'])
def convert_batch():
    if 'files' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
    batch_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix=f"reqifz_batch_{batch_id}_")
    
    batch_data = {
        'dir': temp_dir,
        'files': []
    }
    
    for f in files:
        if not f.filename.endswith('.reqifz'):
            continue
            
        file_id = str(uuid.uuid4())
        filename = secure_filename(f.filename)
        input_path = Path(temp_dir) / filename
        stem = input_path.stem
        output_filename = f"{stem}_elm72.reqifz"
        output_path = Path(temp_dir) / output_filename
        
        f.save(input_path)
        
        # Setup logging capture for this file
        log_handler = MemoryLogHandler()
        log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger = logging.getLogger() # Capture root logger (used by the script)
        logger.addHandler(log_handler)
        # Set level to capture INFO and WARNINGs
        old_level = logger.level
        logger.setLevel(logging.INFO)
        
        status = 'success'
        try:
            # Convert using selected algorithm
            algorithm = request.form.get('algorithm', 'v2')
            if algorithm == 'v1':
                converter = ReqIFZConverterV1(str(input_path), str(output_path))
            else:
                converter = ReqIFZConverter(str(input_path), str(output_path))
            converter.convert()
        except Exception as e:
            status = 'error'
            logger.error(f"Erro crítico durante a conversão: {str(e)}")
        finally:
            logger.removeHandler(log_handler)
            logger.setLevel(old_level)
            
        batch_data['files'].append({
            'id': file_id,
            'original_name': filename,
            'output_filename': output_filename,
            'status': status,
            'logs': "\n".join(log_handler.logs)
        })
        
    batches[batch_id] = batch_data
    
    return jsonify({
        'batch_id': batch_id,
        'results': batch_data['files']
    })

@app.route('/api/download/<batch_id>/<file_id>', methods=['GET'])
def download_file(batch_id, file_id):
    if batch_id not in batches:
        return "Lote não encontrado", 404
        
    batch = batches[batch_id]
    file_data = next((f for f in batch['files'] if f['id'] == file_id), None)
    
    if not file_data or file_data['status'] != 'success':
        return "Arquivo não encontrado ou conversão falhou", 404
        
    output_path = Path(batch['dir']) / file_data['output_filename']
    if not output_path.exists():
        return "Arquivo físico não encontrado", 404
        
    return send_file(
        output_path,
        as_attachment=True,
        download_name=file_data['output_filename'],
        mimetype='application/zip'
    )

@app.route('/api/download_all/<batch_id>', methods=['GET'])
def download_all(batch_id):
    if batch_id not in batches:
        return "Lote não encontrado", 404
        
    batch = batches[batch_id]
    success_files = [f for f in batch['files'] if f['status'] == 'success']
    
    if not success_files:
        return "Nenhum arquivo convertido com sucesso para baixar", 400
        
    memory_zip = io.BytesIO()
    with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_data in success_files:
            output_path = Path(batch['dir']) / file_data['output_filename']
            if output_path.exists():
                zf.write(output_path, arcname=file_data['output_filename'])
                
    memory_zip.seek(0)
    return send_file(
        memory_zip,
        as_attachment=True,
        download_name=f"reqifz_batch_converted_{batch_id[:8]}.zip",
        mimetype='application/zip'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
