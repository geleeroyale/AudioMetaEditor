import os
import io
import tempfile
import logging
from flask import Flask, render_template, request, jsonify, session, send_file
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, COMM
from mutagen.wave import WAVE
from mutagen.mp3 import MP3
import pydub

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure temp directory for file uploads
TEMP_DIR = tempfile.gettempdir()
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload size

# Map of supported file formats and their extensions
SUPPORTED_FORMATS = {
    'flac': ['audio/flac', 'audio/x-flac'],
    'mp3': ['audio/mpeg', 'audio/mp3'],
    'wav': ['audio/wav', 'audio/x-wav', 'audio/wave'],
    'aaf': ['audio/aaf', 'audio/x-aaf']  # Note: AAF format may need special handling
}

def get_format_extension(mimetype):
    """Convert mimetype to file extension"""
    for ext, mimetypes in SUPPORTED_FORMATS.items():
        if mimetype in mimetypes:
            return ext
    return None

def is_supported_file(filename):
    """Check if the file extension is supported"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in SUPPORTED_FORMATS.keys()

def get_temp_path(filename):
    """Get a secure temporary file path"""
    return os.path.join(TEMP_DIR, secure_filename(filename))

def read_metadata(file_path):
    """Read metadata from audio file based on its format"""
    try:
        file_ext = file_path.rsplit('.', 1)[1].lower()
        metadata = {}
        
        if file_ext == 'flac':
            audio = FLAC(file_path)
            metadata = {
                'title': audio.get('title', [''])[0],
                'artist': audio.get('artist', [''])[0],
                'album': audio.get('album', [''])[0],
                'date': audio.get('date', [''])[0],
                'genre': audio.get('genre', [''])[0],
                'comment': audio.get('comment', [''])[0],
                'format': 'FLAC',
                'channels': audio.info.channels,
                'sample_rate': audio.info.sample_rate,
                'bits_per_sample': audio.info.bits_per_sample,
                'length': audio.info.length
            }
            
        elif file_ext == 'mp3':
            audio = MP3(file_path)
            id3 = ID3(file_path) if audio.tags else None
            
            metadata = {
                'title': id3.get('TIT2', TIT2(encoding=3, text=[''])).text[0] if id3 else '',
                'artist': id3.get('TPE1', TPE1(encoding=3, text=[''])).text[0] if id3 else '',
                'album': id3.get('TALB', TALB(encoding=3, text=[''])).text[0] if id3 else '',
                'date': str(id3.get('TDRC', TDRC(encoding=3, text=[''])).text[0]) if id3 else '',
                'genre': str(id3.get('TCON', TCON(encoding=3, text=[''])).text[0]) if id3 else '',
                'comment': id3.get('COMM', COMM(encoding=3, text=[''])).text[0] if id3 and 'COMM' in id3 else '',
                'format': 'MP3',
                'channels': audio.info.channels,
                'sample_rate': audio.info.sample_rate,
                'bitrate': audio.info.bitrate,
                'length': audio.info.length
            }
            
        elif file_ext == 'wav':
            audio = WAVE(file_path)
            metadata = {
                'title': '',
                'artist': '',
                'album': '',
                'date': '',
                'genre': '',
                'comment': '',
                'format': 'WAV',
                'channels': audio.info.channels,
                'sample_rate': audio.info.sample_rate,
                'bits_per_sample': getattr(audio.info, 'bits_per_sample', 0),
                'length': audio.info.length
            }
            
            # Try to get ID3 tags if available in WAV
            try:
                id3 = ID3(file_path)
                metadata.update({
                    'title': id3.get('TIT2', TIT2(encoding=3, text=[''])).text[0] if 'TIT2' in id3 else '',
                    'artist': id3.get('TPE1', TPE1(encoding=3, text=[''])).text[0] if 'TPE1' in id3 else '',
                    'album': id3.get('TALB', TALB(encoding=3, text=[''])).text[0] if 'TALB' in id3 else '',
                    'date': str(id3.get('TDRC', TDRC(encoding=3, text=[''])).text[0]) if 'TDRC' in id3 else '',
                    'genre': str(id3.get('TCON', TCON(encoding=3, text=[''])).text[0]) if 'TCON' in id3 else '',
                    'comment': id3.get('COMM', COMM(encoding=3, text=[''])).text[0] if 'COMM' in id3 else ''
                })
            except:
                # WAV may not have ID3 tags, just continue
                pass
                
        elif file_ext == 'aaf':
            # AAF handling is more complex, this is a simplified approach
            # Would typically require specialized libraries or bindings
            metadata = {
                'title': '',
                'artist': '',
                'album': '',
                'date': '',
                'genre': '',
                'comment': '',
                'format': 'AAF',
                'length': 0,
                'note': 'AAF metadata extraction requires specialized libraries'
            }
            
            # Try to use mutagen to extract any available metadata
            try:
                audio = mutagen.File(file_path)
                if audio and hasattr(audio, 'info'):
                    metadata['length'] = audio.info.length
            except:
                logging.warning("Could not extract AAF metadata with mutagen")
        
        return metadata
    
    except Exception as e:
        logging.error(f"Error reading metadata: {str(e)}")
        return {
            'error': str(e),
            'title': '',
            'artist': '',
            'album': '',
            'date': '',
            'genre': '',
            'comment': '',
            'format': file_ext.upper()
        }

def write_metadata(file_path, metadata):
    """Write metadata to audio file based on its format"""
    try:
        file_ext = file_path.rsplit('.', 1)[1].lower()
        
        if file_ext == 'flac':
            audio = FLAC(file_path)
            if 'title' in metadata: audio['title'] = metadata['title']
            if 'artist' in metadata: audio['artist'] = metadata['artist']
            if 'album' in metadata: audio['album'] = metadata['album']
            if 'date' in metadata: audio['date'] = metadata['date']
            if 'genre' in metadata: audio['genre'] = metadata['genre']
            if 'comment' in metadata: audio['comment'] = metadata['comment']
            audio.save()
            
        elif file_ext == 'mp3':
            try:
                audio = ID3(file_path)
            except:
                # If no ID3 tags exist, create them
                from mutagen.id3 import ID3NoHeaderError
                try:
                    audio = ID3()
                except ID3NoHeaderError:
                    audio = ID3()
            
            if 'title' in metadata: audio['TIT2'] = TIT2(encoding=3, text=[metadata['title']])
            if 'artist' in metadata: audio['TPE1'] = TPE1(encoding=3, text=[metadata['artist']])
            if 'album' in metadata: audio['TALB'] = TALB(encoding=3, text=[metadata['album']])
            if 'date' in metadata: audio['TDRC'] = TDRC(encoding=3, text=[metadata['date']])
            if 'genre' in metadata: audio['TCON'] = TCON(encoding=3, text=[metadata['genre']])
            if 'comment' in metadata: 
                audio['COMM'] = COMM(encoding=3, lang='eng', desc='Comment', text=[metadata['comment']])
            
            audio.save(file_path)
            
        elif file_ext == 'wav':
            # WAV files can have ID3 tags, but it's not standard
            try:
                audio = ID3(file_path)
            except:
                # If no ID3 tags exist, create them
                audio = ID3()
            
            if 'title' in metadata: audio['TIT2'] = TIT2(encoding=3, text=[metadata['title']])
            if 'artist' in metadata: audio['TPE1'] = TPE1(encoding=3, text=[metadata['artist']])
            if 'album' in metadata: audio['TALB'] = TALB(encoding=3, text=[metadata['album']])
            if 'date' in metadata: audio['TDRC'] = TDRC(encoding=3, text=[metadata['date']])
            if 'genre' in metadata: audio['TCON'] = TCON(encoding=3, text=[metadata['genre']])
            if 'comment' in metadata: 
                audio['COMM'] = COMM(encoding=3, lang='eng', desc='Comment', text=[metadata['comment']])
            
            audio.save(file_path)
            
        elif file_ext == 'aaf':
            # AAF format requires specialized handling
            # This is a placeholder - actual implementation would depend on AAF libraries
            return {
                'success': False,
                'message': 'Writing AAF metadata is not fully supported in this version.'
            }
            
        return {
            'success': True,
            'message': 'Metadata updated successfully'
        }
        
    except Exception as e:
        logging.error(f"Error writing metadata: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to update metadata: {str(e)}'
        }

@app.route('/')
def index():
    """Render the main application page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and extract metadata"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not is_supported_file(file.filename):
        return jsonify({'error': 'Unsupported file format'}), 400
    
    try:
        # Save the file to a temporary location
        temp_path = get_temp_path(file.filename)
        file.save(temp_path)
        
        # Extract metadata
        metadata = read_metadata(temp_path)
        
        # Store the temp path in session for later use
        session['current_file'] = {
            'path': temp_path,
            'name': file.filename
        }
        
        # Add the filename to metadata
        metadata['filename'] = file.filename
        
        return jsonify(metadata)
    
    except Exception as e:
        logging.error(f"Error processing upload: {str(e)}")
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/save', methods=['POST'])
def save_metadata():
    """Save updated metadata to the audio file"""
    if 'current_file' not in session:
        return jsonify({'error': 'No file is currently loaded'}), 400
    
    file_info = session.get('current_file')
    metadata = request.json
    
    if not metadata:
        return jsonify({'error': 'No metadata provided'}), 400
    
    result = write_metadata(file_info['path'], metadata)
    
    if result.get('success', False):
        return jsonify(result)
    else:
        return jsonify(result), 500

@app.route('/download')
def download_file():
    """Download the edited file"""
    if 'current_file' not in session:
        return jsonify({'error': 'No file is currently loaded'}), 400
    
    file_info = session.get('current_file')
    
    try:
        return send_file(
            file_info['path'],
            as_attachment=True,
            download_name=file_info['name'],
            mimetype='audio/mpeg'  # This will be overridden by the actual file type
        )
    except Exception as e:
        logging.error(f"Error during download: {str(e)}")
        return jsonify({'error': f'Error during download: {str(e)}'}), 500

@app.route('/play')
def play_audio():
    """Stream the current audio file for playback"""
    if 'current_file' not in session:
        return jsonify({'error': 'No file is currently loaded'}), 400
    
    file_info = session.get('current_file')
    
    try:
        return send_file(
            file_info['path'],
            conditional=True
        )
    except Exception as e:
        logging.error(f"Error during audio playback: {str(e)}")
        return jsonify({'error': f'Error during audio playback: {str(e)}'}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
