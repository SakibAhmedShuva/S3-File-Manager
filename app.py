from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import boto3
from botocore.exceptions import ClientError
import os
from werkzeug.utils import secure_filename
import mimetypes
import base64
from io import BytesIO
from PIL import Image

app = Flask(__name__)
CORS(app)

s3_client = None
bucket_name = None

def init_s3_client(access_key, secret_key, region):
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
    """Generate a thumbnail for image files"""
    try:
        with Image.open(file_path) as img:
            img.thumbnail(max_size)
            buffered = BytesIO()
            img.save(buffered, format=img.format)
            return base64.b64encode(buffered.getvalue()).decode()
    except Exception:
        return None

def upload_to_s3(file_path, s3_key, make_public=False, expires_in=3600):
    """Upload a file to S3 and return a pre-signed URL or public URL."""
    try:
        extra_args = {'ACL': 'public-read'} if make_public else {}
        
        # Add content type detection
        content_type = mimetypes.guess_type(file_path)[0]
        if content_type:
            extra_args['ContentType'] = content_type
        
        s3_client.upload_file(
            file_path, 
            bucket_name, 
            s3_key,
            ExtraArgs=extra_args
        )
        
        if make_public:
            url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        else:
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': s3_key},
                ExpiresIn=int(expires_in)
            )
            
        # Generate thumbnail for images and videos
        thumbnail = None
        if content_type and content_type.startswith(('image/', 'video/')):
            thumbnail = generate_thumbnail(file_path)
            
        return url, thumbnail
    except Exception as e:
        raise Exception(f"Error uploading to S3: {str(e)}")

def list_s3_files(expires_in=3600):
    """List all files in the S3 bucket."""
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                # Check if the object is public by getting its ACL
                try:
                    acl_response = s3_client.get_object_acl(Bucket=bucket_name, Key=obj['Key'])
                    is_public = any(
                        grant['Grantee'].get('URI') == 'http://acs.amazonaws.com/groups/global/AllUsers' 
                        and grant['Permission'] in ['READ', 'FULL_CONTROL']
                        for grant in acl_response['Grants']
                    )
                except:
                    is_public = False

                # Generate the appropriate URL based on whether the object is public
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
                
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'url': url,
                    'content_type': content_type,
                    'isPublic': is_public  # Add this field to indicate if the file is public
                })
        return files
    except Exception as e:
        raise Exception(f"Error listing S3 files: {str(e)}")

@app.route('/configure', methods=['POST'])
def configure():
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
    if not s3_client:
        return jsonify({"error": "S3 not configured"}), 400
    try:
        expires_in = request.args.get('expires_in', 3600)
        files = list_s3_files(expires_in)
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    try:
        filename = secure_filename(file.filename)
        # Use os.path.join with normalized separators
        temp_path = os.path.normpath(os.path.join(os.path.dirname(__file__), 'tmp', filename))
        
        # Ensure tmp directory exists
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        file.save(temp_path)
        
        make_public = request.form.get('public') == 'true'
        expires_in = request.form.get('expires_in', 3600)
        url, thumbnail = upload_to_s3(temp_path, filename, make_public, expires_in)
        
        os.remove(temp_path)  # Clean up temporary file
        
        return jsonify({
            "message": "File uploaded successfully",
            "url": url,
            "thumbnail": thumbnail
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/delete', methods=['POST'])
def delete_file():
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

@app.route('/delete-all', methods=['POST'])
def delete_all_files():
    if not s3_client:
        return jsonify({"error": "S3 not configured"}), 400
        
    data = request.json
    captcha = data.get('captcha')
    expected_captcha = data.get('expected_captcha')
    
    if not captcha or not expected_captcha:
        return jsonify({"error": "CAPTCHA verification required"}), 400
        
    if captcha.lower() != expected_captcha.lower():
        return jsonify({"error": "Invalid CAPTCHA"}), 400
        
    try:
        # List all objects in the bucket
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            # Create list of objects to delete
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
            
            # Delete all objects
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

if __name__ == '__main__':
    app.run(port=5006, debug=True)