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
        self.last_pick_date = None

    # -------------------- Helper Functions --------------------

    async def get_channel_safe(self):
        """Return the channel object or None if invalid."""
        channel = self.get_channel(CHANNEL_ID)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    def format_vlogger_list(self, users):
        """Return formatted string 'Name (ID)' for a list of Members."""
        return ", ".join([f"{u.name} ({u.id})" for u in users]) if users else "None"

    async def delete_last_pick_message(self, channel):
        """Delete the message from the previous pick day."""
        if not self.last_pick_date:
            return
        async for msg in channel.history(limit=50):
            if "Today's vlogger:" in msg.content:
                try:
                    msg_date_str = msg.content.splitlines()[0].split(":")[1].strip()
                    msg_date = datetime.strptime(msg_date_str, "%Y-%m-%d").date()
                    if msg_date == self.last_pick_date:
                        await msg.delete()
                        break
                except Exception:
                    continue

    async def recover_state_from_messages(self, channel):
        """Recover the bot state from the last pick message in the channel."""
        try:
            async for msg in channel.history(limit=20):
                if "Today's vlogger:" in msg.content:
                    lines = msg.content.splitlines()

                    # Parse last pick date
                    self.last_pick_date = datetime.strptime(
                        lines[0].split(":")[1].strip(), "%Y-%m-%d"
                    ).date()

                    guild = self.guilds[0]  # assumes single guild

                    # Parse current pick
                    user_id = int(lines[1].split("(")[1].strip(")"))
                    self.current_pick = guild.get_member(user_id)

                    # Parse gone and remaining
                    def parse_users(line):
                        users = []
                        if ": None" not in line:
                            for part in line.split(":")[1].split(","):
                                uid = int(part.split("(")[1].strip(")"))
                                member = guild.get_member(uid)
                                if member:
                                    users.append(member)
                        return users

                    gone = parse_users(lines[2])
                    remaining = parse_users(lines[3])

                    self.remaining_picks = remaining
                    self.vloggers = gone + remaining
                    print(f"Recovered state: {len(self.vloggers)} vloggers, current pick: {self.current_pick}")
                    break
        except Exception as e:
            print(f"Could not recover state from messages: {e}")

    async def send_daily_pick_message(self, channel):
        """Send today's pick message with all details."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        gone = [v for v in self.vloggers if v not in self.remaining_picks]
        remaining = self.remaining_picks

        gone_text = self.format_vlogger_list(gone)
        remaining_text = self.format_vlogger_list(remaining)

        if self.current_pick:
            pick_text = f"{self.current_pick.name}"
            pick_id = self.current_pick.id
        else:
            pick_text = "No one picked yet"
            pick_id = "N/A"

        await channel.send(
            f"📅 Date: {today_str}\n"
            f"🎬 Today's vlogger: {pick_text} \n"
            f"✅ Already gone this cycle: {gone_text}\n"
            f"⏳ Still remaining: {remaining_text}"
        )

    # -------------------- Event Handlers --------------------

    async def on_ready(self):
        print(f'Logged on as {self.user}')
        channel = await self.get_channel_safe()
        if not channel:
            return

        # Recover state from last pick message
        await self.recover_state_from_messages(channel)

        if not self.daily_task:
            self.daily_task = self.loop.create_task(self.daily_picker())

    async def on_message(self, message):
        if message.author == self.user:
            return
        
        if message.content.startswith('!help'):
            help_text = (
                "**Vlog Bot Commands:**\n"
                "`!joinVlogs` — Join the daily vlogging rotation\n"
                "`!list` — Show all vloggers, current pick, and cycle progress\n"
            )
            await message.channel.send(help_text)
            return

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

        if message.content.startswith('!joinVlogs'):
            if message.author not in self.vloggers:
                self.vloggers.append(message.author)
                self.remaining_picks.append(message.author)
                vloggers_list = ", ".join([user.mention for user in self.vloggers])
                await message.channel.send(
                    f"{message.author.mention} has joined the vlogs!\n"
                    f"Vloggers: {vloggers_list}\n"
                    "One vlogger will be picked randomly each day to create a vlog."
                )
                print(f'Current vloggers: {[user.name for user in self.vloggers]}')
            else:
                await message.channel.send(f'{message.author.mention}, you are already in the list.')

    # -------------------- Daily Picker --------------------

    async def daily_picker(self):
        await self.wait_until_ready()
        channel = await self.get_channel_safe()
        if not channel:
            print(f"Channel with ID {CHANNEL_ID} is not a text channel or does not exist.")
            return

        while not self.is_closed():
            now = datetime.now()
            next_pick_time = datetime.combine(now.date(), datetime.min.time())
            if now >= next_pick_time:
                next_pick_time += timedelta(days=1)

            wait_seconds = (next_pick_time - now).total_seconds()
            await asyncio.sleep(wait_seconds)

            if not self.vloggers:
                await channel.send('No one has joined the vlogs yet today!')
                continue

            # Reset remaining picks if all have been picked
            if not self.remaining_picks:
                self.remaining_picks = self.vloggers.copy()

            today = datetime.now().date()
            if self.last_pick_date != today:
                if not self.remaining_picks:
                    self.remaining_picks = self.vloggers.copy()

                self.current_pick = random.choice(self.remaining_picks)
                self.remaining_picks.remove(self.current_pick)

                # Delete previous day's pick
                await self.delete_last_pick_message(channel)

                self.last_pick_date = today
                await self.send_daily_pick_message(channel)


# -------------------- Run Bot --------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = Client(intents=intents)
bot.run(TOKEN)
