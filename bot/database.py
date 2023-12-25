import sqlite3
import utils
import logging

args, config = utils.general_setup()

con = sqlite3.connect(config["db_path"])
cur = con.cursor()

def insert_participant(email, first_name, last_name, discord_id):
    '''
    Insert participant data into Participants table. Performs no checks.
    '''
    cur.execute("INSERT INTO Participants VALUES (?, ?, ?, ?);", (email, first_name, last_name, discord_id))
    con.commit()
    logging.info(f"Database: Added participant to database: {email}, {first_name}, {last_name}, {discord_id}")


def check_if_verified(email, first_name, last_name, discord_id):
    '''
    Should be run before inserting a new participant; checks if the participant's email is already used,
    or if the discord account is already used.
    '''

    # check if someone's already verified their account as this participant
    cur.execute("SELECT * FROM Participants WHERE email = ?;", (email,))
    match_email = cur.fetchall()
    logging.info(f"Database: Found {len(match_email)} participants matching email {email}: {match_email}")

    # check if this account has already been verified
    cur.execute("SELECT * FROM Participants WHERE discord_id = ?;", (discord_id,))
    match_discord = cur.fetchall()
    logging.info(f"Database: Found {len(match_discord)} participants matching discord id {discord_id}: {match_discord}")

    if match_email:
        return "email"
    elif match_discord:
        return "discord"
    else:
        return False