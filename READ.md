# Google Drive Manager

This application manages files and folders on Google Drive by performing recursive copy operations and automatically monitoring folders to copy new files and subfolders. Additionally, it allows you to cancel all operations by deleting all objects that were copied via the AddMonitor process. Detailed log messages provide insight into which monitor tasks and objects are being cancelled and deleted.

## Features

- **Copy**: Recursively copies files and subfolders from one folder to another.
- **Monitor / AddMonitor / RemoveMonitor**: Creates and removes monitor tasks that automatically copy new objects (files and subfolders) from a source folder.
- **Report**: Displays a detailed change log report with timestamps and operation details.
- **SetPermissions**: Updates file or folder permissions.
- **Cancel All Operations**: Deletes all objects that were copied via the AddMonitor process and clears all monitor tasks. The application logs detailed progress for each deletion.

## Project Structure

project/ ├── config.py # Configuration (Service Account file path and Google Root ID) ├── drive_service.py # Module for interacting with the Google Drive API (supports Shared Drives and recursive operations) ├── gui.py # Graphical user interface ├── monitor_tasks.json # JSON file to store monitor tasks (paths and IDs of copied objects) ├── changes_log.json # JSON file to store the change log ├── requirements.txt # List of dependencies └── read.md # This project description

markdown
نسخ

## Setup

1. **Clone the Project**  
   Clone the repository or download the source code into your local environment.

2. **Install Dependencies**  
   Install all required Python packages using pip:
   ```bash
   pip install -r requirements.txt
Configure the Google Drive API

Create a project in the Google Cloud Console.

Enable the Google Drive API via APIs & Services → Library.

Create a Service Account:

Go to APIs & Services → Credentials.

Click Create Credentials and select Service Account.

Fill in the necessary details and assign an appropriate role (e.g., Editor).

After creating the account, navigate to the Keys tab and click Add Key → Create new key (JSON format).

Rename the downloaded JSON file to credentials.json and place it in the project root directory.

Configure Project Settings
Open config.py and verify that the GOOGLE_ROOT_ID is set as needed (default is "root").

Running the Application
Launch the application by executing:

bash
نسخ
python gui.py
The GUI window will open with buttons for the various operations:

Copy – Recursively copy files and subfolders from a source folder to a destination folder.

Monitor / AddMonitor / RemoveMonitor – Manage monitor tasks for automatic copying of new objects.

Report – View a full change log report.

SetPermissions – Change file or folder permissions.

Cancel All Operations – Delete all objects copied via AddMonitor and clear monitor tasks; detailed progress is shown in the log area.

Usage
Copy:
Enter the source and destination folder URLs. The application will recursively copy all files and subfolders and log the total number of objects copied.

AddMonitor:
Creates a monitor task by performing an initial copy and then monitoring the source folder for new objects. If a task already exists for the specified source and destination, it will not be recreated.

RemoveMonitor:
Removes an existing monitor task by providing the source and destination folder URLs.

Report:
Opens a window displaying a complete change log with timestamps, operation types, and file/folder details.

SetPermissions:
Allows you to change the permissions for a file or folder by entering the URL, user email, and the desired role (reader, writer, or owner).

Cancel All Operations:
Deletes all objects that were copied via monitor tasks and clears all monitor tasks. Detailed messages are logged during the deletion process to indicate which objects and tasks are being cancelled.

Notes
Data Files:
If monitor_tasks.json or changes_log.json do not exist, they will be automatically created on the first run.

Error Handling:
The application uses the tenacity library to retry operations (such as copying or deletion) in case of transient errors. Detailed error messages are displayed in the log area.

Permissions:
Ensure that the Service Account has sufficient permissions on Google Drive. The relevant folders must be shared with the Service Account's email address.
For Shared Drives, verify that the Service Account has an appropriate role (e.g., Content Manager or Editor).

Invalid IDs:
If the copy operation does not save correct IDs in monitor tasks (for example, if it stores the literal "file"), the cancel operation will skip those entries. The best approach is to ensure that the copy function returns a valid ID for each file.

Manual Cleanup:
If monitor tasks contain incorrect data, you might need to manually adjust monitor_tasks.json or perform additional cleanup via the Google Drive interface.

Google API and Service Account Reference
For further details on setting up the Google Drive API and Service Accounts, refer to the Google Developers documentation.
