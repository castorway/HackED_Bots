import discord
import os
from discord.channel import CategoryChannel
from discord.ext import commands
from discord.utils import find, get

# Following code loads the .env file located
# Can be commented out if the user wishes to use there own token
# just be sure to assign TOKEN your token value
from dotenv import load_dotenv
from dotenv.main import find_dotenv
load_dotenv(find_dotenv())
TOKEN = os.environ.get("DISCORD_TOKEN")

COUNT = 0
# This line sets the prefix for any user activatable commands
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents = intents)

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))

'''This command prints out the judging list to the channel when called. 
This is to help the teams gthe order in which they will be called'''
@bot.command()
async def order(ctx):

    # first deletes the command made by the admin
    await ctx.message.delete()

    guild = ctx.guild
    # role = ctx.guild.roles
    # Finds the required roles needed in the guild
    global inperson, online, channel

    # channel for admin use
    channel = bot.get_channel(1060056031620780102)

    inperson = discord.utils.find(lambda r: r.name == 'In-Person', ctx.message.guild.roles)
    online = discord.utils.find(lambda r: r.name == 'Online', ctx.message.guild.roles)
    
    # finding all the teams that were created by the participant (team creation bot created teams with a particuar colour)
    teams_str = [role.name for role in guild.roles if role.colour == discord.Colour(0x808080) ]
    # print(teams_str)

    # initiating numbering for the teams
    index = 1


    # initiating a dictionary that would be used when we need to call the next team up for judging
    global dic, V, I, team

    dic = {}
    V = online.name
    I = inperson.name


    if ctx.message.channel.name == "judging":

        # creating the online list
        await ctx.send('**This is the list for the teams presenting**')
        # printing the list for admin more nicely
        await channel.send('**This is the list for the teams presenting**')
        judging_message = ""
        admin_judging_message = ""
        for order, team in enumerate(teams_str):
            
            # using the string names to find the roles and store them in a list
            teams_role = find(lambda r: r.name == f'{team}', ctx.message.guild.roles)
            print(teams_role)

            ONLINE = []
            INPERSON = []
            # if gthere are no memebers in team
            if len(teams_role.members) == 0:
                pass
            else:
                for member in teams_role.members:
                    # checks if member is online
                    if (online in member.roles):
                        ONLINE.append(member.name)
                        # to check if the team has already beeen added to the list
                        if team in dic.keys():
                            continue
                        else:
                            dic[f'{team}'] = V
                            print(f'{team} : {dic[team]}')
                            # sending the list to the channel
                            #await ctx.send(f'{index}. {team}')
                            judging_message += f'{index}. {team}\n'
                            index += 1
                            # printing the list for admin more nicely
                            #await channel.send(f'{team} : {dic[team]}')
                            admin_judging_message += f'{team} : {dic[team]}\n'
                            continue
                    elif (inperson in member.roles):
                        INPERSON.append(member.name)   
                    else:
                        pass
            
                # checking if all members of the team are inperson
                # if they are then the team is presenting INPERSON
                if (len(INPERSON) == len(teams_role.members)):
                    # adding the teams to the dictionary                    
                    if (member.name in INPERSON):
                        dic[f'{team}'] = I
                        print(f'{team} : {dic[team]}')
                        # sending the list to the channel
                        #await ctx.send(f'{index}. {team}')
                        judging_message += f'{index}. {team}\n'
                        index += 1
                        # printing the list for admin more nicely
                        #await channel.send(f'{team} : {dic[team]}')
                        admin_judging_message += f'{team} : {dic[team]}\n'                        
                        continue            

        await ctx.send(judging_message)
        await channel.send(admin_judging_message)
        await ctx.send('** **')
        print(dic)

    return dic

@bot.command()
async def move(ctx, channel: discord.VoiceChannel, *members:discord.Member):
    for member in members:
        for everymember in member:
            await everymember.move_to(channel)


@bot.command()
async def next1(ctx):

    if ctx.message.channel.name == "judging":
    
        # first deletes the command made by the admin
        await ctx.message.delete()
        
        await ctx.send('**************************************************************')
        guild = ctx.guild
        role = ctx.guild.roles
        global dic_list
        dic_list = list(dic)

        await ctx.send('** **')

        # if there are no more items in the dictionary
        if len(dic) == 0:
            await ctx.send('There are no more teams to judge')

        # if there is one item in the dictionary
        elif len(dic) == 1:
            current_key = dic_list[0]
            role_name = find(lambda r: r.name == f'{current_key}', ctx.message.guild.roles)
            judging = get(ctx.guild.roles, name = 'Judgable1')

            # checking if the team is online or inperson
            if dic[current_key] == I:
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, Please head to Room 1. The Organizers at the front desk will be happy to guide where it is if you need help locating the room. You have 3 minutes to get there before you are skipped over.')
            elif dic[current_key] == V:
                members = role_name.members
                for member in members:
                    await member.add_roles(judging)
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, you have been given the judgable role so now please head over to Judging Room 1. The judges will wait up up till two minutes, if you are not in the online room by then you will NOT be judged and the next team will be called.')
            
            # removes first item (team) since that team has been judged
            dic.pop(current_key)

        # if there are more than two items in the dictionary
        elif len(dic) >= 2:
            current_key = dic_list[0]
            next_key = dic_list[1]
            role_name = find(lambda r: r.name == f'{current_key}', ctx.message.guild.roles)
            next_role_name = find(lambda r: r.name == f'{next_key}', ctx.message.guild.roles)
            judging = get(ctx.guild.roles, name = 'Judgable1')

            # checking if the team is online or inperson
            if dic[current_key] == I:
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, Please head to Room 1. The Organizers at the front desk will be happy to guide where it is if you need help locating the room. You have 3 minutes to get there before you are skipped over.')
                await ctx.send(f'{next_role_name.mention} please get ready.')
            elif dic[current_key] == V:
                members = role_name.members
                for member in members:
                    await member.add_roles(judging)
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, you have been given the judgable role so now please head over to Judging Room 1. The judges will wait up till two minutes, if you are not in the online room by then you will NOT be judged and the next team will be called.')
                await ctx.send(f'{next_role_name.mention} please get ready')

            # removes first item (team) since that team has been judged
            dic.pop(current_key)

        else:
            pass

        # print(dic)
        # print(role_name.name)
        # print(dic[role_name])
        # print(f'{str(role_name)} : {str(dic[role_name])}')
        
        await channel.send('** **')

        # printing the updated list for admin more nicely
        for i in dic:
            print(i)
            await channel.send(f'{i} : {dic[i]}')
            
        print()
        print(f'whats left: {dic}')
        print()

    return dic
    

@bot.command()
async def next2(ctx):

    if ctx.message.channel.name == "judging":

        # first deletes the command made by the admin
        await ctx.message.delete()
        
        await ctx.send('**************************************************************')
        guild = ctx.guild
        role = ctx.guild.roles
        global dic_list
        dic_list = list(dic)

        await ctx.send('** **')

        # if there are no more items in the dictionary
        if len(dic) == 0:
            await ctx.send('There are no more teams to judge')

        # if there is one item in the dictionary
        elif len(dic) == 1:
            current_key = dic_list[0]
            role_name = find(lambda r: r.name == f'{current_key}', ctx.message.guild.roles)
            judging = get(ctx.guild.roles, name = 'Judgable2')

            # checking if the team is online or inperson
            if dic[current_key] == I:
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, Please head to Room 2. The Organizers at the front desk will be happy to guide where it is if you need help locating the room. You have 3 minutes to get there before you are skipped over.')
            elif dic[current_key] == V:
                members = role_name.members
                for member in members:
                    await member.add_roles(judging)
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, you have been given the judgable role so now please head over to Judging Room 2. The judges will wait up till two minutes, if you are not in the online room by then you will NOT be judged and the next team will be called.')

            # removes first item (team) since that team has been judged
            dic.pop(current_key)

        # if there are more than two items in the dictionary
        elif len(dic) >= 2:
            current_key = dic_list[0]
            next_key = dic_list[1]
            role_name = find(lambda r: r.name == f'{current_key}', ctx.message.guild.roles)
            next_role_name = find(lambda r: r.name == f'{next_key}', ctx.message.guild.roles)
            judging = get(ctx.guild.roles, name = 'Judgable2')

            # checking if the team is online or inperson
            if dic[current_key] == I:
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, Please head to Room 2. The Organizers at the front desk will be happy to guide where it is if you need help locating the room. You have 3 minutes to get there before you are skipped over.')
                await ctx.send(f'{next_role_name.mention} please get ready.')
            elif dic[current_key] == V:
                members = role_name.members
                for member in members:
                    await member.add_roles(judging)
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, you have been given the judgable role so now please head over to Judging Room 2. The judges will wait up till two minutes, if you are not in the online room by then you will NOT be judged and the next team will be called.')
                await ctx.send(f'{next_role_name.mention} please get ready')

            # removes first item (team) since that team has been judged
            dic.pop(current_key)

        else:
            pass

        await channel.send('** **')
        
        # printing the updated list for admin more nicely
        for i in dic:
            print(i)
            await channel.send(f'{i} : {dic[i]}')
            
        print()
        print(f'whats left: {dic}')
        print()

    return dic

@bot.command()
async def next3(ctx):

    if ctx.message.channel.name == "judging":

        # first deletes the command made by the admin
        await ctx.message.delete()
        
        await ctx.send('**************************************************************')
        guild = ctx.guild
        role = ctx.guild.roles
        global dic_list
        dic_list = list(dic)

        await ctx.send('** **')

        # if there are no more items in the dictionary
        if len(dic) == 0:
            await ctx.send('There are no more teams to judge')

        # if there is one item in the dictionary
        elif len(dic) == 1:
            current_key = dic_list[0]
            role_name = find(lambda r: r.name == f'{current_key}', ctx.message.guild.roles)
            judging = get(ctx.guild.roles, name = 'Judgable3')

            # checking if the team is online or inperson
            if dic[current_key] == I:
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, Please head to Room 3. The Organizers at the front desk will be happy to guide where it is if you need help locating the room. You have 3 minutes to get there before you are skipped over.')
            elif dic[current_key] == V:
                members = role_name.members
                for member in members:
                    await member.add_roles(judging)
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, you have been given the judgable role so now please head over to Judging Room 3. The judges will wait up till two minutes, if you are not in the online room by then you will NOT be judged and the next team will be called.')

            # removes first item (team) since that team has been judged
            dic.pop(current_key)

        # if there are more than two items in the dictionary
        elif len(dic) >= 2:
            current_key = dic_list[0]
            next_key = dic_list[1]
            role_name = find(lambda r: r.name == f'{current_key}', ctx.message.guild.roles)
            next_role_name = find(lambda r: r.name == f'{next_key}', ctx.message.guild.roles)
            judging = get(ctx.guild.roles, name = 'Judgable3')

            # checking if the team is online or inperson
            if dic[current_key] == I:
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, Please head to Room 3. The Organizers at the front desk will be happy to guide where it is if you need help locating the room. You have 3 minutes to get there before you are skipped over.')
                await ctx.send(f'{next_role_name.mention} please get ready.')
            elif dic[current_key] == V:
                members = role_name.members
                for member in members:
                    await member.add_roles(judging)
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, you have been given the judgable role so now please head over to Judging Room 3. The judges will wait up till two minutes, if you are not in the online room by then you will NOT be judged and the next team will be called.')
                await ctx.send(f'{next_role_name.mention} please get ready.')

            # removes first item (team) since that team has been judged
            dic.pop(current_key)
        else:
            pass

        await channel.send('** **')
        
        # printing the updated list for admin more nicely
        for i in dic:
            print(i)
            await channel.send(f'{i} : {dic[i]}')

        print()
        print(f'whats left: {dic}')
        print()

    return dic

@bot.command()
async def next4(ctx):

    if ctx.message.channel.name == "judging":

        # first deletes the command made by the admin
        await ctx.message.delete()
        
        await ctx.send('**************************************************************')
        guild = ctx.guild
        role = ctx.guild.roles
        global dic_list
        dic_list = list(dic)

        await ctx.send('** **')

        # if there are no more items in the dictionary
        if len(dic) == 0:
            await ctx.send('There are no more teams to judge')

        # if there is one item in the dictionary
        elif len(dic) == 1:
            current_key = dic_list[0]
            role_name = find(lambda r: r.name == f'{current_key}', ctx.message.guild.roles)
            judging = get(ctx.guild.roles, name = 'Judgable4')

            # checking if the team is online or inperson
            if dic[current_key] == I:
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, Please head to Room 4. The Organizers at the front desk will be happy to guide where it is if you need help locating the room. You have 3 minutes to get there before you are skipped over.')
            elif dic[current_key] == V:
                members = role_name.members
                for member in members:
                    await member.add_roles(judging)
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, you have been given the judgable role so now please head over to Judging Room 4. The judges will wait up till two minutes, if you are not in the online room by then you will NOT be judged and the next team will be called.')

            # removes first item (team) since that team has been judged
            dic.pop(current_key)

        # if there are more than two items in the dictionary
        elif len(dic) >= 2:
            current_key = dic_list[0]
            next_key = dic_list[1]
            role_name = find(lambda r: r.name == f'{current_key}', ctx.message.guild.roles)
            next_role_name = find(lambda r: r.name == f'{next_key}', ctx.message.guild.roles)
            judging = get(ctx.guild.roles, name = 'Judgable4')

            # checking if the team is online or inperson
            if dic[current_key] == I:
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, Please head to Room 4. The Organizers at the front desk will be happy to guide where it is if you need help locating the room. You have 3 minutes to get there before you are skipped over.')
                await ctx.send(f'{next_role_name.mention} please get ready.')
            elif dic[current_key] == V:
                members = role_name.members
                for member in members:
                    await member.add_roles(judging)
                await ctx.send(f'Hey {role_name.mention}, your team will be judged now, you have been given the judgable role so now please head over to Judging Room 4. The judges will wait up till two minutes, if you are not in the online room by then you will NOT be judged and the next team will be called.')
                await ctx.send(f'{next_role_name.mention} please get ready.')

            # removes first item (team) since that team has been judged
            dic.pop(current_key)
        else:
            pass

        await channel.send('** **')
        
        # printing the updated list for admin more nicely
        for i in dic:
            print(i)
            await channel.send(f'{i} : {dic[i]}')

        print()
        print(f'whats left: {dic}')
        print()

    return dic



bot.run(TOKEN)