import discord
from dotenv import load_dotenv
import os
import random
import asyncio
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
TOKEN = str(os.environ.get("DISCORD_TOKEN"))

channel_id_str = os.environ.get("CHANNEL_ID")
if channel_id_str is None:
    raise ValueError("CHANNEL_ID environment variable is not set")

CHANNEL_ID = int(channel_id_str)

class Client(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.vloggers = []
        self.remaining_picks = []
        self.current_pick = None
        self.daily_task = None
        self.reminder_task = None

    async def on_ready(self):
        print(f'Logged on as {self.user}')

        # Start the daily pick task
        if not self.daily_task:
            self.daily_task = self.loop.create_task(self.daily_picker())

    async def on_message(self, message):
        if message.author == self.user:
            return
        
        # ===== !help =====
        if message.content.startswith('!help'):
            help_text = (
                "**Vlog Bot Commands:**\n"
                "`!joinVlogs` — Join the daily vlogging rotation\n"
                "`!list` — Show all vloggers, current pick, and cycle progress\n"
                "`!done` — Mark your vlog as completed for today\n"
            )
            await message.channel.send(help_text)
            return

        # ===== !list =====
        if message.content.startswith('!list'):
            if not self.vloggers:
                await message.channel.send("No vloggers have joined yet!")
                return

            gone = [v for v in self.vloggers if v not in self.remaining_picks]
            remaining = self.remaining_picks
            current = self.current_pick

            gone_list = ", ".join([u.mention for u in gone]) if gone else "None yet"
            remaining_list = ", ".join([u.mention for u in remaining]) if remaining else "None — cycle complete!"
            current_text = current.mention if current else "No one picked yet"

            msg = (
                "**📋 Vlogger List**\n"
                f"**All vloggers:** {', '.join([u.mention for u in self.vloggers])}\n\n"
                f"**Already gone this cycle:** {gone_list}\n"
                f"**Still remaining:** {remaining_list}\n"
                f"**Current vlogger:** {current_text}"
            )
            await message.channel.send(msg)
            return

        # Add user to joinVlogs list
        if message.content.startswith('!joinVlogs'):
            if message.author not in self.vloggers:
                self.vloggers.append(message.author)
                if isinstance(message.channel, discord.TextChannel):
                    vloggers_list = ", ".join([user.mention for user in self.vloggers])
                    message_text = (
                        f"{message.author.mention} has joined the vlogs!\n"
                        f"Vloggers: {vloggers_list}\n"
                        "One vlogger will be picked randomly each day to create a vlog.\n"
                        "Use `!done` when you finish your vlog."
                    )
                    await message.channel.send(message_text)
                    print(f'Current vloggers: {[user.name for user in self.vloggers]}')
            else:
                if isinstance(message.channel, discord.TextChannel):
                    await message.channel.send(f'{message.author.mention}, you are already in the list.')

        # Mark current user as done
        if message.content.startswith('!done'):
            if message.author == self.current_pick:
                if isinstance(message.channel, discord.TextChannel):
                    await message.channel.send(f'Thank you {message.author.mention}! The next pick will be ready tomorrow.')
                self.current_pick = None
                if self.reminder_task:
                    self.reminder_task.cancel()
            else:
                if isinstance(message.channel, discord.TextChannel):
                    await message.channel.send(f'{message.author.mention}, it is not your turn to mark done.')

    async def daily_picker(self):
        await self.wait_until_ready()
        channel = self.get_channel(CHANNEL_ID)

        if not isinstance(channel, discord.TextChannel):
            print(f"Channel with ID {CHANNEL_ID} is not a text channel or does not exist.")
            return

        while not self.is_closed():
            now = datetime.now()
            next_pick_time = datetime.combine(now.date(), datetime.min.time()) + timedelta(hours=12)
            if now >= next_pick_time:
                next_pick_time += timedelta(days=1)

            wait_seconds = (next_pick_time - now).total_seconds()
            await asyncio.sleep(wait_seconds)

            if not self.vloggers:
                await channel.send('No one has joined the vlogs yet today!')
                continue

            if not self.remaining_picks:
                self.remaining_picks = self.vloggers.copy()

            self.current_pick = random.choice(self.remaining_picks)
            self.remaining_picks.remove(self.current_pick)

            await channel.send(f"Today's vlogger is {self.current_pick.mention}! Type `!done` when finished.")

            # Start reminder task
            if self.reminder_task:
                self.reminder_task.cancel()
            self.reminder_task = self.loop.create_task(self.remind_current_user(channel))

    async def remind_current_user(self, channel: discord.TextChannel):
        while self.current_pick:
            await asyncio.sleep(43200)  # Reminder every 12 hours
            if self.current_pick:
                await channel.send(f'{self.current_pick.mention}, please finish your vlog and type `!done`!')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = Client(intents=intents)
bot.run(TOKEN)
