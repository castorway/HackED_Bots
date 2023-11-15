# HackED_Bots
bots for the CompE Club's HackED hackathons!

## Team Creation

Any user is able to use the `team` command to create a team.

`~team <team name> [team members]`

`~team 1337H4X0RZ @teammate1 @teammate2 @teammate3 @teammate4`

The bot will create a new Discord role, category, text channel, and voice channel with the team's name. The role colour will match the `team_role_colour` defined in the config; ensure that this colour is not used for any other role on the server, or else the bot will treat that role as a 'team'.

Team names are limited to ASCII characters. This is because some special characters can break some judging functionality.

## Judging

### General procedure

1. Run `set_judging_react_messages` to tell the bot which messages have the team reaction for judging medium and category.

2. 

### Setup

`~set_judging_react_messages #<channel> <medium_msg_id> <category_msg_id>`

This command must be run if you want to use `auto_make_queues` to generate judging queues.

### `next` command

`~next <room_id>`

When run, this command increments the bot's judging queue for the room identified as `room_id` in the config. The new schedule will be sent to the `judging_log` channel identified in the config.