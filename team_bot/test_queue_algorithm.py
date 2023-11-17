import queuing

team_category_choice = {
    "hackers": ["mecsimcalc", "edi"],
    "hackers2": ["mecsimcalc", "edi"],
    "aaa": ["mecsimcalc", "edi"],
    "bbb": ["mecsimcalc", "edi"],
    "ccc": ["edi"],
    "ddd": ["edi"],
    "eee": ["mecsimcalc"],
    "fff": ["mecsimcalc"],
    "ggg": ["mecsimcalc"],
    "hhh": ["mecsimcalc"],
    "teamname": [],
    "teamname2": [],
    "teamname3": [],
    "teamname4": [],
    "teamname5": [],
    "teamname6": []
}

team_medium_pref = {
    "hackers": "online",
    "hackers2": "online",
    "aaa": "online",
    "bbb": "inperson",
    "ccc": "inperson",
    "ddd": "online",
    "eee": "online",
    "fff": "inperson",
    "ggg": "inperson",
    "hhh": "inperson",
    "teamname": "inperson",
    "teamname2": "inperson",
    "teamname3": "inperson",
    "teamname4": "inperson",
    "teamname5": "inperson",
    "teamname6": "online"
}

team_category_reacts = {
    "hackers": ["⚙️"],
    "hackers2": ["⚙️", "⭐"],
    "aaa": ["⚙️", "⭐"],
    "bbb": [],
    "ccc": [],
    "ddd": ["⭐"],
    "eee": ["⭐"]
}

# queuing.queue_algorithm(team_category_choice, team_medium_pref)
x = queuing.category_priority(team_category_reacts)

print(x)