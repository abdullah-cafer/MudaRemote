import sys
import asyncio
import discord
from discord.ext import commands
import re
import json
import threading
import datetime
import inquirer
import logging

# Global bot name
BOT_NAME = "MudaRemote"

# Load presets from JSON file
presets = {}
try:
    with open("presets.json", "r") as f:
        presets = json.load(f)
except FileNotFoundError:
    print("presets.json file not found. Please create it and enter the required information.")
    sys.exit(1)

# Target bot ID (Mudae's ID)
TARGET_BOT_ID = 432610292342587392

# ANSI color codes for logging
COLORS = {
    "INFO": "\033[94m",    # Blue
    "CLAIM": "\033[92m",   # Green
    "KAKERA": "\033[93m",  # Yellow
    "ERROR": "\033[91m",   # Red
    "CHECK": "\033[95m",   # Magenta
    "RESET": "\033[36m",   # Cyan
    "ENDC": "\033[0m"      # End Color
}

# Define claim and kakera emojis
CLAIM_EMOJIS = ['💖', '💗', '💘', '❤️', '💓', '💕', '♥️', '🪐']
KAKERA_EMOJIS = ['kakeraY', 'kakeraO', 'kakeraR', 'kakeraW', 'kakeraL']

# Logging functions
def color_log(message, preset_name, log_type="INFO"):
    """Format log messages with colors and timestamps."""
    color_code = COLORS.get(log_type.upper(), COLORS["INFO"])
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}][{preset_name}] {message}"
    print(f"{color_code}{log_message}{COLORS['ENDC']}")
    return log_message

def write_log_to_file(log_message):
    """Write log messages to a file."""
    try:
        with open("logs.txt", "a") as log_file:
            log_file.write(log_message + "\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")

def print_log(message, preset_name, log_type="INFO"):
    """Print and log messages."""
    log_message_formatted = color_log(message, preset_name, log_type)
    write_log_to_file(log_message_formatted)

# Main bot function
def run_bot(token, prefix, target_channel_id, roll_command, min_kakera, delay_seconds, mudae_prefix,
            log_function, preset_name, key_mode, start_delay, snipe_mode, snipe_delay,
            snipe_ignore_min_kakera_reset, wishlist, series_snipe_mode, series_snipe_delay,
            series_wishlist, roll_speed, kakera_snipe_mode=False, kakera_snipe_threshold=0,
            kakera_snipe_delay=2):
    """Run the MudaRemote bot with the specified configuration."""
    client = commands.Bot(command_prefix=prefix, chunk_guilds_at_startup=False)

    # Disable discord.py's default console logging
    discord_logger = logging.getLogger('discord')
    discord_logger.propagate = False
    handlers = [h for h in discord_logger.handlers if isinstance(h, logging.StreamHandler)]
    for handler in handlers:
        discord_logger.removeHandler(handler)

    # Store preset-specific settings in the client
    client.preset_name = preset_name
    client.min_kakera = min_kakera
    client.snipe_mode = snipe_mode
    client.snipe_delay = snipe_delay
    client.snipe_ignore_min_kakera_reset = snipe_ignore_min_kakera_reset
    client.wishlist = wishlist
    client.series_snipe_mode = series_snipe_mode
    client.series_snipe_delay = series_snipe_delay
    client.series_wishlist = series_wishlist
    client.muda_name = BOT_NAME
    client.claim_right_available = False
    client.target_channel_id = target_channel_id
    client.roll_speed = roll_speed
    client.kakera_snipe_mode = kakera_snipe_mode
    client.kakera_snipe_threshold = kakera_snipe_threshold
    client.kakera_snipe_delay = kakera_snipe_delay
    client.maintenance_mode = False
    client.rolling = False
    client.sniped_messages = set()
    client.snipe_happened = False
    client.series_sniped_messages = set()
    client.series_snipe_happened = False
    client.kakera_sniped_messages = set()
    client.kakera_snipe_happened = False

    @client.event
    async def on_ready():
        """Handle bot startup."""
        log_function(f"[{client.muda_name}] Bot is ready.", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Delay: {delay_seconds} seconds", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Start Delay: {start_delay} seconds", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Key Mode: {'Enabled' if key_mode else 'Disabled'}", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Snipe Mode: {'Enabled' if snipe_mode else 'Disabled'}", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Series Snipe Mode: {'Enabled' if series_snipe_mode else 'Disabled'}", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Kakera Snipe Mode: {'Enabled' if kakera_snipe_mode else 'Disabled'}", preset_name, "INFO")
        if kakera_snipe_mode:
            log_function(f"[{client.muda_name}] Kakera Snipe Threshold: {kakera_snipe_threshold}", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Roll Speed: {roll_speed} seconds", preset_name, "INFO")
        await asyncio.sleep(start_delay)
        await asyncio.sleep(delay_seconds)
        channel = client.get_channel(target_channel_id)
        try:
            await channel.send(f"{mudae_prefix}limroul 1 1 1 1")
            await asyncio.sleep(0.5)
            await channel.send(f"{mudae_prefix}dk")
            await asyncio.sleep(0.5)
            await channel.send(f"{mudae_prefix}daily")
            await asyncio.sleep(0.5)
            await check_status(client, channel, mudae_prefix)
        except discord.errors.Forbidden as e:
            log_function(f"[{client.muda_name}] Error: Cannot send messages to channel, permission denied. {e}", preset_name, "ERROR")
            await client.close()

    async def check_status(client, channel, mudae_prefix):
        """Check claim rights and rolls using $tu command."""
        log_function(f"[{client.muda_name}] Checking claim rights and rolls using $tu...", preset_name, "CHECK")
        error_count = 0
        max_retries = 5
        while True:
            await channel.send(f"{mudae_prefix}tu")
            await asyncio.sleep(1)
            try:
                async for msg in channel.history(limit=2):
                    if msg.author.id == TARGET_BOT_ID:
                        content_lower = msg.content.lower()
                        if "you __can__ claim" in content_lower:
                            client.claim_right_available = True
                            match_claim = re.search(r"next claim reset is in \*\*(\d+h)?\s*(\d+)\*\* min", content_lower)
                            if match_claim:
                                hours = int(match_claim.group(1)[:-1]) if match_claim.group(1) else 0
                                minutes = int(match_claim.group(2))
                                remaining_seconds = (hours * 60 + minutes) * 60
                                if remaining_seconds <= 3600:
                                    if client.snipe_mode and client.snipe_ignore_min_kakera_reset:
                                        log_function(f"[{client.muda_name}] Claim right available (<1h) and snipe override active; ignoring min_kakera limit.", preset_name, "INFO")
                                        await check_rolls_left_tu(client, channel, mudae_prefix, ignore_limit=True)
                                    else:
                                        log_function(f"[{client.muda_name}] Claim right available (<1h) but snipe override inactive; applying claim limit.", preset_name, "INFO")
                                        await check_rolls_left_tu(client, channel, mudae_prefix, ignore_limit=False)
                                else:
                                    log_function(f"[{client.muda_name}] Claim right available (>1h remaining); applying claim limit.", preset_name, "INFO")
                                    await check_rolls_left_tu(client, channel, mudae_prefix, ignore_limit=False)
                                return
                            else:
                                raise ValueError("Claim time information could not be parsed from $tu output.")
                        elif "you can't claim for another" in content_lower:
                            client.claim_right_available = False
                            match_claim_wait = re.search(r"you can't claim for another \*\*(\d+h)?\s*(\d+)\*\* min", content_lower)
                            if match_claim_wait:
                                hours = int(match_claim_wait.group(1)[:-1]) if match_claim_wait.group(1) else 0
                                minutes = int(match_claim_wait.group(2))
                                total_seconds = (hours * 60 + minutes) * 60
                                if key_mode:
                                    log_function(f"[{client.muda_name}] Claim right not available, but Key Mode is enabled. Rolling for kakera only.", preset_name, "INFO")
                                    await check_rolls_left_tu(client, channel, mudae_prefix, ignore_limit=True, key_mode_only_kakera=True)
                                    return
                                else:
                                    log_function(f"[{client.muda_name}] Claim right not available. Will retry in {hours}h {minutes}min.", preset_name, "INFO")
                                    await wait_for_reset(total_seconds, delay_seconds, log_function, preset_name)
                                    await check_status(client, channel, mudae_prefix)
                                    return
                            else:
                                raise ValueError("Claim waiting time not found in $tu output.")
                        else:
                            raise ValueError("Claim right status not found in $tu output.")
                raise ValueError("Mudae $tu message not found.")
            except ValueError as e:
                error_count += 1
                log_function(f"[{client.muda_name}] Error: {e}", preset_name, "ERROR")
                if error_count >= max_retries:
                    log_function(f"[{client.muda_name}] Max retries reached for $tu claim rights. Retrying in 30 minutes.", preset_name, "ERROR")
                    await asyncio.sleep(1800)
                    error_count = 0
                else:
                    log_function(f"[{client.muda_name}] Claim right check failed using $tu. Retrying in 5 seconds.", preset_name, "ERROR")
                    await asyncio.sleep(5)
                continue
            except Exception as e:
                error_count += 1
                log_function(f"[{client.muda_name}] Unexpected error: {e}", preset_name, "ERROR")
                if error_count >= max_retries:
                    log_function(f"[{client.muda_name}] Max retries reached for $tu claim rights. Retrying in 30 minutes.", preset_name, "ERROR")
                    await asyncio.sleep(1800)
                    error_count = 0
                else:
                    log_function(f"[{client.muda_name}] Claim right check failed using $tu. Retrying in 5 seconds.", preset_name, "ERROR")
                    await asyncio.sleep(5)
                continue

    async def check_rolls_left_tu(client, channel, mudae_prefix, ignore_limit=False, key_mode_only_kakera=False):
        """Parse rolls left from $tu output and proceed accordingly."""
        log_function(f"[{client.muda_name}] Checking rolls left using $tu...", preset_name, "CHECK")
        error_count = 0
        max_retries = 5
        while True:
            # Try to find the most recent $tu response from Mudae
            tu_message = None
            async for msg in channel.history(limit=5): # Check more messages if needed
                # --- CORRECTION START ---
                # Check if it's from Mudae and contains the roll count phrase.
                # REMOVED: "$tu" in msg.content.lower() check, because Mudae's response doesn't contain it.
                if msg.author.id == TARGET_BOT_ID and "you have" in msg.content.lower():
                # --- CORRECTION END ---
                    tu_message = msg
                    break # Found the relevant message

            if tu_message:
                content_lower = tu_message.content.lower()
                # Updated regex to handle optional text like "(+++X** $mk)" before "left"
                match_rolls = re.search(r"you have \*\*(\d+)\*\* rolls?(?: \(.+?\))? left", content_lower)

                if match_rolls:
                    rolls_left = int(match_rolls.group(1))
                    reset_match = re.search(r"next rolls? reset in \*\*(\d+)\*\* min", content_lower)
                    reset_time = int(reset_match.group(1)) if reset_match else 0
                    if not reset_match:
                        log_function(f"[{client.muda_name}] Warning: Could not parse roll reset time from $tu output.", preset_name, "ERROR")

                    if rolls_left == 0:
                        log_function(f"[{client.muda_name}] No rolls left. Reset in {reset_time} min.", preset_name, "RESET")
                        await wait_for_rolls_reset(reset_time, delay_seconds, log_function, preset_name)
                        await check_status(client, channel, mudae_prefix)
                        return
                    else:
                        log_function(f"[{client.muda_name}] Rolls left: {rolls_left}", preset_name, "INFO")
                        await start_roll_commands(client, channel, rolls_left, ignore_limit, key_mode_only_kakera)
                        return
                else:
                    # If the regex failed on the found message, log the specific message
                    log_function(f"[{client.muda_name}] Error: Could not parse roll information from $tu output: {tu_message.content}", preset_name, "ERROR")
                    # Fall through to retry logic
            else:
                 # If no suitable message was found in history
                 log_function(f"[{client.muda_name}] Error: Could not find recent $tu response containing roll info.", preset_name, "ERROR")
                 # Fall through to retry logic

            # Retry logic
            error_count += 1
            log_function(f"[{client.muda_name}] Roll check failed using $tu ({error_count}/{max_retries}). Retrying in 5 seconds.", preset_name, "ERROR")
            if error_count >= max_retries:
                log_function(f"[{client.muda_name}] Max retries reached for $tu rolls check. Retrying in 30 minutes.", preset_name, "ERROR")
                await asyncio.sleep(1800)
                error_count = 0 # Reset error count after long wait
                await channel.send(f"{mudae_prefix}tu") # Send tu again before restarting loop
                await asyncio.sleep(2) # Wait for potential response
            else:
                await asyncio.sleep(5)
            # Continue loop to retry fetching/parsing


    async def start_roll_commands(client, channel, rolls_left, ignore_limit=False, key_mode_only_kakera=False):
        """Execute roll commands and handle responses."""
        try:
            if client.maintenance_mode:
                log_function(f"[{client.muda_name}] Roll commands suspended due to maintenance.", preset_name, "RESET")
                return
            client.rolling = True
            for _ in range(rolls_left):
                await channel.send(f"{mudae_prefix}{roll_command}")
                await asyncio.sleep(client.roll_speed)
            await asyncio.sleep(4)
            await check_new_characters(client, channel)
            mudae_messages = []
            async for msg in channel.history(limit=rolls_left * 2, oldest_first=False):
                if msg.author.id == TARGET_BOT_ID:
                    mudae_messages.append(msg)
            log_function(f"[{client.muda_name}] Fetched {len(mudae_messages)} Mudae messages.", preset_name, "INFO")
            await handle_mudae_messages(client, channel, mudae_messages, ignore_limit, key_mode_only_kakera)
            log_function(f"[{client.muda_name}] Finished handling Mudae messages.", preset_name, "INFO")
            client.rolling = False
            await asyncio.sleep(2)
            if client.snipe_happened or client.series_snipe_happened or client.kakera_snipe_happened:
                client.snipe_happened = client.series_snipe_happened = client.kakera_snipe_happened = False
                await asyncio.sleep(2)
                log_function(f"[{client.muda_name}] Sniping occurred, flags reset.", preset_name, "INFO")
            await check_status(client, channel, mudae_prefix)
        except Exception as e:
            log_function(f"[{client.muda_name}] Exception in start_roll_commands: {str(e)}", preset_name, "ERROR")
            await asyncio.sleep(5)
            await check_status(client, channel, mudae_prefix)

    async def handle_mudae_messages(client, channel, mudae_messages, ignore_limit=False, key_mode_only_kakera=False):
        """Process Mudae messages for kakera and character claims."""
        # Kakera claim logic
        for msg in mudae_messages:
            if msg.embeds and msg.components:
                embed = msg.embeds[0]
                for component in msg.components:
                    for button in component.children:
                        if button.emoji and button.emoji.name in KAKERA_EMOJIS:
                            try:
                                await button.click()
                                log_function(f"[{client.muda_name}] Claimed Kakera: {embed.author.name}", preset_name, "KAKERA")
                                await asyncio.sleep(3)
                            except discord.errors.HTTPException as e:
                                log_function(f"[{client.muda_name}] Kakera claim error: {e}", preset_name, "ERROR")

        # Character claim logic
        if not client.claim_right_available and key_mode:
            highest_claim_character = None
            highest_claim_character_message = None
            for msg in mudae_messages:
                if msg.embeds and msg.embeds[0].color.value in [16751916, 1360437]:
                    embed = msg.embeds[0]
                    description = embed.description or ""
                    match = re.search(r"\*\*([\d,]+)\*\*<:kakera:", description)
                    if match:
                        kakera_value = int(match.group(1).replace(",", ""))
                        if (not highest_claim_character or kakera_value > highest_claim_character) and (ignore_limit or kakera_value > client.min_kakera):
                            highest_claim_character = kakera_value
                            highest_claim_character_message = msg
            if highest_claim_character_message and highest_claim_character > client.min_kakera:
                await channel.send(f"{mudae_prefix}rt")
                await asyncio.sleep(0.5)
                await claim_character(client, channel, highest_claim_character_message, is_rt_claim=True)
        elif client.claim_right_available:
            highest_claim_character = highest_claim_character_message = None
            second_highest_claim_character = second_highest_claim_character_message = None
            for msg in mudae_messages:
                if msg.embeds and msg.embeds[0].color.value in [16751916, 1360437]:
                    embed = msg.embeds[0]
                    description = embed.description or ""
                    match = re.search(r"\*\*([\d,]+)\*\*<:kakera:", description)
                    if match:
                        kakera_value = int(match.group(1).replace(",", ""))
                        if (not highest_claim_character or kakera_value > highest_claim_character) and (ignore_limit or kakera_value > client.min_kakera):
                            second_highest_claim_character = highest_claim_character
                            second_highest_claim_character_message = highest_claim_character_message
                            highest_claim_character = kakera_value
                            highest_claim_character_message = msg
                        elif (not second_highest_claim_character or kakera_value > second_highest_claim_character) and (ignore_limit or kakera_value > client.min_kakera):
                            second_highest_claim_character = kakera_value
                            second_highest_claim_character_message = msg
            if highest_claim_character_message:
                await claim_character(client, channel, highest_claim_character_message)
                if second_highest_claim_character_message and second_highest_claim_character > client.min_kakera:
                    await channel.send(f"{mudae_prefix}rt")
                    await asyncio.sleep(0.5)
                    await claim_character(client, channel, second_highest_claim_character_message, is_rt_claim=True)

    async def claim_character(client, channel, msg, is_kakera=False, is_rt_claim=False):
        """Claim a character or kakera by clicking a button or adding a reaction."""
        log_message = "Claimed Kakera" if is_kakera else ("Claimed Character with $rt" if is_rt_claim else "Claimed Character")
        log_type = "KAKERA" if is_kakera else "CLAIM"
        if msg.components:
            for component in msg.components:
                for button in component.children:
                    if button.emoji and button.emoji.name in (KAKERA_EMOJIS if is_kakera else CLAIM_EMOJIS):
                        try:
                            await button.click()
                            log_function(f"[{client.muda_name}] {log_message}: {msg.embeds[0].author.name}", client.preset_name, log_type)
                            await asyncio.sleep(3)
                            return
                        except discord.errors.HTTPException as e:
                            log_function(f"[{client.muda_name}] Claim error: {e}", client.preset_name, "ERROR")
        else:
            try:
                await msg.add_reaction("✅")
                log_function(f"[{client.muda_name}] {log_message}: {msg.embeds[0].author.name if msg.embeds else 'Character'}", client.preset_name, log_type)
                await asyncio.sleep(3)
            except discord.errors.HTTPException:
                log_function(f"[{client.muda_name}] Reaction could not be added.", client.preset_name, "ERROR")

    async def check_new_characters(client, channel):
        """Placeholder for checking new characters (to be implemented)."""
        async for msg in channel.history(limit=15):
            if msg.author.id == TARGET_BOT_ID and msg.embeds:
                embed = msg.embeds[0]
                if re.search(r"Claims: \#\d+", embed.description or ""):
                    pass  # Future implementation here

    async def wait_for_reset(seconds, delay_seconds, log_function, preset_name):
        """Wait for claim reset."""
        now = datetime.datetime.now()
        target_time = now + datetime.timedelta(seconds=seconds)
        target_time = target_time.replace(second=0, microsecond=0)
        if target_time < now:
            target_time += datetime.timedelta(minutes=1)
        wait_seconds = (target_time - now).total_seconds() + delay_seconds
        log_function(f"[{client.muda_name}] Waiting for reset. Target time: {target_time.strftime('%H:%M:%S')}", preset_name, "RESET")
        await asyncio.sleep(wait_seconds)

    async def wait_for_rolls_reset(reset_time_minutes, delay_seconds, log_function, preset_name):
        """Wait for rolls reset."""
        now = datetime.datetime.now()
        target_minute = (now.minute + reset_time_minutes) % 60
        target_time = now.replace(minute=target_minute, second=0, microsecond=0)
        if target_time < now:
            target_time += datetime.timedelta(hours=1)
        wait_seconds = (target_time - now).total_seconds() + delay_seconds
        log_function(f"[{client.muda_name}] Waiting for rolls reset. Target time: {target_time.strftime('%H:%M:%S')}", preset_name, "RESET")
        await asyncio.sleep(wait_seconds)

    @client.event
    async def on_message(message):
        """Handle real-time sniping and maintenance detection."""
        if message.author.id != TARGET_BOT_ID:
            await client.process_commands(message)
            return

        if "maintenance" in message.content.lower():
            if not client.maintenance_mode:
                client.maintenance_mode = True
                log_function(f"[{client.muda_name}] Maintenance detected! Suspending rolls for 30 minutes.", preset_name, "RESET")
                await asyncio.sleep(1800)
                client.maintenance_mode = False
                log_function(f"[{client.muda_name}] Maintenance period over. Resuming rolls.", preset_name, "RESET")
            await client.process_commands(message)
            return

        if not message.embeds or (not client.claim_right_available and not client.series_snipe_mode and not client.snipe_mode and not client.kakera_snipe_mode) or client.rolling:
            await client.process_commands(message)
            return

        embed = message.embeds[0]
        # Series sniping
        if client.series_snipe_mode and client.series_wishlist and message.channel.id == client.target_channel_id:
            description = embed.description or ""
            first_line = description.splitlines()[0]
            if any(kw.lower() in first_line.lower() for kw in client.series_wishlist if kw):
                if any(button.emoji and button.emoji.name in CLAIM_EMOJIS for comp in message.components for button in comp.children):
                    if message.id not in client.series_sniped_messages:
                        client.series_sniped_messages.add(message.id)
                        log_function(f"[{client.muda_name}] (Real-time) Series snipe: {first_line}", preset_name, "CLAIM")
                        await asyncio.sleep(client.series_snipe_delay)
                        await claim_character(client, message.channel, message)
                        client.series_snipe_happened = True
                        await asyncio.sleep(2)
                        await client.process_commands(message)
                        return

        # Normal sniping
        if client.snipe_mode and client.wishlist and message.channel.id == client.target_channel_id:
            character_name = embed.author.name if embed.author else None
            if character_name and any(wish.lower() in character_name.lower() for wish in client.wishlist if wish):
                if any(button.emoji and button.emoji.name in CLAIM_EMOJIS for comp in message.components for button in comp.children):
                    if message.id not in client.sniped_messages:
                        client.sniped_messages.add(message.id)
                        log_function(f"[{client.muda_name}] (Real-time) Snipe: {character_name}", preset_name, "CLAIM")
                        await asyncio.sleep(client.snipe_delay)
                        await claim_character(client, message.channel, message)
                        client.snipe_happened = True
                        await asyncio.sleep(2)
                        await client.process_commands(message)
                        return

        # Kakera sniping
        if client.kakera_snipe_mode and message.channel.id == client.target_channel_id and embed.color.value in [16751916, 1360437]:
            description = embed.description or ""
            match = re.search(r"\*\*([\d,]+)\*\*<:kakera:", description)
            if match:
                kakera_value = int(match.group(1).replace(",", ""))
                if kakera_value >= client.kakera_snipe_threshold:
                    if message.id not in client.kakera_sniped_messages:
                        client.kakera_sniped_messages.add(message.id)
                        character_name = embed.author.name if embed.author else "Unknown Character"
                        log_function(f"[{client.muda_name}] (Real-time) Kakera snipe: {character_name} - {kakera_value}", preset_name, "CLAIM")
                        await asyncio.sleep(client.kakera_snipe_delay)
                        await claim_character(client, message.channel, message)
                        client.kakera_snipe_happened = True
                        await asyncio.sleep(2)
                        await client.process_commands(message)
                        return

        await client.process_commands(message)

    client.run(token)

# User interface functions
def show_banner():
    """Display the MudaRemote banner."""
    banner = r"""
  __  __ _    _ _____          _____  ______ __  __  ____ _______ ______
 |  \/  | |  | |  __ \   /\   |  __ \|  ____|  \/  |/ __ \__   __|  ____|
 | \  / | |  | | |  | | /  \  | |__) | |__  | \  / | |  | | | |  | |__
 | |\/| | |  | | |  | |/ /\ \ |  _  /|  __| | |\/| | |  | | | |  |  __|
 | |  | | |__| | |__| / ____ \| | \ \| |____| |  | | |__| | | |  | |____
 |_|  |_|\____/|_____/_/    \_\_|  \_\______|_|  |_|\____/  |_|  |______|
    """
    print("\033[1;36m" + banner + "\033[0m")
    print("\033[1;33mWelcome to MudaRemote - Your Remote Mudae Assistant\033[0m\n")

def main_menu():
    """Display the main menu and handle user input."""
    show_banner()
    while True:
        questions = [
            inquirer.List('option',
                          message="Please select an option:",
                          choices=['Select and Run Preset', 'Select and Run Multiple Presets', 'Exit'])
        ]
        answers = inquirer.prompt(questions)
        if answers['option'] == 'Select and Run Preset':
            select_and_run_preset()
        elif answers['option'] == 'Select and Run Multiple Presets':
            select_and_run_multiple_presets()
        elif answers['option'] == 'Exit':
            print("\033[1;32mExiting MudaRemote. Goodbye!\033[0m")
            break

def select_and_run_preset():
    """Select and run a single preset."""
    preset_list = list(presets.keys())
    if not preset_list:
        print("No presets found.")
        return
    questions = [inquirer.List('preset', message="Select a preset to run:", choices=preset_list)]
    answers = inquirer.prompt(questions)
    preset_name = answers['preset']
    preset = presets[preset_name]
    run_preset(preset, preset_name)

def select_and_run_multiple_presets():
    """Select and run multiple presets."""
    preset_list = list(presets.keys())
    if not preset_list:
        print("No presets found.")
        return
    questions = [inquirer.Checkbox('presets', message="Select presets to run:", choices=preset_list)]
    answers = inquirer.prompt(questions)
    for preset_name in answers['presets']:
        preset = presets[preset_name]
        run_preset(preset, preset_name)

def run_preset(preset, preset_name):
    """Helper function to run a preset in a separate thread."""
    threading.Thread(target=run_bot, args=(
        preset["token"],
        preset["prefix"],
        preset["channel_id"],
        preset["roll_command"],
        preset["min_kakera"],
        preset["delay_seconds"],
        preset["mudae_prefix"],
        print_log,
        preset_name,
        preset.get("key_mode", False),
        preset.get("start_delay", 0),
        preset.get("snipe_mode", False),
        preset.get("snipe_delay", 5),
        preset.get("snipe_ignore_min_kakera_reset", False),
        preset.get("wishlist", []),
        preset.get("series_snipe_mode", False),
        preset.get("series_snipe_delay", 5),
        preset.get("series_wishlist", []),
        preset.get("roll_speed", 0.3),
        preset.get("kakera_snipe_mode", False),
        preset.get("kakera_snipe_threshold", 0),
        preset.get("kakera_snipe_delay", 2)
    )).start()

if __name__ == "__main__":
    main_menu()
