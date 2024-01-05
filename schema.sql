CREATE TABLE Participants(
    email      CHAR(100),
    first_name CHAR(100),
    last_name  CHAR(100),
    discord_id CHAR(20),
    team_name  CHAR(100),
    PRIMARY KEY (email),
    FOREIGN KEY (team_name) REFERENCES Teams
);

CREATE TABLE Teams(
    team_name   CHAR(100),
    channel_id  CHAR(20),
    voice_id    CHAR(20),
    category_id CHAR(20),
    role_id     CHAR(20),
    medium_pref CHAR(20),
    github_link CHAR(100),
    devpost_link CHAR(100),
    PRIMARY KEY (team_name)
);

CREATE TABLE Challenges(
    challenge_name CHAR(100),
    team_name      CHAR(100),
    PRIMARY KEY (challenge_name, team_name),
    FOREIGN KEY (team_name) REFERENCES Teams
);

-- https://discord.com/developers/docs/reference#snowflakes IT HAS LITTLE SNOWFLAKES