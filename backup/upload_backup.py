'''
Script to upload a file to Google Drive, in our Platform/Database Backups folder.

https://ragug.medium.com/how-to-upload-files-using-the-google-drive-api-in-python-ebefdfd63eab
https://medium.com/@raselkabircse/uploading-a-file-to-google-drive-using-python-34e111d3912c
'''

import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import googleapiclient
from datetime import datetime
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--file_path", required=True)
parser.add_argument("-s", "--service_account", required=True)
args = parser.parse_args()

# https://ragug.medium.com/how-to-upload-files-using-the-google-drive-api-in-python-ebefdfd63eab
# https://medium.com/@raselkabircse/uploading-a-file-to-google-drive-using-python-34e111d3912c

# Define the Google Drive API scopes and service account file path
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = "/home/castorsh3m/HackED_Bots/google_service_account.json"
FOLDER_ID = "1kfRU10N7n_MDSOqnUmQDqnip8-Jhg5pE"

# Create credentials using the service account file
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Build the Google Drive service
drive_service = build('drive', 'v3', credentials=credentials)

# Upload file
file_metadata = {
    'name': os.path.basename(args.file_path),
    'parents': [FOLDER_ID]
}
media = googleapiclient.http.MediaFileUpload(args.file_path, resumable=True)
uploaded_file = drive_service.files().create(
    body=file_metadata,
    media_body=media,
    fields='id'
).execute()

print(f"File uploaded with ID: {uploaded_file['id']}")