# Bot Controller

- Run `~ping room_id` to ping the next team when prompted.
- When notified that a team has begun presenting, run `~tick <room_id>` to increment the queue to show the new current team.
- By the 4-minute mark, if at least one member of next team has not shown up (either in-person or online), start pinging the team after them as well.
  - If the team after them shows up, use `~skip <room_id>` to skip the next team and go to the team after them.
  - If the team after them doesn't show up, panic and suffer.