import discord
from dotenv import load_dotenv
import os

class Client(discord.Client):
    async def on_ready(self): # calls when the bot is connected and ready
        print(f'Logged on as {self.user}') # prints the bot's username
    

intents = discord.Intents.default() # create default intents
intents.members = True 
intents.message_content = False 
intents.presences = False 
bot = Client(intents=intents) # create bot instance with intents

# Load Discord token from .env file
load_dotenv()
token = str(os.environ.get("DISCORD_TOKEN"))
bot.run(token)