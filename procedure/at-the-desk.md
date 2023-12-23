# Exec-at-the-desk

- Keep an eye out for in-person teams coming to the front desk. Get their team names.
  - When a team gets to the front desk, ping the room channel.
- The current team presenting is identified on the judging log prints. The team just beneath them is the next team presenting. Keep an eye on the VC for the *next team*.
  - When the next team gets to the VC, ping the room channel.
- When the exec-in-the-room pings that they are ready for the next team:
  - Verify who the next team *is* first, in case a team has been skipped.
  - Send anyone in-person from the next team in.
  - Use `~vcpull <room_id>` (team name optional) to send in the online members.
    - If `~vcpull` is giving you the wrong team, use `~vcpull <room_id> <team_name>`.
- If, by the 4-minute mark, the *next team* is not ready either in-person their VC, ping the room channel so the bot controller can start pinging the team after.