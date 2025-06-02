import streamlit as st
import pandas as pd
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import json
import bcrypt
import re
import urllib.parse

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), 'credentials.json')
SPREADSHEET_ID = '1FyDt7xu-wTNe0lsLOL_c1dDZZf4gr1jKALIJgciAZqQ'
SHEET_NAME = 'Sample_Human_NH_Original_used_Mixed_Classificaton'
USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')

class GoogleSheetHandler:
    def __init__(self, credentials_path, spreadsheet_id, sheet_name):
        creds = service_account.Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self.service = build('sheets', 'v4', credentials=creds)
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name

    def load_data(self):
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=self.sheet_name
        ).execute()
        values = result.get('values', [])
        if not values:
            return pd.DataFrame()
        df = pd.DataFrame(values[1:], columns=values[0])
        return df

    def add_new_worksheet_and_write(self, df, worksheet_name):
        sheets_api = self.service.spreadsheets()
        worksheet_exists = False

        try:
            result = sheets_api.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{worksheet_name}!A1:Z"
            ).execute()
            values = result.get('values', [])
            if values and 'PMID' in values[0]:
                worksheet_exists = True
                header = values[0]
                existing_rows = values[1:]
                existing_pmids = set(row[header.index('PMID')] for row in existing_rows if len(row) > header.index('PMID'))
                new_rows = df[~df['PMID'].astype(str).isin(existing_pmids)]
                if new_rows.empty:
                    st.info(f"No new responses to add to worksheet: {worksheet_name}")
                    return
                append_values = new_rows.values.tolist()
                sheets_api.values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=worksheet_name,
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body={'values': append_values}
                ).execute()
                st.success(f"Appended {len(append_values)} new rows to worksheet: {worksheet_name}")
                return
        except Exception as e:
            st.warning(f"Could not read worksheet {worksheet_name} (may not exist): {e}")

        if not worksheet_exists:
            add_sheet_request = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': worksheet_name,
                            'gridProperties': {
                                'rowCount': max(1000, len(df) + 10),
                                'columnCount': max(10, len(df.columns) + 2)
                            }
                        }
                    }
                }]
            }
            try:
                sheets_api.batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=add_sheet_request
                ).execute()
                st.success(f"Created new worksheet: {worksheet_name}")
            except Exception as e:
                st.error(f"Sheet creation error: {e}")
                return

            values = [df.columns.values.tolist()] + df.values.tolist()
            body = {'values': values}
            sheets_api.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{worksheet_name}!A1",
                valueInputOption='RAW',
                body=body
            ).execute()
            st.success(f"Wrote all data to worksheet: {worksheet_name}")

    def get_validated_pmids(self, worksheet_name):
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{worksheet_name}!A1:Z"
            ).execute()
            values = result.get('values', [])
            if not values or 'PMID' not in values[0]:
                return set()
            pmid_idx = values[0].index('PMID')
            return set(row[pmid_idx] for row in values[1:] if len(row) > pmid_idx)
        except Exception as e:
            st.warning(f"Could not read worksheet {worksheet_name}: {e}")
            return set()

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def login():
    st.title("Genome Data Validation")

    users = load_users()

    if 'user' not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if username in users and bcrypt.checkpw(password.encode('utf-8'), users[username].encode('utf-8')):
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Invalid username or password")
    else:
        st.write(f"Welcome, {st.session_state.user}!")
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()

def create_clickable_pmid(pmid):
    """Create a clickable PMID that navigates to that record in the GUI"""
    # Use Streamlit's button with a custom key based on the PMID
    return f'<button onclick="window.parent.postMessage({{type: \'streamlit:componentCommunication\', value: {pmid}}}, \'*\')" style="background: none; border: none; color: blue; text-decoration: underline; cursor: pointer;">{pmid}</button>'

def create_clickable_pmcid(pmcid):
    """Create a clickable PMCID that opens PubMed page"""
    if pd.isna(pmcid) or not pmcid:
        return ""
    # Convert PMCID to PMID format if needed (remove PMC prefix)
    pmid = pmcid.replace('PMC', '') if isinstance(pmcid, str) and pmcid.startswith('PMC') else pmcid
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    return f'<a href="{url}" target="_blank">{pmcid}</a>'

def display_records_table(df, cols_to_display):
    """Helper function to display records table with clickable links"""
    if df.empty:
        return
    
    display_df = df.copy()
    
    # Create clickable PMID links
    if 'PMID' in display_df.columns:
        display_df['PMID'] = display_df['PMID'].apply(create_clickable_pmid)
    
    # Create clickable PMCID links if column exists
    if 'PMCID' in display_df.columns:
        display_df['PMCID'] = display_df['PMCID'].apply(create_clickable_pmcid)
    
    # Filter columns that actually exist in the dataframe
    existing_cols = [col for col in cols_to_display if col in display_df.columns]
    
    # Display the table
    st.markdown(display_df[existing_cols].to_html(escape=False, index=False), unsafe_allow_html=True)

def main():
    login()

    if st.session_state.user is None:
        return

    sheet_handler = GoogleSheetHandler(CREDENTIALS_PATH, SPREADSHEET_ID, SHEET_NAME)

    # Load full dataset initially
    full_df = sheet_handler.load_data()

    if full_df.empty:
        st.error("No data found in the spreadsheet")
        return

    st.header("Genome Data Validation")

    # Get validated PMIDs for current user
    worksheet_name = f"Validation_{st.session_state.user}"
    validated_pmids = sheet_handler.get_validated_pmids(worksheet_name)

    # --- Navigation and Record Counts ---
    total_records = full_df.shape[0]
    completed_count = len(validated_pmids)
    remaining_count = total_records - completed_count

    st.subheader("Record Progress")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Records", total_records)
    col2.metric("Completed", completed_count)
    col3.metric("Remaining", remaining_count)

    # Initialize current record index in session state (index in full_df)
    if 'current_record_index' not in st.session_state:
        st.session_state.current_record_index = 0

    # Ensure index is within bounds of the full DataFrame
    if st.session_state.current_record_index >= total_records:
        st.session_state.current_record_index = total_records - 1 if total_records > 0 else 0
    if st.session_state.current_record_index < 0:
         st.session_state.current_record_index = 0

    # Navigation buttons (navigate through full_df)
    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 8]) # Adjust column widths as needed
    with nav_col1:
        if st.button("Previous", disabled=st.session_state.current_record_index == 0):
            st.session_state.current_record_index -= 1
            # Clear existing reason text and used sentences when navigating
            if 'hnh_reason_text' in st.session_state:
                del st.session_state.hnh_reason_text
            if 'hnh_used_sentences' in st.session_state:
                del st.session_state.hnh_used_sentences
            if 'type_reason_text' in st.session_state:
                del st.session_state.type_reason_text
            if 'type_used_sentences' in st.session_state:
                del st.session_state.type_used_sentences
            if 'non_human_subcategories' in st.session_state:
                del st.session_state.non_human_subcategories
            st.rerun()
    with nav_col2:
        if st.button("Next", disabled=st.session_state.current_record_index >= total_records - 1):
            st.session_state.current_record_index += 1
            # Clear existing reason text and used sentences when navigating
            if 'hnh_reason_text' in st.session_state:
                del st.session_state.hnh_reason_text
            if 'hnh_used_sentences' in st.session_state:
                del st.session_state.hnh_used_sentences
            if 'type_reason_text' in st.session_state:
                del st.session_state.type_reason_text
            if 'type_used_sentences' in st.session_state:
                del st.session_state.type_used_sentences
            if 'non_human_subcategories' in st.session_state:
                del st.session_state.non_human_subcategories
            st.rerun()

    # Get the current record based on the index in the full DataFrame
    current_pmid = full_df.iloc[st.session_state.current_record_index]
    current_pmid_value = current_pmid.get('PMID', '')

    st.subheader(f"PMID: {current_pmid_value}")
    st.write("Title:", current_pmid.get('Title', ''))

    # Get original classification and reason, with fallback values if columns don't exist
    original_hnh_class = current_pmid.get('Human_NonHuman_Classification', 'Unclear')
    original_hnh_reason = current_pmid.get('Human_NonHuman_Reason', '')
    original_type = current_pmid.get('Dataset_Type', 'Unclear')
    original_type_reason = current_pmid.get('Dataset_Type_Reason', '')

    # Display original classifications and their reasons
    st.write(f"Original Human/Non-Human Classification: **{original_hnh_class}**")
    if original_hnh_reason:
        st.write(f"Original Human/Non-Human Reason: {original_hnh_reason}")

    st.write(f"Original Dataset Type: **{original_type}**")
    if original_type_reason:
         st.write(f"Original Dataset Type Reason: {original_type_reason}")

    st.write("Abstract:")
    # Split abstract into sentences for selection and display
    abstract = current_pmid.get('Abstract', '')
    # Improved split by common sentence endings. Still basic.
    abstract_sentences = re.split(r'(?<=[.!?])\s+', abstract)
    abstract_sentences = [s.strip() for s in abstract_sentences if s.strip()]

    # Initialize session state for used sentences if not exists (used for highlighting)
    if 'hnh_used_sentences' not in st.session_state:
        st.session_state.hnh_used_sentences = set()
    if 'type_used_sentences' not in st.session_state:
        st.session_state.type_used_sentences = set()

    # Display abstract sentences, highlighting selected ones (bold) and original reasons (colored)
    highlighted_abstract_text = ""
    original_hnh_reason_text_lower = original_hnh_reason.lower()
    original_type_reason_text_lower = original_type_reason.lower()
    
    for sentence in abstract_sentences:
        sentence_lower = sentence.lower()
        
        # Check if sentence is used in either NEW reason text area (bold) - highest priority
        is_used_for_new_reason = sentence in st.session_state.hnh_used_sentences or sentence in st.session_state.type_used_sentences
        
        # Check if sentence is part of ORIGINAL Human/Non-Human reason (blue)
        # Only highlight if the full sentence matches (case-insensitive)
        is_part_of_hnh_original_reason = sentence_lower == original_hnh_reason_text_lower

        # Check if sentence is part of ORIGINAL Dataset Type reason (green)
        # Only highlight if the full sentence matches (case-insensitive)
        is_part_of_type_original_reason = sentence_lower == original_type_reason_text_lower
        
        if is_used_for_new_reason:
            highlighted_abstract_text += f"**{sentence}.** " # Bold for user-selected sentences
        elif is_part_of_hnh_original_reason:
            highlighted_abstract_text += f"<span style=\"color:blue;\">{sentence}.</span> "
        elif is_part_of_type_original_reason:
            highlighted_abstract_text += f"<span style=\"color:green;\">{sentence}.</span> "
        else:
            highlighted_abstract_text += f"{sentence}. "

    st.markdown(highlighted_abstract_text.strip(), unsafe_allow_html=True)

    # --- Validation Interface (Always Visible) ---
    # --- Human/Non-Human Classification ---
    st.subheader("Human/Non-Human Classification")
    hnh_options = ["Human", "Non-Human", "Unclear"]
    hnh_action = st.radio("Action", ["Keep Original", "Change Classification"], key="hnh_action_radio")

    if hnh_action == "Change Classification":
        hnh_new = st.selectbox("New Classification", hnh_options, key="hnh_new_class")

        # Non-Human subcategories
        if hnh_new == "Non-Human":
            non_human_options = ["Plants", "Environmental", "Microbial", "Animal"]
            selected_subcategories = st.multiselect(
                "Select Non-Human Categories",
                options=non_human_options,
                key="non_human_subcategories"
            )

        # Sentence selection for reason
        st.write("Select sentence(s) from the Abstract to add to the reason:")
        selected_hnh_sentence = st.selectbox(
            "Abstract Sentences",
            options=abstract_sentences,
            key="hnh_sentence_select"
        )

        # Initialize session state for HNH reason text
        if 'hnh_reason_text' not in st.session_state:
            st.session_state.hnh_reason_text = ""

        if st.button("Add Selected Sentence to Reason", key="add_hnh_sentence"):
            if selected_hnh_sentence and selected_hnh_sentence not in st.session_state.hnh_used_sentences:
                st.session_state.hnh_used_sentences.add(selected_hnh_sentence)
                if st.session_state.hnh_reason_text:
                    st.session_state.hnh_reason_text += "\n" + selected_hnh_sentence
                else:
                    st.session_state.hnh_reason_text = selected_hnh_sentence
                st.rerun()

        hnh_reason = st.text_area("Reason for Change", value=st.session_state.hnh_reason_text, key="hnh_reason")
    else:
        hnh_new = original_hnh_class
        hnh_reason = original_hnh_reason
        # Clear session state for HNH reason if not changing classification
        if 'hnh_reason_text' in st.session_state:
            del st.session_state.hnh_reason_text
        if 'hnh_used_sentences' in st.session_state:
            del st.session_state.hnh_used_sentences

    # --- Dataset Type Classification ---
    st.subheader("Dataset Type Classification")
    type_options = ["Original", "Used", "Mixed"]
    type_action = st.radio("Action", ["Keep Original", "Change Classification"], key="type_action_radio")

    if type_action == "Change Classification":
        type_new = st.selectbox("New Dataset Type", type_options, key="type_new_class")

        # Sentence selection for reason
        st.write("Select sentence(s) from the Abstract to add to the reason:")
        selected_type_sentence = st.selectbox(
            "Abstract Sentences",
            options=abstract_sentences,
            key="type_sentence_select"
        )

        # Initialize session state for Dataset Type reason text
        if 'type_reason_text' not in st.session_state:
            st.session_state.type_reason_text = ""

        if st.button("Add Selected Sentence to Reason", key="add_type_sentence"):
            if selected_type_sentence and selected_type_sentence not in st.session_state.type_used_sentences:
                st.session_state.type_used_sentences.add(selected_type_sentence)
                if st.session_state.type_reason_text:
                    st.session_state.type_reason_text += "\n" + selected_type_sentence
                else:
                    st.session_state.type_reason_text = selected_type_sentence
                st.rerun()

        type_reason = st.text_area("Reason for Change", value=st.session_state.type_reason_text, key="type_reason")
    else:
        type_new = original_type
        type_reason = original_type_reason
        # Clear session state for Dataset Type reason if not changing classification
        if 'type_reason_text' in st.session_state:
            del st.session_state.type_reason_text
        if 'type_used_sentences' in st.session_state:
            del st.session_state.type_used_sentences

    # --- Save Button ---
    if st.button("Save and Next"):
        # Capture current reason texts from session state before clearing
        hnh_reason_to_save = st.session_state.get('hnh_reason_text', original_hnh_reason) if hnh_action == "Change Classification" else original_hnh_reason
        type_reason_to_save = st.session_state.get('type_reason_text', original_type_reason) if type_action == "Change Classification" else original_type_reason

        response = {
            'user': st.session_state.user,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'PMID': current_pmid_value,
            'Title': current_pmid.get('Title', ''),
            'Abstract': current_pmid.get('Abstract', ''),
            'original_Human_NonHuman_Classification': original_hnh_class,
            'original_Human_NonHuman_Reason': original_hnh_reason,
            'original_Dataset_Type': original_type,
            'original_Dataset_Type_Reason': original_type_reason,
            'hnh_action': hnh_action,
            'hnh_new_classification': hnh_new,
            'hnh_new_reason': hnh_reason_to_save,
            'type_action': type_action,
            'type_new_classification': type_new,
            'type_new_reason': type_reason_to_save
        }

        # Add non-human subcategories if applicable
        if hnh_new == "Non-Human" and 'non_human_subcategories' in st.session_state:
            response['non_human_subcategories'] = ', '.join(st.session_state.non_human_subcategories)

        resp_df = pd.DataFrame([response])
        sheet_handler.add_new_worksheet_and_write(resp_df, worksheet_name)

        # Move to the next record after saving
        st.session_state.current_record_index += 1
        # Ensure index is within bounds of the full DataFrame
        if st.session_state.current_record_index >= total_records:
             st.session_state.current_record_index = total_records - 1 if total_records > 0 else 0
             st.info("You have reached the end of the records.")

        # Clear session state for the next record
        if 'hnh_reason_text' in st.session_state:
            del st.session_state.hnh_reason_text
        if 'hnh_used_sentences' in st.session_state:
            del st.session_state.hnh_used_sentences
        if 'type_reason_text' in st.session_state:
            del st.session_state.type_reason_text
        if 'type_used_sentences' in st.session_state:
            del st.session_state.type_used_sentences
        if 'non_human_subcategories' in st.session_state:
            del st.session_state.non_human_subcategories

        st.rerun() # Rerun to display the next record

    # Initialize session state for PMID navigation if not exists
    if 'navigate_to_pmid' not in st.session_state:
        st.session_state.navigate_to_pmid = None

    # Check if we need to navigate to a specific PMID
    if st.session_state.navigate_to_pmid is not None:
        # Find the index of the PMID in the full dataset
        target_pmid = str(st.session_state.navigate_to_pmid)
        matching_indices = full_df[full_df['PMID'].astype(str) == target_pmid].index
        if not matching_indices.empty:
            st.session_state.current_record_index = matching_indices[0]
            st.session_state.navigate_to_pmid = None  # Reset the navigation flag
            st.rerun()
        else:
            st.warning(f"Could not find PMID {target_pmid} in the dataset")
            st.session_state.navigate_to_pmid = None

    # --- Show Progress Button and Display ---
    if st.button("Show Progress"):
        st.session_state.show_progress = not st.session_state.get("show_progress", False)

    if st.session_state.get("show_progress", False):
        with st.expander("Progress Details"):
            st.subheader("Completed Records")
            if completed_count > 0:
                # Read completed records from the user's validation sheet
                completed_records_df = sheet_handler.load_data_from_worksheet(worksheet_name)
                if not completed_records_df.empty:
                    # Display records with clickable links
                    display_records_table(completed_records_df, ['PMID', 'Title', 'PMCID'])
                else:
                    st.write("No records completed yet.")

            st.subheader("Remaining Records")
            if remaining_count > 0:
                # Filter full_df for records not in validated_pmids
                remaining_records_df = full_df[~full_df['PMID'].astype(str).isin(validated_pmids)].copy()
                
                # Display records with clickable links
                display_records_table(remaining_records_df, ['PMID', 'Title', 'PMCID'])
            else:
                st.write("All records completed.")

    # Add JavaScript to handle PMID navigation
    st.markdown("""
        <script>
            window.addEventListener('message', function(e) {
                if (e.data.type === 'streamlit:componentCommunication') {
                    // Send the PMID to Streamlit
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        value: e.data.value
                    }, '*');
                }
            });
        </script>
    """, unsafe_allow_html=True)

# Add a helper function to GoogleSheetHandler to load data from a specific worksheet
# This assumes the worksheet has a header row
if not hasattr(GoogleSheetHandler, 'load_data_from_worksheet'):
    def load_data_from_worksheet(self, worksheet_name):
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{worksheet_name}!A1:Z"
            ).execute()
            values = result.get('values', [])
            if not values:
                return pd.DataFrame()
            df = pd.DataFrame(values[1:], columns=values[0])
            return df
        except Exception as e:
            st.warning(f"Could not read worksheet {worksheet_name}: {e}")
            return pd.DataFrame()
    GoogleSheetHandler.load_data_from_worksheet = load_data_from_worksheet

if __name__ == "__main__":
    main()