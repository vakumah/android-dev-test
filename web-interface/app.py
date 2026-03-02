#!/usr/bin/env python3
import os
import subprocess
from flask import Flask, render_template, request, jsonify, send_from_directory, Response
from werkzeug.utils import secure_filename
import threading
import time
import requests

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/apks'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ADB device
ADB_DEVICE = "localhost:5555"
SCRCPY_URL = "http://localhost:8000"

def run_command(cmd):
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'flask': 'running',
        'port': 8080
    })

@app.route('/scrcpy/')
@app.route('/scrcpy/<path:path>')
def proxy_scrcpy(path=''):
    """Proxy scrcpy web interface"""
    try:
        url = f"{SCRCPY_URL}/{path}"
        
        # Forward request
        resp = requests.request(
            method=request.method,
            url=url,
            headers={key: value for (key, value) in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True,
            timeout=10
        )
        
        # Forward response
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]
        
        return Response(resp.content, resp.status_code, headers)
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Scrcpy not available yet, please wait...'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/device/status')
def device_status():
    """Get device status"""
    result = run_command(f'adb devices | grep {ADB_DEVICE}')
    is_online = 'device' in result.get('output', '')
    
    if is_online:
        android_version = run_command(f'adb -s {ADB_DEVICE} shell getprop ro.build.version.release')
        model = run_command(f'adb -s {ADB_DEVICE} shell getprop ro.product.model')
        cpu_abi = run_command(f'adb -s {ADB_DEVICE} shell getprop ro.product.cpu.abi')
        
        return jsonify({
            'online': True,
            'android_version': android_version.get('output', '').strip(),
            'model': model.get('output', '').strip(),
            'cpu_abi': cpu_abi.get('output', '').strip()
        })
    else:
        return jsonify({'online': False})

@app.route('/api/packages')
def list_packages():
    """List installed packages"""
    result = run_command(f'adb -s {ADB_DEVICE} shell pm list packages -3')
    if result['success']:
        packages = [line.replace('package:', '') for line in result['output'].strip().split('\n') if line]
        return jsonify({'success': True, 'packages': packages})
    return jsonify({'success': False, 'error': result.get('error', 'Failed to list packages')})

@app.route('/api/upload', methods=['POST'])
def upload_apk():
    """Upload and install APK"""
    if 'apk' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    
    file = request.files['apk']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    if not file.filename.endswith('.apk'):
        return jsonify({'success': False, 'error': 'File must be .apk'})
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Install APK
    result = run_command(f'adb -s {ADB_DEVICE} install -r "{filepath}"')
    
    # Clean up
    try:
        os.remove(filepath)
    except:
        pass
    
    if result['success'] or 'Success' in result.get('output', ''):
        return jsonify({'success': True, 'message': 'APK installed successfully'})
    else:
        return jsonify({'success': False, 'error': result.get('error', 'Installation failed')})

@app.route('/api/uninstall', methods=['POST'])
def uninstall_package():
    """Uninstall package"""
    data = request.json
    package = data.get('package')
    
    if not package:
        return jsonify({'success': False, 'error': 'Package name required'})
    
    result = run_command(f'adb -s {ADB_DEVICE} uninstall {package}')
    
    if result['success'] or 'Success' in result.get('output', ''):
        return jsonify({'success': True, 'message': f'Uninstalled {package}'})
    else:
        return jsonify({'success': False, 'error': result.get('error', 'Uninstall failed')})

@app.route('/api/launch', methods=['POST'])
def launch_app():
    """Launch app"""
    data = request.json
    package = data.get('package')
    
    if not package:
        return jsonify({'success': False, 'error': 'Package name required'})
    
    result = run_command(f'adb -s {ADB_DEVICE} shell monkey -p {package} -c android.intent.category.LAUNCHER 1')
    
    if result['success']:
        return jsonify({'success': True, 'message': f'Launched {package}'})
    else:
        return jsonify({'success': False, 'error': result.get('error', 'Launch failed')})

@app.route('/api/screenshot')
def screenshot():
    """Take screenshot"""
    timestamp = int(time.time())
    filename = f'screenshot_{timestamp}.png'
    filepath = f'/tmp/{filename}'
    
    # Take screenshot
    run_command(f'adb -s {ADB_DEVICE} shell screencap -p /sdcard/screen.png')
    result = run_command(f'adb -s {ADB_DEVICE} pull /sdcard/screen.png {filepath}')
    
    if result['success'] and os.path.exists(filepath):
        return send_from_directory('/tmp', filename, as_attachment=True)
    else:
        return jsonify({'success': False, 'error': 'Screenshot failed'})

@app.route('/api/shell', methods=['POST'])
def shell_command():
    """Execute shell command"""
    data = request.json
    command = data.get('command', '')
    
    if not command:
        return jsonify({'success': False, 'error': 'Command required'})
    
    result = run_command(f'adb -s {ADB_DEVICE} shell {command}')
    return jsonify({
        'success': result['success'],
        'output': result.get('output', ''),
        'error': result.get('error', '')
    })

@app.route('/api/logcat')
def logcat():
    """Get logcat output"""
    result = run_command(f'adb -s {ADB_DEVICE} logcat -d -t 100')
    return jsonify({
        'success': result['success'],
        'output': result.get('output', ''),
        'error': result.get('error', '')
    })

@app.route('/api/clear-logcat', methods=['POST'])
def clear_logcat():
    """Clear logcat"""
    result = run_command(f'adb -s {ADB_DEVICE} logcat -c')
    return jsonify({'success': result['success']})

if __name__ == '__main__':
    print("=" * 50)
    print("Starting Flask Web Interface")
    print("Port: 8080")
    print("=" * 50)
    try:
        app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
    except Exception as e:
        print(f"ERROR: Failed to start Flask: {e}")
        import traceback
        traceback.print_exc()
