import gspread
import pandas as pd
import logging
import utils

args, config = utils.general_setup()

account = gspread.service_account(filename="./google_service_account.json")
sheet = account.open_by_key(config["registration_form_key"])

def reload_values():
    '''
    Open a connection to the Google Sheet and load the relevant information as a DataFrame.
    '''
    
    worksheet = sheet.get_worksheet(0)

    # get email and name columns
    info_cols = worksheet.get("B:D")
    # go to elaborate lengths to avoid querying the sensitive personal info columns
    discord_col = worksheet.get(f"AH1:AH{len(info_cols)}", maintain_size=True)

    df = pd.DataFrame(info_cols[1:], columns=info_cols[0]) # make df
    df = df.map(lambda x: x.strip().lower()) # make matching easier

    df[ discord_col[0] ] = discord_col[1:] # concatenate discord info to column

    return df


def check_if_registered(email, first_name, last_name):
    '''
    Check if a person has registered in the registration sheet.
    '''
    
    df = reload_values() # this will be live while people are still registering (scary)

    res = df[ (df['Email Address'] == email) & (df['First Name'] == first_name) & (df['Last Name'] == last_name) ]

    # participant not registered
    if len(res) == 0:
        return False
    
    # participant submitted the form more than once; this is ok, but should warn
    if len(res) > 1:
        logging.warning(f"Participant ({email}, {first_name}, {last_name}) appears {len(res)} times in registration sheet.")

    return True


def check_if_verified(email, first_name, last_name, discord_id):
    '''
    Check if a participant has already been verified in the registration sheet.
    '''
    
    df = reload_values()
    res = df[ (df['Email Address'] == email) & (df['First Name'] == first_name) & (df['Last Name'] == last_name) ]

    # if any of multiple entries checked, assume verified...
    if any(res['Discord ID'] != ""):
        logging.info(f"Sheet: Participant ({email}, {first_name}, {last_name}) already registered with some discord ID.")
        return "email" # i.e. email has already been verified with some discord account
    
    res = df[ df['Discord ID'] == str(discord_id) ]
    if len(res) != 0:
        logging.info(f"Sheet: Discord ID {discord_id} already used for another participant.")
        return "discord" # i.e. discord id has already been used to verify a user
    
    return False


def verify(email, first_name, last_name, discord_id):
    '''
    Edit the spreadsheet to verify the participant (add their Discord ID to the right column).
    Should check if registered first, because this function does not.
    '''

    df = reload_values()
    res = df[ (df['Email Address'] == email) & (df['First Name'] == first_name) & (df['Last Name'] == last_name) ]

    if len(res.index) == 0:
        logging.error(f"Tried to verify participant ({email}, {first_name}, {last_name}, {discord_id}) in sheet, but no results that match.")
        return False

    for i in range(len(res.index)):
        # row index is df index + 1 (for sheet header) + 1 (for one-indexed rows)
        cell = f"AH{res.index[i].astype(int) + 2}"
        sheet.get_worksheet(0).update(cell, str(discord_id))

        logging.info(f"Updated cell {cell} to verify participant ({email}, {first_name}, {last_name}, {discord_id})")
        return True