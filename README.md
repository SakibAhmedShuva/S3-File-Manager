# S3 File Manager

A web-based file management interface for Amazon S3 buckets, built with Flask and vanilla JavaScript. This application provides an intuitive way to manage files in your S3 bucket, including uploading, downloading, and deleting files.

## 🚀 Features

- **S3 Bucket Configuration**
  - Easy setup with AWS credentials
  - Support for different regions
  - Secure credential handling
  - Persistent session management

- **File Management**
  - Upload files to S3
  - Generate presigned URLs for private files
  - Public/Private file access control
  - Individual file deletion
  - Bulk delete all files with CAPTCHA verification
  - List all files with details
  - Thumbnail preview for images and videos

- **Advanced File Listing**
  - Sort files by:
    - Name
    - Date Modified
    - Size
    - File Type
  - Ascending/Descending sort order
  - Real-time list refresh without losing session
  - File metadata display

- **User Interface**
  - Clean and responsive design
  - File preview capabilities
  - Copy shareable links
  - CAPTCHA security for destructive operations
  - Real-time status updates
  - Refresh button for file list

## 🛠️ Installation

1. Clone the repository:
```bash
git clone https://github.com/SakibAhmedShuva/S3-File-Manager.git
cd S3-File-Manager
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

3. Run the Flask application:
```bash
python app.py
```

4. Open `app.html` in your web browser or serve it through a web server.

## ⚙️ Configuration

Before using the application, you'll need:
- AWS Access Key
- AWS Secret Key
- S3 Bucket Name
- AWS Region

Enter these details in the configuration form when you first launch the application.

## 🔧 Usage

1. **Initial Setup**
   - Fill in your AWS credentials in the configuration form
   - Click "Connect to S3" to establish connection

2. **Uploading Files**
   - Select a file using the file input
   - Choose between public or private access
   - Set expiration time for private files
   - Click "Upload" to send file to S3

3. **Managing Files**
   - View all files in your bucket
   - Sort files using various criteria
   - Download files directly
   - Copy shareable links
   - Delete individual files
   - Preview images and videos

4. **Bulk Operations**
   - Delete all files with CAPTCHA verification
   - Refresh file list to see updates
   - Sort files by different parameters

## 🔒 Security Features

- AWS credentials are handled server-side
- Support for both public and private file access
- Configurable expiration times for presigned URLs
- CAPTCHA verification for bulk delete operations
- Secure file handling with proper mime-type detection

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Sakib Ahmed Shuva**
- GitHub: [@SakibAhmedShuva](https://github.com/SakibAhmedShuva)

## ⭐️ Show your support

Give a ⭐️ if this project helped you!

## 📄 Requirements

- Python 3.6+
- Flask
- boto3
- Pillow
- Flask-CORS
- Web browser with JavaScript enabled

## Known Issues

Please check the [Issues](https://github.com/SakibAhmedShuva/S3-File-Manager/issues) page for current known issues and feature requests.

## Recent Updates

- Added bulk delete functionality with CAPTCHA verification
- Implemented file sorting capabilities
- Added real-time file list refresh feature
- Improved session management
- Enhanced UI with better feedback and controls
