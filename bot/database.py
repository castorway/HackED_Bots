import sqlite3
import utils
import logging
import discord
from discord.utils import get as dget
from declare_cog import challenge_order

args, config = utils.general_setup()

con = sqlite3.connect(config["db_path"])
cur = con.cursor()

# set up
cur.execute("PRAGMA foreign_keys = ON;")
con.commit()

def insert_participant(email, first_name, last_name, discord_id):
    '''
    Insert participant data into Participants table. Performs no checks.
    '''
    cur.execute("INSERT INTO Participants VALUES (?, ?, ?, ?, ?);", (email, first_name, last_name, discord_id, None))
    con.commit()
    logging.info(f"Database: Added participant to database: {email}, {first_name}, {last_name}, {discord_id}, None")


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
    

def is_on_team(member: discord.Member):
    '''
    Check if a participant identified as a discord.Member object is on a team.
    '''
    # get participant's email
    cur.execute("SELECT team_name FROM Participants WHERE discord_id = ?;", (member.id,))
    matches = cur.fetchall()

    # if we have multiple participants with same id, this is a Problem (but should not happen due to other checks)
    if len(matches) > 1:
        logging.error(f"Database: Multiple participants in Participants table match discord_id={member.id}. Using one with email={matches[0][0]}")
        return matches[0][0] != None # if team_name == None, then not on team
    elif len(matches) == 1:
        return matches[0][0] != None
    else:
        logging.error(f"Database: No entry in Participants table matches discord_id={member.id}.")
        return False


def team_exists(team_name: str):
    '''
    Check if a team exists with a particular name.
    '''
    cur.execute("SELECT * FROM Teams WHERE team_name = ?;", (team_name,))
    if len(cur.fetchall()) > 0:
        logging.info(f"Database: team name {team_name} exists.")
        return True
    else:
        return False


def participant_exists(discord_id):
    # verify participant exists
    cur.execute("SELECT * From Participants WHERE discord_id = ?;", (str(discord_id),))
    matches = cur.fetchall()
    if len(matches) == 0:
        return False
    elif len(matches) == 1:
        return True
    else: # more than 1 match
        logging.error(f"More than one participant in database matches discord_id={discord_id}")
        return True


def check_team_validity(
    team_name: str, 
    team_text: discord.TextChannel,
    team_vc: discord.VoiceChannel,
    team_cat: discord.CategoryChannel,
    team_role: discord.Role,
    members: list 
):
    '''
    Should be run before insert_team. Checks a team can be inserted correctly.
    '''
    logging.info(f"check_team_validity called with args: {team_name}, {team_text}, {team_vc}, {team_cat}, {team_role}")

    if team_exists(team_name):
        return False
    
    cur.execute("SELECT * FROM Teams WHERE channel_id = ? OR voice_id = ? OR category_id = ? OR role_id = ?;",
        (str(team_text.id), str(team_vc.id), str(team_cat.id), str(team_role.id))
    )
    if len(cur.fetchall()) > 0:
        logging.error("Database: one of the IDs for channel/category/role was already in the database.")
        return False
    
    for member in members:
        # get participant's email
        cur.execute("SELECT email, team_name FROM Participants WHERE discord_id = ?;", (str(member.id),))
        matches = cur.fetchall()

        # if we have multiple participants with same id, this is a Problem (but should not happen due to other checks)
        # adding this check is why we aren't using is_on_team here
        if len(matches) > 1:
            logging.error(f"Database: Multiple participants in Participants table match discord_id = {member.id}")
            return False
        
        elif len(matches) == 0:
            logging.error(f"Database: No participant matches discord_id = {member.id}")
            return False
        
        elif matches[0][1] != None:
            logging.error(f"Database: Participant {member.name} with id={member.id} is already on a team (team_name={matches[0][1]})")
            return False
        
        
    # otherwise, checks pass
    return True


def insert_team(
    team_name: str, 
    team_text: discord.TextChannel,
    team_vc: discord.VoiceChannel,
    team_cat: discord.CategoryChannel,
    team_role: discord.Role,
    members: list
):
    '''
    Insert a team and participants into the Participants and Teams tables.
    Does not check for foreign key constraints or illegal duplicates; this should be done first.
    '''

    # add team to Teams table
    cur.execute("INSERT INTO Teams VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
        (team_name, str(team_text.id), str(team_vc.id), str(team_cat.id), str(team_role.id), None, None, None)
        # None/NULL for judging info that isnt yet specified
    )
    con.commit()
    logging.info(f"Database: created team {team_name}")

    # add each participant as member of team to Members table
    for member in members:
        cur.execute("UPDATE Participants SET team_name = ? WHERE discord_id = ?;", (team_name, str(member.id)))
        logging.info(f"Database: updated member (name={member.name}, id={member.id}) to have team_name={team_name}")

    con.commit()


def remove_from_team(team_name, member):
    '''
    Run checks and remove a participant from a team.
    '''
    res, info = False, ""
    logging.info(f"remove_from_team called with args: {team_name}, {member}")

    cur.execute("SELECT team_name FROM Participants WHERE discord_id = ?;", (str(member.id),))
    matches = cur.fetchall()
    
    # check participant exists
    if len(matches) == 0:
        logging.error(f"Database: No participant matches discord_id = {member.id}")
        res, info = False, "That user is not a verified participant."
                
    # check participant is actually on this team
    elif matches[0][0] != team_name:
        logging.info(f"Database: Participant {member.name} with id={member.id} is not on team {team_name}")
        res, info = False, f"That participant is not on team `{team_name}`."

    # can remove from team
    else:
        cur.execute("UPDATE Participants SET team_name = NULL WHERE discord_id = ?;", (str(member.id),))
        con.commit()
        res, info = True, f"Successfully removed participant {member.mention} from team `{team_name}`."

    return res, info


def add_to_team(team_name, member):
    '''
    Run checks and add a participant to a team.
    '''
    res, info = False, ""
    logging.info(f"add_to_team called with args: {team_name}, {member}")

    # check there aren't already max participants on the team
    cur.execute("SELECT * FROM Participants WHERE team_name = ?;", (team_name,))
    matches = cur.fetchall()

    if len(matches) >= config['max_team_participants']:
        logging.info(f"Database: There are already the maximum number participants on team {team_name}.")
        res, info = False, f"There are already the maximum number participants on team {team_name}."
        return res, info
    
    # verify team exists
    if not team_exists(team_name):
        res, info = False, f"Team `{team_name}` does not exist."
        return res, info
    
    # verify participant isn't already on a team
    if is_on_team(member):
        res, info = False, "That participant is already on a team."
        return res, info
    
    # verify participant exists
    if not participant_exists(member.id):
        res, info = False, "That user is not a verified participant."
        return res, info

    # can add to team
    cur.execute("UPDATE Participants SET team_name = ? WHERE discord_id = ?;", (team_name, str(member.id),))
    con.commit()
    return True, f"Successfully added participant {member.mention} to team `{team_name}`."


def get_team_role(guild: discord.Guild, team_name: str):
    '''
    Get the role corresponding to a Team.
    '''
    cur.execute("SELECT role_id FROM Teams WHERE team_name = ?;", (team_name,))
    match = cur.fetchone()

    role = dget(guild.roles, id=int(match[0]))
    return role


def make_team_info(guild: discord.Guild, team: tuple):
    '''
    Takes a Guild and a row from the Teams table, constructs a dictionary.
    '''
    logging.info(f"make_team_info called for team: {team}")

    # construct info for team
    team_info = {
        "team_text": dget(guild.channels, id=int(team[1])),
        "team_vc": dget(guild.channels, id=int(team[2])),
        "team_cat": dget(guild.categories, id=int(team[3])),
        "team_role": dget(guild.roles, id=int(team[4]))
    }

    # get all members
    cur.execute(f"SELECT * FROM Participants WHERE team_name = ?;", (team[0],))
    members = cur.fetchall()
    members_info = []

    # append info of each member
    for member in members:
        members_info.append({
            "member_email": member[0],
            "member_first_name": member[1],
            "member_last_name": member[2],
            "member_discord_id": member[3],
            "member_object": dget(guild.members, id=int(member[3]))
        })

    team_info["team_members"] = members_info
    return team_info


def get_teams_info(guild: discord.Guild):
    logging.info(f"get_teams_info: called")
    info = {}

    # for each team, get everything, 10 at a time
    cur.execute("SELECT * FROM Teams;")
    matches = cur.fetchall()
    
    for match in matches:
        info[match[0]] = make_team_info(guild, match)

    return info


def get_team_info(guild: discord.Guild, team_name: str):
    logging.info(f"get_team_info: called")
    info = {}

    cur.execute("SELECT * FROM Teams WHERE team_name = ?;", (team_name,))
    matches = cur.fetchone()
    info[match[0]] = make_team_info(guild, match)

    return info


def team_from_text_channel(channel_id):
    '''
    Gets the team associated with a text channel ID, if any.
    '''

    cur.execute("SELECT team_name FROM Teams WHERE channel_id = ?;", (str(channel_id),))
    matches = cur.fetchall()

    if len(matches) == 0:
        logging.info(f"No team found matching channel_id {channel_id}")
        return None
    elif len(matches) == 1:
        return matches[0][0]
    else:
        logging.error(f"More than 1 team_name matches channel_id {channel_id}")


def modify_team_challenges(team_name: str, challenge_names: list):
    '''
    Sign up a team for a set of challenges (should include main HackED as a challenge). Returns Boolean for success/failure.
    '''
    # check team exists
    if not team_exists(team_name):
        return False
    
    try:
        # remove any existing challenge signups for this team
        cur.execute("DELETE FROM Challenges WHERE team_name = ?;", (team_name,))

        # add new challenge signups
        for challenge_name in challenge_names:
            cur.execute("INSERT INTO Challenges VALUES (?, ?);", (challenge_name, team_name))
        con.commit()

        logging.info(f"database, team {team_name} signed up for challenges {challenge_names}")
        return True
    
    except Exception as e:
        logging.error(f"something went wrong: {e}")
        return False


def get_teams_challenges(team_name: str):
    '''
    Get challenges associated with a particular team.
    '''    
    cur.execute("SELECT challenge_name FROM Challenges WHERE team_name = ?;", (team_name,))
    matches = cur.fetchall()
    return [m[0] for m in matches]


def modify_team_judging_info(team_name: str, medium_pref: str, github_link: str, devpost_link: str):
    '''
    Modify necessary judging info for a team. Returns Boolean for success/failure.
    '''
    # check team exists
    if not team_exists(team_name):
        return False

    try:
        cur.execute("UPDATE Teams SET medium_pref = ?, github_link = ?, devpost_link = ? WHERE team_name = ?;", (medium_pref, github_link, devpost_link, team_name))
        con.commit()

        logging.info(f"database, team {team_name} updated judging info: {medium_pref}, {github_link}, {devpost_link}")
        return True
    
    except Exception as e:
        logging.error(f"something went wrong: {e}")
        return False
    

def get_all_challenge_info():
    '''
    Gets information required for sorting teams into judging queues; that is, medium preference and challenges signed up for.
    '''
    info = []

    # get all the teams
    cur.execute("SELECT team_name, medium_pref FROM Teams;")
    matches_team = cur.fetchall()
    
    for team_name, medium_pref in matches_team:
        # get the challenges this team signed up for
        cur.execute("SELECT challenge_name FROM Challenges WHERE team_name = ?;", (team_name,))
        matches_chal = cur.fetchall()

        # construct info
        info.append({
            'team_name': team_name,
            'medium_pref': medium_pref,
            'challenges': challenge_order([m[0] for m in matches_chal])
        })

    return info



def change_team_name(old_name, new_name):
    '''
    not my best work. delete the team and create a new identical one. its fine.
    '''
    logging.info(f"change_team_name called with old={old_name}, new={new_name}")

    if not team_exists(old_name):
        return False, f"Team `{old_name}` not found."

    try:
        cur.execute("UPDATE Teams SET team_name = ? WHERE team_name = ?;", (new_name, old_name))
        cur.execute("UPDATE Participants SET team_name = ? WHERE team_name = ?;", (new_name, old_name))
        cur.execute("UPDATE Challenges SET team_name = ? WHERE team_name = ?;", (new_name, old_name))
        con.commit()

        logging.info("team name changed!")
        return True, f"Team `{old_name}` renamed to `{new_name}`."
    except Exception as e:
        logging.error("something went wrong changing team name", exc_info=e)
