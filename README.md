# Genome Data Validation Interface

A Streamlit-based GUI for human validation of AI-classified genome data.

## Requirements

- Python 3.13 (recommended for running the application)
- pip (Python package manager)
- Virtual environment (recommended)

## Setup

1. Install Python 3.13:
   - Download from [Python Downloads](https://www.python.org/downloads/)
   - Or use pyenv:
     ```bash
     pyenv install 3.13
     pyenv global 3.13
     ```

2. Create and activate a virtual environment:
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with the following structure:
```
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password
```

5. For Google Sheets integration:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Google Sheets API and Google Drive API
   - Create a service account and download the credentials JSON file
   - Rename the downloaded file to `credentials.json` and place it in the project root directory
   - Share your Google Sheets with the service account email address

6. Run the application:
```bash
# Make sure you're using Python 3.13
python --version  # Should show Python 3.13.x
streamlit run main.py
```

## Troubleshooting

If you encounter any issues:

1. Python Version Issues:
   - Ensure you're using Python 3.13
   - Check your Python version: `python --version`
   - If using a different version, install Python 3.13 and create a new virtual environment

2. Make sure you're using the correct command to run the app:
   - Use `streamlit run main.py` instead of `python main.py`
   - The app should open in your default web browser

3. If you see NumPy warnings:
   - Make sure you've installed all dependencies from requirements.txt
   - Try creating a fresh virtual environment
   - The warnings don't affect functionality and can be safely ignored

4. If the app doesn't start:
   - Check that all dependencies are installed correctly
   - Verify that your `.env` file exists and contains the correct credentials
   - Make sure no other application is using port 8501

5. For Google Sheets issues:
   - Ensure the `credentials.json` file is in the correct location
   - Verify that the Google Sheet is shared with the service account email
   - Check that the Google Sheet has the required columns
   - Make sure the Google Sheet URL is correct and accessible

## Features

- User authentication system
- Session management for continuing previous validations
- Interactive validation interface with:
  - Split-screen display of record information and evidence
  - One-click sentence selection for evidence
  - Progress tracking
  - Detailed logging of validation activities
- Multiple data source support:
  - Excel file upload
  - Google Sheets integration
- Export of validated data to Excel or Google Sheets

## Input File Format

The input file (Excel or Google Sheet) should contain the following columns:
- PMID
- PMCID
- Title
- Abstract
- AI Source Classification (human/microbial/animal/plant/other)
- AI Data Type (original/re-use/mixed)
- Reason (AI's supporting evidence)

## Output

The system generates a new file containing all validated records, including:
- Original AI classifications
- Human validator's agreement/disagreement
- Corrected classifications (if any)
- Human-provided evidence
- Timestamps and validator information 