import itertools
import numpy as np
from utils import general_setup
from copy import deepcopy
import logging
import database
import utils
import json
from declare_cog import challenge_order

# setup
args, config = utils.general_setup()

with open(config['challenge_data_path'], 'r') as f:
    challenge_data = json.loads(f.read())


def first_chal_match():
    '''
    Puts teams in the first room that matches their challenge. Disregards medium.
    Returns a dictionary mapping room_id to teams, and a dictionary of unassigned teams.
    '''
    info = database.get_all_challenge_info()
    print(info)

    rooms = {room_id: [] for room_id in config['judging_rooms'].keys()} # available rooms
    unchosen = [] # teams that seemingly did not choose any challenges (including main hacked), i.e. did not sign up for judging
    unassigned = [] # teams that picked challenges but don't get assigned a room

    # for each team, get their challenge combo
    for team_data in info:
        
        team_name = team_data['team_name']
        challenge_choices = team_data['challenges']
        room_found = False
        logging.info(f"{team_name}: {challenge_choices}")

        if challenge_choices == []:
            # team did not sign up for judging
            logging.info("> team has no recorded challenge choices, skipping")
            unchosen.append(team_name)

        # if a challenge and medium matches, put in that room
        for chal in challenge_choices:
            if chal == challenge_data['main_challenge']: continue

            for room_id, room_info in config['judging_rooms'].items():
                if chal in room_info['challenges']:
                    rooms[room_id].append(team_name)
                    room_found = room_id
                    break

            if room_found: break

        # if it doesn't match any rooms for optional challenge, put in a default room matching medium
        if not room_found:
            for room_id, room_info in config['judging_rooms'].items():
                if room_info['challenges'] == []:
                    rooms[room_id].append(team_name)
                    room_found = room_id
                    break
        
        # if this hasn't worked, error
        if not room_found:
            logging.error(f"> Was unable to find a room for {team_name} with medium_pref={medium_pref} and challenges={team_data['challenges']}")
            unassigned.append(team_name)
        else:
            logging.info(f"> Assigned {team_name} to room {room_id}.")
    
    return rooms, unchosen, unassigned


def first_chal_med_match():
    '''
    Puts teams in the first room that matches their challenge/medium.
    Returns a dictionary mapping room_id to teams, and a dictionary of unassigned teams.

    DEPRECATED
    '''
    info = database.get_all_challenge_info()
    print(info)

    rooms = {room_id: [] for room_id in config['judging_rooms'].keys()} # available rooms
    unchosen = [] # teams that seemingly did not choose any challenges (including main hacked), i.e. did not sign up for judging
    unassigned = [] # teams that picked challenges but don't get assigned a room

    # for each team, get their challenge combo
    for team_data in info:
        
        team_name = team_data['team_name']
        medium_pref = team_data['medium_pref']
        challenge_choices = team_data['challenges']
        room_found = False
        logging.info(f"{team_name}: {medium_pref}, {challenge_choices}")

        if challenge_choices == []:
            # team did not sign up for judging
            logging.info("> team has no recorded challenge choices, skipping")
            unchosen.append(team_data)
            continue

        # if a challenge and medium matches, put in that room
        for chal in challenge_choices:
            if chal == challenge_data['main_challenge']: continue

            for room_id, room_info in config['judging_rooms'].items():
                if chal in room_info['challenges'] and medium_pref in room_info['mediums']:
                    rooms[room_id].append(team_data)
                    room_found = room_id
                    break

            if room_found: break

        # if it doesn't match any rooms for optional challenge, put in a default room matching medium
        if not room_found:
            for room_id, room_info in config['judging_rooms'].items():
                if room_info['challenges'] == [] and medium_pref in room_info['mediums']:
                    rooms[room_id].append(team_data)
                    room_found = room_id
                    break
        
        # if this hasn't worked, error
        if not room_found:
            logging.error(f"> Was unable to find a room for {team_name} with medium_pref={medium_pref} and challenges={team_data['challenges']}")
            unassigned.append(team_data)
        else:
            logging.info(f"> Assigned {team_name} to room {room_id}.")
    
    return rooms, unchosen, unassigned



"""
def category_priority(team_category_reacts):
    '''
    Teams are ordered based on category priority defined in config, then split evenly across any judging rooms.
    
    DEPRECATED, worked with old reaction system but not with new sqlite3 db system.
    '''

    logging.info("category priority algorithm")

    # go by category priority
    ordered_cats = [c for c in config["judging_categories"].keys()]
    ordered_cats = sorted(ordered_cats, key=lambda c: config["judging_categories"][c]["priority"] * -1) # higher numbers first in list
    logging.info(f"sorted categories: {ordered_cats}")

    cat_to_teams = {c: [] for c in ordered_cats}

    # sort team_category_reacts into teams by category, prioritizing higher-priority categories
    for team, reacts in team_category_reacts.items():
        for c in ordered_cats:
            if config["judging_categories"][c]["react"] in reacts:
                cat_to_teams[c].append(team)
                break
        else:
            logging.warning(f"team {team} with reacts {reacts} couldn't be put in a category, skipping")
    
    for c in ordered_cats:
        msg = f"> teams whose highest-priority category is {c} {config['judging_categories'][c]['react']}: {', '.join(cat_to_teams[c])}"
        logging.info(msg)

    room_to_teams = {r: [] for r in config["judging_rooms"].keys()}
    room_to_extra = {r: [] for r in config["judging_rooms"].keys()} # any extra info about team to print in private judging logs

    # sort categories into available rooms for that category
    for c in ordered_cats:
        logging.info(f"looking at category {c} with priority {config['judging_categories'][c]['priority']} and rooms {config['judging_categories'][c]['rooms']}")
        
        n_rooms = len(config["judging_categories"][c]["rooms"])
        
        if len(cat_to_teams[c]) == 0:
            continue

        np.random.shuffle(cat_to_teams[c])

        split_by_room = np.array_split(cat_to_teams[c], n_rooms)
        msg = f"teams assigned to each room for category {c} {config['judging_categories'][c]['react']}:"

        for i, room in enumerate(config["judging_categories"][c]["rooms"]):
            room_to_teams[room] += list(split_by_room[i])
            room_to_extra[room] += [config["judging_categories"][c]["react"]] * len(split_by_room[i])
            msg += f"\n=== {room} ===\n{', '.join(split_by_room[i])}"

        logging.info(msg)
    
    return room_to_teams, room_to_extra


def original_queue_algorithm(team_category_choice, team_medium_pref):
    '''
    One of many possible ways to do queueing. This way, teams are shuffled, and each in order is given their first
    choice for category + medium if possible (high-priority). Then, if a team has selected more than one special category,
    they are also given a room in that category (low-priority).

    team_category_choice is a dictionary mapping team name to a list of the names of the special categories
    they selected to be judged in.

    team_medium_pref is a dictionary mapping team name to a string "online" or "inperson" corresponding to their preferred
    judging medium.

    DEPRECATED
    '''

    room_to_teams = {r: [] for r in config["judging_rooms"].keys()}

    categories = [cat for cat, info in config["judging_categories"].items()] # use string names for categories
    mediums = ["online", "inperson"]

    catmed_pairs = list(itertools.product(categories, mediums))
    # priority_teams = {x: [] for x in catmed_pairs}
    # non_priority_teams = {x: [] for x in catmed_pairs}
    teams_by_catmed = {x: [] for x in catmed_pairs}

    all_judgable_teams = list(set(list(team_category_choice.keys()) + list(team_medium_pref.keys())))
    np.random.shuffle(all_judgable_teams)

    # map choice of (category, medium) to teams
    for team_name in all_judgable_teams:

        # first, go by special category
        cat_choices = list(set(team_category_choice[team_name]))
        med = team_medium_pref[team_name] # get team's online/inperson preference
        priority = True

        if len(cat_choices) == 0: # no special categories, hooray
            teams_by_catmed[("default", med)].append(team_name)

        else:
            # assign team into a room for each category. default judging can also be done by category judges, so
            # they don't also need to be in a default room.
            for cat in cat_choices:
                teams_by_catmed[(cat, med)].append(team_name)
                # if priority:
                #     # if team is online, they must be put in an online room (if available)
                #     priority_teams[(cat, med)].append(team_name)
                # else:
                #     # otherwise (if team not online or if no online room available), they go in whatever's available
                #     non_priority_teams[(cat, med)].append(team_name)
                # priority = False # team only has priority for the first category they are entered in

    # log information
    msg = "\n=====================================\n"
    msg += "Initial team assignment breakdown:\n"
    msg += "-------------------------------------\n"
    for (cat, med) in catmed_pairs:
        msg += f"=== {cat.upper()} & {med.upper()} ===\n"
        # log_f(f">>> PRIORITY: {len(priority_teams[(cat, med)])}\n{priority_teams[(cat, med)]}\n")
        # log_f(f">>> NON-PRIORITY: {len(non_priority_teams[(cat, med)])}\n{non_priority_teams[(cat, med)]}\n")
        msg += f"num={len(teams_by_catmed[(cat, med)])}\n{teams_by_catmed[(cat, med)]}\n"
    msg += "=====================================\n"
    logging.info(msg)

    # redistribute categories; if a lot of teams are in default category, 

    # get rooms available by (cat, med) pair
    rooms_by_catmed = {x: [] for x in catmed_pairs}
    room_dist = {} # this will hold final distribution
    for cat, cat_info in config["judging_categories"].items():
        for med, rooms in cat_info["rooms"].items():
            rooms_by_catmed[(cat, med)] += rooms
            for r in rooms:
                room_dist[r] = []

    logging.info(f"Rooms available: {rooms_by_catmed}")

    # then, distribute inperson teams such that online and inperson rooms have number
    # proportional to number of available rooms

    for cat in categories:
        online_teams = teams_by_catmed[(cat, "online")]
        inperson_teams = teams_by_catmed[(cat, "inperson")]
        online_rooms = rooms_by_catmed[(cat, "online")]
        inperson_rooms = rooms_by_catmed[(cat, "inperson")]

        logging.info(f"{cat} | online_teams={len(online_teams)}, inperson_teams={len(inperson_teams)}, online_rooms={len(online_rooms)}, inperson_rooms={len(inperson_rooms)}")

        if len(online_rooms) > 0 and len(inperson_rooms) > 0:
            # teams_by_catmed[(cat, "online")] can stay, all online teams stay in online rooms

            # if we have more inperson teams than ideal 'target' value, redistribute some onto online
            n_teams = len(online_teams) + len(inperson_teams)
            target_n_inperson = int(n_teams * len(inperson_rooms) / (len(online_rooms) + len(inperson_rooms)))
            logging.info(f"> target_n_inperson={target_n_inperson}")

            if target_n_inperson < len(inperson_teams):
                # redistribute overflow
                logging.info(f"> redistribute {len(inperson_teams) - target_n_inperson} to online")
                online_teams += deepcopy(inperson_teams[target_n_inperson:])
                inperson_teams = inperson_teams[:target_n_inperson]

        elif len(online_rooms) == 0 and len(inperson_rooms) > 0:
            # we have only inperson rooms
            logging.info(f"> redistribute all to inperson")
            inperson_teams += deepcopy(online_teams)
            online_teams = []
        
        elif len(online_rooms) > 0 and len(inperson_rooms) == 0:
            # we have only online rooms
            logging.info(f"> redistribute all to online")
            online_teams += deepcopy(inperson_teams)
            inperson_teams = []

        else:
            logging.info(f"> no redistribution")

        logging.info(f"{cat} | online_teams={len(online_teams)}, inperson_teams={len(inperson_teams)}, online_rooms={len(online_rooms)}, inperson_rooms={len(inperson_rooms)}")
        teams_by_catmed[(cat, "online")] = online_teams
        teams_by_catmed[(cat, "inperson")] = inperson_teams

    msg = "\n=====================================\n"
    msg += "After redistribution by availability & room weighting:\n"
    msg += "-------------------------------------\n"
    for (cat, med) in catmed_pairs:
        msg += f"=== {cat.upper()} & {med.upper()} (rooms={len(rooms_by_catmed[(cat, med)])}) (teams={len(teams_by_catmed[(cat, med)])}) ===\n{teams_by_catmed[(cat, med)]}\n"
    msg += "=====================================\n"
    logging.info(msg)

    # then, distribute teams by (cat, med) into *individual* rooms by (cat, med)
    for (cat, med), teams in teams_by_catmed.items():
        if len(teams) == 0: continue

        rooms = rooms_by_catmed[(cat, med)]
        room_split = np.array_split(teams, len(rooms))
        for i, room in enumerate(rooms):
            room_dist[room] = room_split[i].tolist()
    
    # log information
    msg = "\n=====================================\n"
    msg += "After redistribution into actual rooms:\n"
    msg += "-------------------------------------\n"
    for room, teams in room_dist.items():
        msg += f"=== {room} (teams={len(teams)}) ===\n{teams}\n"
    msg += "=====================================\n"
    logging.info(msg)

    # done
    return room_dist
"""