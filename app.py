# Import required libraries
from flask import Flask, request, jsonify, send_file  # Flask web framework components
from flask_cors import CORS  # Cross-Origin Resource Sharing support
import boto3  # AWS SDK for Python
from botocore.exceptions import ClientError  # AWS specific exceptions
import os  # Operating system interface
from werkzeug.utils import secure_filename  # Secure file handling
import mimetypes  # File type detection
import base64  # Base64 encoding/decoding
from io import BytesIO  # In-memory binary streams
from PIL import Image  # Python Imaging Library for image processing

# Initialize Flask application with CORS support
app = Flask(__name__)
CORS(app)

# Global variables for S3 client and bucket name
s3_client = None
bucket_name = None

def init_s3_client(access_key, secret_key, region):
    """
    Initialize the S3 client with provided AWS credentials
    Returns True if successful, error response if failed
    """
    global s3_client
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        return True
    except Exception as e:
        return {"error": str(e)}, 400

def generate_thumbnail(file_path, max_size=(100, 100)):
    """
    Generate a thumbnail for image files
    Returns base64 encoded thumbnail or None if generation fails
    Parameters:
        file_path: Path to the image file
        max_size: Maximum dimensions for thumbnail (width, height)
    """
    try:
        with Image.open(file_path) as img:
            img.thumbnail(max_size)
            buffered = BytesIO()
            img.save(buffered, format=img.format)
            return base64.b64encode(buffered.getvalue()).decode()
    except Exception:
        return None

def upload_to_s3(file_path, s3_key, make_public=False, expires_in=3600):
    """
    Upload a file to S3 and generate appropriate access URL
    Parameters:
        file_path: Local path to file
        s3_key: Desired key (path) in S3
        make_public: Boolean to make file publicly accessible
        expires_in: Expiration time for presigned URLs in seconds
    Returns:
        Tuple of (URL, thumbnail)
    """
    try:
        # Set up extra arguments for upload
        extra_args = {'ACL': 'public-read'} if make_public else {}
        
        # Detect and set content type
        content_type = mimetypes.guess_type(file_path)[0]
        if content_type:
            extra_args['ContentType'] = content_type
        
        # Upload file to S3
        s3_client.upload_file(
            file_path, 
            bucket_name, 
            s3_key,
            ExtraArgs=extra_args
        )
        
        # Generate appropriate URL based on public/private setting
        if make_public:
            url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        else:
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': s3_key},
                ExpiresIn=int(expires_in)
            )
            
        # Generate thumbnail for media files
        thumbnail = None
        if content_type and content_type.startswith(('image/', 'video/')):
            thumbnail = generate_thumbnail(file_path)
            
        return url, thumbnail
    except Exception as e:
        raise Exception(f"Error uploading to S3: {str(e)}")

def list_s3_files(expires_in=3600):
    """
    List all files in the S3 bucket with their metadata
    Parameters:
        expires_in: Expiration time for presigned URLs in seconds
    Returns:
        List of dictionaries containing file metadata
    """
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                # Check object's public/private status
                try:
                    acl_response = s3_client.get_object_acl(Bucket=bucket_name, Key=obj['Key'])
                    is_public = any(
                        grant['Grantee'].get('URI') == 'http://acs.amazonaws.com/groups/global/AllUsers' 
                        and grant['Permission'] in ['READ', 'FULL_CONTROL']
                        for grant in acl_response['Grants']
                    )
                except:
                    is_public = False

                # Generate appropriate URL
                if is_public:
                    url = f"https://{bucket_name}.s3.amazonaws.com/{obj['Key']}"
                else:
                    url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': obj['Key']},
                        ExpiresIn=int(expires_in)
                    )
                
                # Get content type
                try:
                    head = s3_client.head_object(Bucket=bucket_name, Key=obj['Key'])
                    content_type = head.get('ContentType', '')
                except:
                    content_type = mimetypes.guess_type(obj['Key'])[0] or ''
                
                # Compile file metadata
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'url': url,
                    'content_type': content_type,
                    'isPublic': is_public
                })
        return files
    except Exception as e:
        raise Exception(f"Error listing S3 files: {str(e)}")

# API Routes

@app.route('/configure', methods=['POST'])
def configure():
    """Configure S3 client with provided credentials"""
    global bucket_name
    data = request.json
    bucket_name = data.get('bucket_name')
    region = data.get('region')
    access_key = data.get('access_key')
    secret_key = data.get('secret_key')
    
    if init_s3_client(access_key, secret_key, region):
        return jsonify({"message": "Successfully connected to S3!"})
    else:
        return jsonify({"error": "Failed to connect to S3"}), 400

@app.route('/files', methods=['GET'])
def list_files():
    """List all files in the configured S3 bucket"""
    if not s3_client:
        return jsonify({"error": "S3 not configured"}), 400
    try:
        expires_in = request.args.get('expires_in', 3600)
        files = list_s3_files(expires_in)
        print("Files returned:", files)  # Debug log
        return jsonify(files)
    except Exception as e:
        print("Error in list_files:", str(e))  # Debug log
        return jsonify({"error": str(e)}), 400

@app.route('/create-folder', methods=['POST'])
def create_folder():
    """Create a new folder (prefix) in S3"""
    if not s3_client:
        return jsonify({"error": "S3 not configured"}), 400
        
    data = request.json
    path = data.get('path', '').strip('/')
    
    if not path:
        return jsonify({"error": "No folder path provided"}), 400
        
    try:
        # Create empty object with trailing slash
        s3_client.put_object(Bucket=bucket_name, Key=f"{path}/")
        return jsonify({"message": f"Folder {path} created successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/upload', methods=['POST'])
def upload():
    """
    Handle file uploads to S3
    Supports folder paths, public/private access, and generates thumbnails for media
    """
    if not s3_client:
        return jsonify({"error": "S3 not configured"}), 400

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    folder_path = request.form.get('folder_path', '').strip('/')
    
    try:
        # Secure the filename
        filename = secure_filename(file.filename)
        
        # Build full S3 key
        s3_key = f"{folder_path}/{filename}" if folder_path else filename
        
        # Create temporary file
        temp_path = os.path.normpath(os.path.join(os.path.dirname(__file__), 'tmp', filename))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        file.save(temp_path)
        
        # Get upload settings
        make_public = request.form.get('public') == 'true'
        expires_in = request.form.get('expires_in', 3600)
        
        # Create folder if needed
        if folder_path:
            try:
                s3_client.head_object(Bucket=bucket_name, Key=f"{folder_path}/")
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    s3_client.put_object(Bucket=bucket_name, Key=f"{folder_path}/")
        
        # Upload and get URL/thumbnail
        url, thumbnail = upload_to_s3(temp_path, s3_key, make_public, expires_in)
        
        # Clean up
        os.remove(temp_path)
        
        return jsonify({
            "message": "File uploaded successfully",
            "url": url,
            "key": s3_key,
            "folder": folder_path,
            "thumbnail": thumbnail
        })
        
    except Exception as e:
        # Clean up on error
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"error": str(e)}), 400
    
@app.route('/delete', methods=['POST'])
def delete_file():
    """Delete a single file from S3"""
    if not s3_client:
        return jsonify({"error": "S3 not configured"}), 400
        
    data = request.json
    key = data.get('key')
    
    if not key:
        return jsonify({"error": "No file key provided"}), 400
        
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=key)
        return jsonify({"message": f"File {key} deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/delete-folder', methods=['POST'])
def delete_folder():
    """
    Delete a folder and all its contents from S3
    Handles pagination for folders with many objects
    """
    if not s3_client:
        return jsonify({"error": "S3 not configured"}), 400
        
    data = request.json
    folder_path = data.get('path', '').strip('/')
    
    if not folder_path:
        return jsonify({"error": "No folder path provided"}), 400
        
    try:
        # Get paginator for handling large folders
        paginator = s3_client.get_paginator('list_objects_v2')
        objects_to_delete = []
        
        # Collect all objects in folder
        for page in paginator.paginate(Bucket=bucket_name, Prefix=f"{folder_path}/"):
            if 'Contents' in page:
                objects_to_delete.extend(
                    {'Key': obj['Key']} for obj in page['Contents']
                )
        
        if objects_to_delete:
            # Delete in batches of 1000 (S3 limit)
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i:i + 1000]
                s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={
                        'Objects': batch,
                        'Quiet': True
                    }
                )
            
            return jsonify({
                "message": f"Folder {folder_path} and its contents ({len(objects_to_delete)} objects) deleted successfully"
            })
        else:
            return jsonify({
                "message": f"Folder {folder_path} was empty or didn't exist"
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/delete-all', methods=['POST'])
def delete_all_files():
    """
    Delete all files in the bucket
    Requires CAPTCHA verification for safety
    """
    if not s3_client:
        return jsonify({"error": "S3 not configured"}), 400
        
    data = request.json
    captcha = data.get('captcha')
    expected_captcha = data.get('expected_captcha')
    
    # Verify CAPTCHA
    if not captcha or not expected_captcha:
        return jsonify({"error": "CAPTCHA verification required"}), 400
        
    if captcha.lower() != expected_captcha.lower():
        return jsonify({"error": "Invalid CAPTCHA"}), 400
        
    try:
        # List and delete all objects
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
            
            s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={
                    'Objects': objects_to_delete,
                    'Quiet': True
                }
            )
            
            return jsonify({
                "message": f"Successfully deleted {len(objects_to_delete)} files",
                "count": len(objects_to_delete)
            })
        return jsonify({"message": "No files to delete"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Run the Flask application
if __name__ == '__main__':
    app.run(port=5006, debug=True)