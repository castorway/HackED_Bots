# HackED_Bots
bots for the CompE Club's HackED hackathons!

## General Setup

1. Ensure you have a `.env` file in the toplevel repo (`HackED_Bots/`) which contains a variable `BOT_TOKEN=<your_bot_token>`.
2. Ensure you have a sqlite3 database file referenced by the `"db_path"` key in the config. Open the file and run the code in `schema.sql` to initialize it with the tables for participants and teams.

## Team Creation

Any user is able to use the `team` command to create a team.

`~team <team name> [team members]`

`~team 1337H4X0RZ @teammate1 @teammate2 @teammate3 @teammate4`

The bot will create a new Discord role, category, text channel, and voice channel with the team's name. The role colour will match the `team_role_colour` defined in the config; ensure that this colour is not used for any other role on the server, or else the bot will treat that role as a 'team'.

Team names are limited to ASCII characters. This is because some special characters can break some judging functionality.

### Notes

- Anyone can create a team containing any (valid) member.
- There is no way for members to remove themselves from a team, or join an existing team.

## Judging

### Setup

`~set_judging_react_messages #<channel> <medium_msg_id> <category_msg_id>`

This command must be run if you want to use `auto_make_queues` to generate judging queues.

### `next` command

`~next <room_id>`

When run, this command increments the bot's judging queue for the room identified as `room_id` in the config. The new schedule will be sent to the `judging_log` channel identified in the config.

## General procedure

### Setup

* Define all judging rooms in the config.
    * Ensure that a `text` channel is specified for all online *and* in-person judging rooms.
        * Specifically ensure that the `judge` role cannot view the text channel. This is for messy commands and panicking about judging that the actual judges should not see.
    * Ensure that all in-person judging rooms have a `location` specified, all online judging rooms have a `judging_vc` specified, and all hybrid judging rooms have both.

### Team Creation Phase

* Run `~turn_team_creation on` to switch to the team creation phase.
    * During this phase, participants can create teams using `~create_team`.

### Judging Phase

* Run `~turn_team_creation off` to disable the `~create_team` command.
* To automatically generate judging queues:
    * Run `~set_judging_react_messages` to tell the bot where the messages with judging-related reactions are.
    * Run `~auto_make_queues` to generate judging queues.
* Modify the generated json file as you like.
* Run `~start_judging` with the json file to start the judging process.

* For the following process, there should be:
    * A "controller", an organizer or volunteer who is able to run commands that increment the judging queue and ping teams.
        * Runs `~ping` to ping teams at appropriate intervals.
        * Runs `~next` to increment the queue once informed that a team has arrived in their judging room.
        * Runs `~skip` if a team takes does not report to the front desk (in-person) or enter their VC (online).
            * The controller should communicate with the exec in the room and/or exec at the desk to be sure that the team has not shown up before skipping them.
    * An "exec in the room", an organizer or volunteer in each judging room to inform the controller when a team has begun presenting.
        * If online/hybrid: Watches the next-up team's VC and runs `~vcpull` to move members from their VC to the judging room once they have joined their VC.
        * Pings the controller in their room's text channel once a team has arrived and begun presenting (or if a team is taking too long to arrive).
        * Watches the text channel associated with their room.
        * Generally moderates the room. Chats with the judges during quiet periods. Asks the team questions if the judges don't have any. Gently cuts the team off if they go overtime.
    * An "exec at the desk", an organizer or volunteer at the front desk to direct teams to their judging room.
        * Watches all text channels associated with all in-person judging rooms, so they know which teams should be on their way and which rooms to direct them to.
        * Directs teams to the correct judging rooms when they arrive at the front desk.
        * Pings the controller in the appropriate judging room's text channel once a team has arrived and been directed to their room (or if a team is taking too long to arrive).

* There are two notable teams at any given time:
    * The "next-up team"; the team that will be judged next.
    * The "current team"; the team that is currently in the judging room, being judged.

* For each room, until judging is over...

    * For online rooms:
        1. The controller runs `~ping <room_id>` to ping the next-up team (as many times as desired).
            * Teams assigned to an online judging room will be pinged and told to join their VC.
        2. Wait until the next-up team joins their VC.
            * If the team doesn't respond or arrive, the exec in the room should ping the controller, who after some time will run `~skip <room_id>` to skip this team and move them to the end of the queue. The controller then runs `~ping <room_id>` to ping the team after this one, which is the new next-up team.
        3. Once all members of the next-up team are in their VC *and* the current team (if any) has left the judging VC, the exec in the room runs `~vcpull` in the room's associated text channel to pull the next-up team into the judging VC.
            * They can also just move members in manually.
            * The exec in the room should ensure all members of the current team have left the judging VC before letting in the members of the next-up team.
        4. Several things happen at once.
            * The new current team presents to the judges.
                * If a member of the current team disconnects from the judging VC during presentation, they should rejoin their VC and the exec in the room must manually move them into the judging VC.
            * Meanwhile, the exec in the room pings the controller (in the room's associated text channel) to start preparing for the next team.
            * The controller runs `~tick <room_id>` to move the queue, and `~ping <room_id>` to ping the next-up team.
        5. Return to [3].

    * For in-person rooms:
        1. The controller runs `~ping <room_id>` to ping the next-up team (as many times as desired).
            * Teams assigned to an in-person judging room will be pinged and told to come to the front desk.
        2. Wait until next-up team arrives at the front desk.
            * If the team doesn't respond or arrive, the exec at the front desk should ping the controller, who will run `~skip <room_id>` to skip this team and move them to the end of the queue. They then run `~ping <room_id>` to ping the team after this one, which is the new next-up team.
        3. Once the team makes it to the front desk, they should be directed to their judging room (someone at the front desk should check which in-person room is actually associated with the team's room id, and then direct them to that room).
        4. Several things happen at once.
            * The team presents to the judges.
            * Meanwhile, the exec in the room pings the controller (in the room's associated text channel) to start preparing for the next team.
            * The controller runs `~tick <room_id>` and `~ping <room_id>` to ping the next-up team.
        5. Return to [3].

    * In general, wherever possible, keep commands and correspondence related to a particular room in the room's associated text channel.

## Quick sqlite3 Reference

Backing up a database: `.backup hacked.bk`
Setting to read-only: `PRAGMA query_only = ON;`