import gspread
import pandas as pd
import logging
import utils

args, config = utils.general_setup()


def reload_values():
    '''
    Open a connection to the Google Sheet and load the relevant information as a DataFrame.
    '''
    
    account = gspread.service_account(filename="./google_service_account.json")
    sheet = account.open_by_key(config["registration_form_key"])

    # only want email and name, and not the sensitive info ones...
    cell_vals = sheet.get_worksheet(0).get("B:D")
    df = pd.DataFrame(cell_vals[1:], columns=cell_vals[0])

    del account, sheet, cell_vals # im like really paranoid

    logging.info("")

    return df


def check_if_registered(email, first_name, last_name):
    '''
    Check if a person has registered.
    '''
    
    df = reload_values() # this will be live while people are still registering (scary)

    res = df[ (df['Email Address'] == email) & (df['First Name'] == first_name) & (df['Last Name'] == last_name) ]

    if len(res) == 0:
        return False
    else:
        return True