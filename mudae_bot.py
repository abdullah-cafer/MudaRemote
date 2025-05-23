import sys
import asyncio
import discord
from discord.ext import commands
import re
import json
import threading
import datetime
from datetime import timezone # Ensure timezone is imported
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
    print("presets.json file not found. Please create it and enter the necessary information.")
    sys.exit(1)
except json.JSONDecodeError:
    print("Error decoding presets.json. Please check the file format.")
    sys.exit(1)


# Target bot ID (Mudae's ID)
TARGET_BOT_ID = 432610292342587392

# ANSI color codes
COLORS = {
    "INFO": "\033[94m",    # Blue
    "CLAIM": "\033[92m",   # Green
    "KAKERA": "\033[93m",  # Yellow
    "ERROR": "\033[91m",    # Red
    "CHECK": "\033[95m",    # Magenta
    "RESET": "\033[36m",    # Cyan
    "ENDC": "\033[0m"      # End Color
}

# Define claim and kakera emojis at the top level
CLAIM_EMOJIS = ['💖', '💗', '💘', '❤️', '💓', '💕', '♥️', '🪐']
KAKERA_EMOJIS = ['kakeraY', 'kakeraO', 'kakeraR', 'kakeraW', 'kakeraL']


def color_log(message, preset_name, log_type="INFO"):
    """Formats a log message with timestamp, preset name, and color."""
    color_code = COLORS.get(log_type.upper(), COLORS["INFO"])
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}][{preset_name}] {message}"
    print(f"{color_code}{log_message}{COLORS['ENDC']}")
    return log_message

def write_log_to_file(log_message):
    """Appends a log message to the logs.txt file."""
    try:
        # Ensure logs.txt exists, create if not
        with open("logs.txt", "a", encoding='utf-8') as log_file: # Specify encoding
            log_file.write(log_message + "\n")
    except Exception as e:
        # Fallback to print error to console if file writing fails
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\033[91m[{timestamp}][System] Error writing to log file: {e}\033[0m")


def print_log(message, preset_name, log_type="INFO"):
    """Prints a colored log message to the console and writes it to the log file."""
    log_message_formatted = color_log(message, preset_name, log_type)
    write_log_to_file(log_message_formatted)


def run_bot(token, prefix, target_channel_id, roll_command, min_kakera, delay_seconds, mudae_prefix,
            log_function, preset_name, key_mode, start_delay, snipe_mode, snipe_delay,
            snipe_ignore_min_kakera_reset, wishlist,
            series_snipe_mode, series_snipe_delay, series_wishlist, roll_speed):
    """Sets up and runs a single bot instance based on preset settings."""

    client = commands.Bot(command_prefix=prefix, chunk_guilds_at_startup=False)

    # Disable discord.py's default logging to console
    discord_logger = logging.getLogger('discord')
    discord_logger.propagate = False
    # Remove existing StreamHandlers if any
    handlers = [handler for handler in discord_logger.handlers if isinstance(handler, logging.StreamHandler)]
    for handler in handlers:
        discord_logger.removeHandler(handler)

    # Store preset-specific settings in the client
    client.preset_name = preset_name
    client.min_kakera = min_kakera
    client.snipe_mode = snipe_mode
    client.snipe_delay = snipe_delay
    client.snipe_ignore_min_kakera_reset = snipe_ignore_min_kakera_reset
    client.wishlist = [w.lower() for w in wishlist] # Store wishlist as lowercase
    client.series_snipe_mode = series_snipe_mode
    client.series_snipe_delay = series_snipe_delay
    client.series_wishlist = [sw.lower() for sw in series_wishlist] # Store series wishlist as lowercase
    client.muda_name = BOT_NAME # Use the global bot name
    client.claim_right_available = False
    client.target_channel_id = target_channel_id
    client.roll_speed = roll_speed
    client.mudae_prefix = mudae_prefix # Store mudae prefix
    # Store key_mode and delay_seconds on client for access in check_status
    client.key_mode = key_mode
    client.delay_seconds = delay_seconds

    # Initialize sniping trackers
    client.sniped_messages = set()
    client.snipe_happened = False
    client.series_sniped_messages = set()
    client.series_snipe_happened = False

    @client.event
    async def on_ready():
        log_function(f"[{client.muda_name}] Bot is ready. User: {client.user}", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Target Channel ID: {target_channel_id}", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Delay: {delay_seconds} seconds", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Start Delay: {start_delay} seconds", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Key Mode: {'Enabled' if key_mode else 'Disabled'}", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Snipe Mode: {'Enabled' if snipe_mode else 'Disabled'}", preset_name, "INFO")
        if snipe_mode:
            log_function(f"[{client.muda_name}] Snipe Delay: {snipe_delay}s", preset_name, "INFO")
            log_function(f"[{client.muda_name}] Snipe Wishlist Size: {len(client.wishlist)}", preset_name, "INFO")
            log_function(f"[{client.muda_name}] Snipe Ignore Min Kakera Reset: {snipe_ignore_min_kakera_reset}", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Series Snipe Mode: {'Enabled' if series_snipe_mode else 'Disabled'}", preset_name, "INFO")
        if series_snipe_mode:
            log_function(f"[{client.muda_name}] Series Snipe Delay: {series_snipe_delay}s", preset_name, "INFO")
            log_function(f"[{client.muda_name}] Series Wishlist Size: {len(client.series_wishlist)}", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Roll Speed: {roll_speed} seconds", preset_name, "INFO")
        log_function(f"[{client.muda_name}] Min Kakera Value: {client.min_kakera}", preset_name, "INFO")

        # Validate Channel Access
        channel = client.get_channel(target_channel_id)
        if not channel:
            log_function(f"[{client.muda_name}] Error: Cannot find channel with ID {target_channel_id}. Check the ID and bot's permissions.", preset_name, "ERROR")
            await client.close()
            return
        # Basic check if it's a text channel (might need refinement based on discord.py version)
        if not isinstance(channel, discord.TextChannel):
             log_function(f"[{client.muda_name}] Error: Target ID {target_channel_id} does not belong to a valid text channel.", preset_name, "ERROR")
             await client.close()
             return
        if not channel.permissions_for(channel.guild.me).send_messages:
            log_function(f"[{client.muda_name}] Error: Bot does not have permission to send messages in channel {channel.name} ({target_channel_id}).", preset_name, "ERROR")
            await client.close()
            return
        if not channel.permissions_for(channel.guild.me).read_message_history:
             log_function(f"[{client.muda_name}] Error: Bot does not have permission to read message history in channel {channel.name} ({target_channel_id}).", preset_name, "ERROR")
             await client.close()
             return
        if not channel.permissions_for(channel.guild.me).add_reactions:
            log_function(f"[{client.muda_name}] Warning: Bot does not have permission to add reactions in channel {channel.name} ({target_channel_id}). Claiming might fail if buttons aren't available.", preset_name, "ERROR") # Changed to ERROR as it's critical

        log_function(f"[{client.muda_name}] Initial delay of {start_delay} seconds...", preset_name, "INFO")
        await asyncio.sleep(start_delay)

        try:
            log_function(f"[{client.muda_name}] Sending initial commands...", preset_name, "INFO")
            await channel.send(f"{client.mudae_prefix}limroul 1 1 1 1")
            await asyncio.sleep(1.0)
            await channel.send(f"{client.mudae_prefix}dk")
            await asyncio.sleep(1.0)
            await channel.send(f"{client.mudae_prefix}daily")
            await asyncio.sleep(1.0)
            await check_status(client, channel, client.mudae_prefix) # Use combined status check
        except discord.errors.Forbidden as e:
            log_function(f"[{client.muda_name}] Error: Permission denied to send messages in the target channel. {e}", preset_name, "ERROR")
            await client.close()
        except Exception as e:
            log_function(f"[{client.muda_name}] Error during initial setup/commands: {e}", preset_name, "ERROR")
            await client.close()

    # --- MODIFIED check_status FUNCTION ---
    async def check_status(client, channel, mudae_prefix):
        """Checks claim rights and rolls using $tu and proceeds."""
        log_function(f"[{client.muda_name}] Checking claim rights and rolls using {mudae_prefix}tu...", client.preset_name, "CHECK")
        error_count = 0
        max_retries = 5
        while True: # This loop is primarily for retrying $tu if it fails
            await channel.send(f"{mudae_prefix}tu")
            await asyncio.sleep(2) # Give Mudae time to respond
            try:
                # Look for Mudae's response in recent history
                async for msg in channel.history(limit=5): # Check a few recent messages
                    if msg.author.id == TARGET_BOT_ID and "rolls left" in msg.content.lower(): # Identify Mudae's $tu response
                        content_lower = msg.content.lower()
                        # --- Claim Right Check ---
                        if "you __can__ claim" in content_lower:
                            client.claim_right_available = True
                            match_claim = re.search(r"next claim reset .*?\*\*(\d+h)?\s*(\d+)\*\* min", content_lower)
                            if match_claim:
                                hours_str = match_claim.group(1)
                                hours = int(hours_str[:-1]) if hours_str else 0
                                minutes = int(match_claim.group(2))
                                remaining_seconds = (hours * 60 + minutes) * 60
                                log_function(f"[{client.muda_name}] Claim right available. Reset in {hours}h {minutes}min.", client.preset_name, "INFO")

                                # Snipe Ignore Logic
                                if remaining_seconds <= 3600: # Less than or equal to 1 hour left
                                    if client.snipe_mode and client.snipe_ignore_min_kakera_reset:
                                        log_function(f"[{client.muda_name}] Claim reset <1h & snipe override active; ignoring min_kakera limit for rolls.", client.preset_name, "INFO")
                                        await check_rolls_left_tu(client, channel, mudae_prefix, log_function, client.preset_name, ignore_limit=True)
                                    else:
                                        log_function(f"[{client.muda_name}] Claim reset <1h; applying min_kakera limit for rolls.", client.preset_name, "INFO")
                                        await check_rolls_left_tu(client, channel, mudae_prefix, log_function, client.preset_name, ignore_limit=False)
                                else:
                                    log_function(f"[{client.muda_name}] Claim reset >1h; applying min_kakera limit for rolls.", client.preset_name, "INFO")
                                    await check_rolls_left_tu(client, channel, mudae_prefix, log_function, client.preset_name, ignore_limit=False)
                            else:
                                log_function(f"[{client.muda_name}] Claim right available, but couldn't parse exact reset time.", client.preset_name, "INFO")
                                await check_rolls_left_tu(client, channel, mudae_prefix, log_function, client.preset_name, ignore_limit=False)
                            return # Exit this check_status call successfully

                        elif "can't claim for another" in content_lower:
                            client.claim_right_available = False
                            match_claim_wait = re.search(r"another \*\*(\d+h)?\s*(\d+)\*\* min", content_lower)
                            if match_claim_wait:
                                hours_str = match_claim_wait.group(1)
                                hours = int(hours_str[:-1]) if hours_str else 0
                                minutes = int(match_claim_wait.group(2))
                                total_seconds = (hours * 60 + minutes) * 60

                                if client.key_mode: # Use client.key_mode here
                                    log_function(f"[{client.muda_name}] Claim unavailable ({hours}h {minutes}m left), but Key Mode active. Rolling for kakera only.", client.preset_name, "INFO")
                                    await check_rolls_left_tu(client, channel, mudae_prefix, log_function, client.preset_name, ignore_limit=True, key_mode_only_kakera=True)
                                else:
                                    log_function(f"[{client.muda_name}] Claim right not available. Reset in {hours}h {minutes}min. Waiting...", client.preset_name, "RESET")
                                    await wait_for_reset(total_seconds, client.delay_seconds, log_function, client.preset_name) # Use client.delay_seconds
                                    log_function(f"[{client.muda_name}] Wait complete. Re-checking status...", client.preset_name, "CHECK")
                                    await check_status(client, channel, mudae_prefix) # Call check_status again to restart the cycle
                            else:
                                log_function(f"[{client.muda_name}] Claim unavailable, but couldn't parse wait time. Retrying status check shortly.", client.preset_name, "ERROR")
                                await asyncio.sleep(60)
                                continue # Go to the next iteration of the while True loop to retry $tu

                            return # Exit this specific call frame of check_status

                        else:
                             log_function(f"[{client.muda_name}] Found Mudae $tu response but couldn't determine claim status. Content: {content_lower}", client.preset_name, "ERROR")
                             # Fall through to retry logic

                # If loop finishes without finding a suitable message
                raise ValueError("Mudae $tu message containing claim status not found in recent history.")

            except ValueError as e: # Catch specific error for not finding message
                error_count += 1
                log_function(f"[{client.muda_name}] Error checking status ({error_count}/{max_retries}): {e}", client.preset_name, "ERROR")
                if error_count >= max_retries:
                    log_function(f"[{client.muda_name}] Max retries reached for $tu status check. Retrying in 30 minutes.", client.preset_name, "ERROR")
                    await asyncio.sleep(1800)
                    error_count = 0 # Reset after long wait
                else:
                    log_function(f"[{client.muda_name}] Retrying status check in 5 seconds.", client.preset_name, "ERROR")
                    await asyncio.sleep(5)
                continue # Explicitly continue the loop

            except Exception as e: # Catch other potential errors
                error_count += 1
                log_function(f"[{client.muda_name}] Unexpected error during status check ({error_count}/{max_retries}): {e}", client.preset_name, "ERROR")
                if error_count >= max_retries:
                    log_function(f"[{client.muda_name}] Max retries reached due to unexpected error. Retrying in 30 minutes.", client.preset_name, "ERROR")
                    await asyncio.sleep(1800)
                    error_count = 0
                else:
                    log_function(f"[{client.muda_name}] Retrying status check in 10 seconds.", client.preset_name, "ERROR")
                    await asyncio.sleep(10)
                continue # Explicitly continue the loop
    # --- END OF MODIFIED FUNCTION ---


    # --- CORRECTED check_rolls_left_tu FUNCTION ---
    async def check_rolls_left_tu(client, channel, mudae_prefix, log_function, preset_name, ignore_limit=False, key_mode_only_kakera=False):
        """Parse rolls left from $tu output (by looking for 'you have') and proceed accordingly."""
        log_function(f"[{client.muda_name}] Checking rolls left using {mudae_prefix}tu output...", preset_name, "CHECK")
        error_count = 0
        max_retries = 5
        while True:
            tu_message = None
            try:
                # Try to find the most recent $tu response from Mudae in history
                async for msg in channel.history(limit=5): # Check recent messages
                    if msg.author.id == TARGET_BOT_ID and "you have" in msg.content.lower() and "rolls left" in msg.content.lower():
                        tu_message = msg
                        break # Found the relevant message

                if tu_message:
                    content_lower = tu_message.content.lower()
                    match_rolls = re.search(r"you have \*\*(\d+)\*\* rolls?(?: \(.+?\))? left", content_lower)

                    if match_rolls:
                        rolls_left = int(match_rolls.group(1))
                        reset_match = re.search(r"next rolls? reset in \*\*(\d+)\*\* min", content_lower)
                        reset_time = int(reset_match.group(1)) if reset_match else 0
                        if not reset_match:
                            log_function(f"[{client.muda_name}] Warning: Could not parse roll reset time from $tu output.", preset_name, "ERROR")

                        if rolls_left == 0:
                            log_function(f"[{client.muda_name}] No rolls left. Reset in {reset_time} min.", preset_name, "RESET")
                            await wait_for_rolls_reset(reset_time, client.delay_seconds, log_function, preset_name)
                            await check_status(client, channel, mudae_prefix)
                            return # Exit check_rolls_left_tu
                        else:
                            log_function(f"[{client.muda_name}] Rolls left: {rolls_left}", preset_name, "INFO")
                            await start_roll_commands(client, channel, rolls_left, ignore_limit, key_mode_only_kakera)
                            return # Exit check_rolls_left_tu successfully
                    else:
                        log_function(f"[{client.muda_name}] Error: Could not parse roll information from likely $tu output: {tu_message.content}", preset_name, "ERROR")

                else:
                    log_function(f"[{client.muda_name}] Error: Could not find recent Mudae response containing roll info.", preset_name, "ERROR")

            except Exception as e:
                 log_function(f"[{client.muda_name}] Unexpected error during roll check: {e}", preset_name, "ERROR")

            # Retry logic
            error_count += 1
            log_function(f"[{client.muda_name}] Roll check failed ({error_count}/{max_retries}). Retrying in 5 seconds.", preset_name, "ERROR")
            if error_count >= max_retries:
                log_function(f"[{client.muda_name}] Max retries reached for rolls check. Retrying status check in 30 minutes.", preset_name, "ERROR")
                await asyncio.sleep(1800)
                error_count = 0
                await channel.send(f"{mudae_prefix}tu")
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(5)
            continue # Continue the while loop to retry

    # --- END OF CORRECTED FUNCTION ---

    # <<< START OF CHANGE >>>
    async def start_roll_commands(client, channel, rolls_left, ignore_limit=False, key_mode_only_kakera=False):
        """Sends roll commands and handles the resulting messages."""
        log_function(f"[{client.muda_name}] Starting {rolls_left} rolls...", client.preset_name, "INFO")
        # --- FIX: Record time before sending rolls ---
        start_time = datetime.datetime.now(datetime.timezone.utc)
        rolled_messages_ids = set() # Keep track of message IDs we initiated rolls for

        for i in range(rolls_left):
            try:
                sent_msg = await channel.send(f"{client.mudae_prefix}{roll_command}")
                rolled_messages_ids.add(sent_msg.id) # Store the ID of the command message
                await asyncio.sleep(client.roll_speed)
            except discord.errors.HTTPException as e:
                log_function(f"[{client.muda_name}] Error sending roll command: {e}. Skipping roll.", client.preset_name, "ERROR")
                await asyncio.sleep(1) # Wait a bit before next attempt

        # Log the start time for debugging
        log_function(f"[{client.muda_name}] Finished sending rolls. Waiting briefly for Mudae... (Rolls started after: {start_time.isoformat()})", client.preset_name, "INFO")
        await asyncio.sleep(5) # Wait time after finishing rolls

        # Fetch recent messages to process
        mudae_messages_to_process = []
        fetch_limit = rolls_left * 2 + 10 # Keep a reasonable fetch limit
        processed_count = 0
        try:
            # --- FIX: Use 'after=start_time' to filter messages ---
            async for msg in channel.history(limit=fetch_limit, after=start_time, oldest_first=False):
                processed_count += 1
                # Ensure it's from Mudae and likely a character roll embed
                if msg.author.id == TARGET_BOT_ID and msg.embeds:
                     # Basic check if it's a character embed (has author name)
                     if msg.embeds[0].author and msg.embeds[0].author.name:
                         mudae_messages_to_process.append(msg)

            # --- OPTIONAL IMPROVEMENT: Process in roll order ---
            # Reverse the list so the first roll appears first in the list to process
            mudae_messages_to_process.reverse()

            # --- Updated Log Message ---
            log_function(f"[{client.muda_name}] Fetched {processed_count} messages since start time. Processing {len(mudae_messages_to_process)} potential character messages from this batch.", client.preset_name, "INFO")
            if mudae_messages_to_process:
                 await handle_mudae_messages(client, channel, mudae_messages_to_process, ignore_limit, key_mode_only_kakera)
            else:
                 log_function(f"[{client.muda_name}] No relevant character messages found to process after rolling.", client.preset_name, "INFO")

        except Exception as e:
            log_function(f"[{client.muda_name}] Error fetching/processing messages after rolling: {e}", client.preset_name, "ERROR")

        await asyncio.sleep(2) # Brief pause before re-checking status

        # Always re-check status after a batch of rolls or a snipe attempt
        if client.snipe_happened or client.series_snipe_happened:
            log_function(f"[{client.muda_name}] Snipe occurred, re-checking status.", client.preset_name, "INFO")
            client.snipe_happened = False
            client.series_snipe_happened = False
            await asyncio.sleep(1)
            await check_status(client, channel, client.mudae_prefix)
        else:
            log_function(f"[{client.muda_name}] Rolls complete, re-checking status.", client.preset_name, "INFO")
            await asyncio.sleep(1)
            await check_status(client, channel, client.mudae_prefix)
    # <<< END OF CHANGE >>>


    async def handle_mudae_messages(client, channel, mudae_messages, ignore_limit=False, key_mode_only_kakera=False):
        """Processes a list of Mudae messages for claiming kakera and characters."""
        kakera_claims = []
        character_claims = [] # Includes wishlist and high-value characters
        wishlist_claims = []
        rt_claims = []

        min_kak_value = client.min_kakera if not ignore_limit else 0
        log_function(f"[{client.muda_name}] Handling messages. Min Kakera: {min_kak_value} (Ignore limit: {ignore_limit}) KeyMode+NoClaim: {key_mode_only_kakera}", client.preset_name, "CHECK")

        # --- First Pass: Identify all potential claims ---
        for msg in mudae_messages:
            if not msg.embeds: continue
            embed = msg.embeds[0]
            if not embed.author or not embed.author.name: continue # Skip embeds without character name

            char_name = embed.author.name.lower() # Lowercase for comparison
            description = embed.description or ""
            kakera_value = 0
            is_wishlist = any(wish == char_name for wish in client.wishlist) # Exact match first
            if not is_wishlist: # Fallback to substring check
                is_wishlist = any(wish in char_name for wish in client.wishlist if len(wish) > 2) # Avoid short common substrings

            # Check for Kakera reaction
            if msg.components:
                for component in msg.components:
                    for button in component.children:
                        if hasattr(button.emoji, 'name') and button.emoji.name in KAKERA_EMOJIS:
                             kakera_claims.append(msg)
                             break # Found kakera button for this message

            # Extract Kakera value if present
            match = re.search(r"\*\*([\d,]+)\*\*<:kakera:", description)
            if match:
                try:
                    kakera_value = int(match.group(1).replace(",", ""))
                except ValueError:
                    log_function(f"[{client.muda_name}] Failed to parse kakera value from: {match.group(1)}", client.preset_name, "ERROR")

            # --- Determine Claim Eligibility ---
            can_claim_this = client.claim_right_available or key_mode_only_kakera # Can we claim *anything* (RT or normal)

            # Claim Logic: Prioritize wishlist, then high kakera
            if can_claim_this:
                has_claim_button = False
                if msg.components:
                     for component in msg.components:
                         for button in component.children:
                             if hasattr(button.emoji, 'name') and button.emoji.name in CLAIM_EMOJIS:
                                 has_claim_button = True
                                 break
                if not has_claim_button and not is_wishlist:
                    continue


                if is_wishlist:
                    if client.claim_right_available or key_mode_only_kakera:
                        wishlist_claims.append((msg, char_name, kakera_value))
                        log_function(f"[{client.muda_name}] Wishlist character found: {embed.author.name} (Value: {kakera_value})", client.preset_name, "INFO")

                elif has_claim_button and kakera_value >= min_kak_value:
                    character_claims.append((msg, char_name, kakera_value))


        # --- Second Pass: Execute Claims based on priority ---

        # 1. Claim Kakera (Always try)
        for msg in kakera_claims:
            await claim_character(client, channel, msg, is_kakera=True)
            await asyncio.sleep(0.3) # Small delay between kakera clicks

        # 2. Claiming Characters
        claimed_normally = False
        claimed_rt = False

        # Prioritize Wishlist for Normal Claim
        if client.claim_right_available and wishlist_claims:
            msg_to_claim, name, value = wishlist_claims[0]
            log_function(f"[{client.muda_name}] Prioritizing wishlist claim: {name}", client.preset_name, "CLAIM")
            await claim_character(client, channel, msg_to_claim, is_kakera=False)
            claimed_normally = True
            client.claim_right_available = False
            character_claims = [(m, n, v) for m, n, v in character_claims if m.id != msg_to_claim.id]
            wishlist_claims.pop(0)

        # Normal Claim for Highest Value (if no wishlist claimed yet)
        if client.claim_right_available and not claimed_normally and character_claims:
            character_claims.sort(key=lambda item: item[2], reverse=True) # Sort by kakera value descending
            msg_to_claim, name, value = character_claims[0]
            log_function(f"[{client.muda_name}] Claiming highest value character: {name} (Value: {value})", client.preset_name, "CLAIM")
            await claim_character(client, channel, msg_to_claim, is_kakera=False)
            claimed_normally = True
            client.claim_right_available = False
            character_claims.pop(0)
            wishlist_claims = [(m, n, v) for m, n, v in wishlist_claims if m.id != msg_to_claim.id]


        # RT Claim Logic
        can_rt = claimed_normally or key_mode_only_kakera

        if can_rt:
            potential_rt_targets = wishlist_claims + character_claims
            potential_rt_targets.sort(key=lambda item: item[2], reverse=True)

            if potential_rt_targets:
                msg_to_rt_claim, name, value = potential_rt_targets[0]
                if value >= client.min_kakera:
                    log_function(f"[{client.muda_name}] Attempting RT claim for: {name} (Value: {value})", client.preset_name, "CLAIM")
                    try:
                        await channel.send(f"{client.mudae_prefix}rt")
                        await asyncio.sleep(0.7)
                        await claim_character(client, channel, msg_to_rt_claim, is_rt_claim=True)
                        claimed_rt = True
                    except Exception as e:
                         log_function(f"[{client.muda_name}] Error during RT command/claim: {e}", client.preset_name, "ERROR")
                else:
                    log_function(f"[{client.muda_name}] Skipping RT for {name} (Value: {value}) as it's below min_kakera ({client.min_kakera}) for RT.", client.preset_name, "INFO")


    async def claim_character(client, channel, msg, is_kakera=False, is_rt_claim=False):
        """Clicks the appropriate button or adds a reaction to claim."""
        if not msg or not msg.embeds: # Basic check
            log_function(f"[{client.muda_name}] Invalid message passed to claim_character.", client.preset_name, "ERROR")
            return

        embed = msg.embeds[0]
        character_name = embed.author.name if embed.author else "Unknown Character"
        log_prefix = f"[{client.muda_name}]"
        log_suffix = f": {character_name}"
        log_type = "CLAIM"
        button_emojis = CLAIM_EMOJIS

        if is_kakera:
            log_message = "Attempting Kakera claim"
            log_type = "KAKERA"
            button_emojis = KAKERA_EMOJIS
        elif is_rt_claim:
            log_message = "Attempting RT claim"
        else:
            log_message = "Attempting character claim"

        button_clicked = False
        if msg.components:
            for component in msg.components:
                for button in component.children:
                    if hasattr(button.emoji, 'name') and button.emoji and button.emoji.name in button_emojis:
                        try:
                            log_function(f"{log_prefix} {log_message}{log_suffix} (via button)", client.preset_name, log_type)
                            await button.click()
                            button_clicked = True
                            await asyncio.sleep(1.5)
                            return
                        except discord.errors.NotFound:
                            log_function(f"{log_prefix} Button interaction failed (NotFound - likely already claimed/expired){log_suffix}", client.preset_name, "ERROR")
                            return
                        except discord.errors.HTTPException as e:
                            log_function(f"{log_prefix} Button click failed (HTTPException {e.status}){log_suffix}", client.preset_name, "ERROR")
                            return
                        except Exception as e:
                             log_function(f"{log_prefix} Unexpected error clicking button{log_suffix}: {e}", client.preset_name, "ERROR")
                             return

        if not button_clicked and not is_kakera:
            log_function(f"{log_prefix} No claim button found/clicked for {character_name}. Attempting reaction fallback.", client.preset_name, "INFO")
            try:
                await msg.add_reaction("💖")
                log_function(f"{log_prefix} {log_message}{log_suffix} (via reaction 💖)", client.preset_name, log_type)
                await asyncio.sleep(1.5)
            except discord.errors.Forbidden:
                 log_function(f"{log_prefix} Reaction claim failed (Forbidden - check permissions){log_suffix}", client.preset_name, "ERROR")
            except discord.errors.NotFound:
                 log_function(f"{log_prefix} Reaction claim failed (NotFound - message deleted?){log_suffix}", client.preset_name, "ERROR")
            except discord.errors.HTTPException as e:
                 log_function(f"{log_prefix} Reaction claim failed (HTTPException {e.status}){log_suffix}", client.preset_name, "ERROR")
            except Exception as e:
                 log_function(f"{log_prefix} Unexpected error adding reaction{log_suffix}: {e}", client.preset_name, "ERROR")


    async def check_new_characters(client, channel):
        """Placeholder function, original logic seemed redundant."""
        pass


    async def wait_for_reset(seconds_to_wait, base_delay_seconds, log_function, preset_name):
        """Waits until the next claim reset, adding the base delay."""
        if seconds_to_wait <= 0:
            seconds_to_wait = 1

        total_wait = seconds_to_wait + base_delay_seconds
        wait_end_time = datetime.datetime.now() + datetime.timedelta(seconds=total_wait)

        log_function(f"[{client.muda_name}] Waiting for claim reset. Wait time: {seconds_to_wait}s + {base_delay_seconds}s delay = {total_wait:.2f}s. Resuming at ~{wait_end_time.strftime('%H:%M:%S')}", preset_name, "RESET")
        await asyncio.sleep(total_wait)
        log_function(f"[{client.muda_name}] Wait finished. Resuming operations.", preset_name, "RESET")


    async def wait_for_rolls_reset(reset_time_minutes, base_delay_seconds, log_function, preset_name):
        """Waits until the next roll reset, adding the base delay."""
        now = datetime.datetime.now()
        seconds_until_reset = (reset_time_minutes * 60) - (now.second)
        if seconds_until_reset < 0:
             seconds_until_reset += (reset_time_minutes * 60)

        if seconds_until_reset <= 0:
             seconds_until_reset = (reset_time_minutes * 60) if reset_time_minutes > 0 else 60

        total_wait = seconds_until_reset + base_delay_seconds
        wait_end_time = datetime.datetime.now() + datetime.timedelta(seconds=total_wait)

        log_function(f"[{client.muda_name}] Waiting for rolls reset ({reset_time_minutes} min cycle). Wait time: {seconds_until_reset}s + {base_delay_seconds}s delay = {total_wait:.2f}s. Resuming at ~{wait_end_time.strftime('%H:%M:%S')}", preset_name, "RESET")
        await asyncio.sleep(total_wait)
        log_function(f"[{client.muda_name}] Roll wait finished. Resuming operations.", preset_name, "RESET")


    @client.event
    async def on_message(message):
        if message.author.id != TARGET_BOT_ID or message.channel.id != client.target_channel_id:
            await client.process_commands(message)
            return

        if not message.embeds:
            return

        embed = message.embeds[0]
        process_further = True

        # 1. Series Sniping Check
        if client.series_snipe_mode and client.series_wishlist:
            description = embed.description or ""
            if description:
                first_line = description.splitlines()[0].lower()
                if any(kw in first_line for kw in client.series_wishlist):
                    if any(hasattr(b.emoji, 'name') and b.emoji.name in CLAIM_EMOJIS for comp in message.components for b in comp.children):
                        if message.id not in client.series_sniped_messages:
                            client.series_sniped_messages.add(message.id)
                            series_name = embed.author.name if embed.author else description.splitlines()[0]
                            log_function(f"[{client.muda_name}] (SNIPE) Series match: {series_name}. Waiting {client.series_snipe_delay}s", client.preset_name, "CLAIM")
                            await asyncio.sleep(client.series_snipe_delay)
                            await claim_character(client, message.channel, message)
                            client.series_snipe_happened = True
                            process_further = False


        # 2. Normal Character Sniping Check (only if series snipe didn't happen)
        if process_further and client.snipe_mode and client.wishlist:
            if embed.author and embed.author.name:
                character_name_lower = embed.author.name.lower()
                is_snipe_target = any(wish == character_name_lower for wish in client.wishlist)
                if not is_snipe_target:
                     is_snipe_target = any(wish in character_name_lower for wish in client.wishlist if len(wish) > 2)

                if is_snipe_target:
                    if any(hasattr(b.emoji, 'name') and b.emoji.name in CLAIM_EMOJIS for comp in message.components for b in comp.children):
                        if message.id not in client.sniped_messages:
                            client.sniped_messages.add(message.id)
                            log_function(f"[{client.muda_name}] (SNIPE) Wishlist match: {embed.author.name}. Waiting {client.snipe_delay}s", client.preset_name, "CLAIM")
                            await asyncio.sleep(client.snipe_delay)
                            await claim_character(client, message.channel, message)
                            client.snipe_happened = True
                            process_further = False

        if process_further:
            await client.process_commands(message)


    # --- Bot Execution ---
    try:
        client.run(token)
    except discord.errors.LoginFailure:
        log_function(f"[{BOT_NAME}] Bot failed to log in for preset '{preset_name}'. Check the token.", preset_name, "ERROR")

    except Exception as e:
        log_function(f"[{BOT_NAME}] An unexpected error occurred running the bot for preset '{preset_name}': {e}", preset_name, "ERROR")


def show_banner():
    """Displays the MudaRemote banner."""
    banner = r"""
  __  __ _    _ _____          _____  ______ __  __  ____ _______ ______
 |  \/  | |  | |  __ \   /\   |  __ \|  ____|  \/  |/ __ \__   __|  ____|
 | \  / | |  | | |  | | /  \  | |__) | |__  | \  / | |  | | | |  | |__
 | |\/| | |  | | |  | |/ /\ \ |  _  /|  __| | |\/| | |  | | | |  |  __|
 | |  | | |__| | |__| / ____ \| | \ \| |____| |  | | |__| | | |  | |____
 |_|  |_|\____/|_____/_/    \_\_|  \_\______|_|  |_|\____/  |_|  |______|

"""
    print("\033[1;36m" + banner + "\033[0m") # Cyan Bold
    print("\033[1;33mWelcome to MudaRemote - Your Remote Mudae Assistant\033[0m\n") # Yellow Bold

def validate_preset(preset_name, preset_data):
    """Validates required fields in a preset."""
    required_keys = ["token", "prefix", "channel_id", "roll_command", "min_kakera", "delay_seconds", "mudae_prefix"]
    missing_keys = [key for key in required_keys if key not in preset_data]
    if missing_keys:
        print(f"\033[91mError in preset '{preset_name}': Missing required keys: {', '.join(missing_keys)}\033[0m")
        return False
    # Basic type checks
    if not isinstance(preset_data["token"], str) or not preset_data["token"]:
        print(f"\033[91mError in preset '{preset_name}': 'token' must be a non-empty string.\033[0m")
        return False
    if not isinstance(preset_data["channel_id"], int):
        print(f"\033[91mError in preset '{preset_name}': 'channel_id' must be an integer.\033[0m")
        return False
    if not isinstance(preset_data["min_kakera"], int) or preset_data["min_kakera"] < 0:
        print(f"\033[91mError in preset '{preset_name}': 'min_kakera' must be a non-negative integer.\033[0m")
        return False
    if not isinstance(preset_data["delay_seconds"], (int, float)) or preset_data["delay_seconds"] < 0:
         print(f"\033[91mError in preset '{preset_name}': 'delay_seconds' must be a non-negative number.\033[0m")
         return False
    # Optional fields validation (type checks if they exist)
    if "key_mode" in preset_data and not isinstance(preset_data["key_mode"], bool):
         print(f"\033[91mWarning in preset '{preset_name}': 'key_mode' should be true or false.\033[0m")
    if "start_delay" in preset_data and (not isinstance(preset_data["start_delay"], (int, float)) or preset_data["start_delay"] < 0):
        print(f"\033[91mWarning in preset '{preset_name}': 'start_delay' should be a non-negative number.\033[0m")
    if "snipe_mode" in preset_data and not isinstance(preset_data["snipe_mode"], bool):
         print(f"\033[91mWarning in preset '{preset_name}': 'snipe_mode' should be true or false.\033[0m")
    if "wishlist" in preset_data and not isinstance(preset_data["wishlist"], list):
         print(f"\033[91mWarning in preset '{preset_name}': 'wishlist' should be a list (e.g., [\"Char1\", \"Char2\"]).\033[0m")

    return True


def start_preset_thread(preset_name, preset_data):
     """Validates and starts a bot thread for a given preset."""
     if not validate_preset(preset_name, preset_data):
         print(f"\033[91mSkipping preset '{preset_name}' due to configuration errors.\033[0m")
         return None # Return None if validation fails

     print(f"\033[92mStarting bot for preset: {preset_name}\033[0m")
     # Get values with defaults for optional settings
     key_mode = preset_data.get("key_mode", False)
     start_delay = preset_data.get("start_delay", 0)
     snipe_mode = preset_data.get("snipe_mode", False)
     snipe_delay = preset_data.get("snipe_delay", 5)
     snipe_ignore_min_kakera_reset = preset_data.get("snipe_ignore_min_kakera_reset", False)
     wishlist = preset_data.get("wishlist", [])
     series_snipe_mode = preset_data.get("series_snipe_mode", False)
     series_snipe_delay = preset_data.get("series_snipe_delay", 5)
     series_wishlist = preset_data.get("series_wishlist", [])
     roll_speed = preset_data.get("roll_speed", 0.3) # Default roll speed

     thread = threading.Thread(target=run_bot, args=(
         preset_data["token"],
         preset_data["prefix"],
         preset_data["channel_id"],
         preset_data["roll_command"],
         preset_data["min_kakera"],
         preset_data["delay_seconds"],
         preset_data["mudae_prefix"],
         print_log, # Pass the unified logging function
         preset_name, # Pass the preset name for logging
         key_mode,
         start_delay,
         snipe_mode,
         snipe_delay,
         snipe_ignore_min_kakera_reset,
         wishlist,
         series_snipe_mode,
         series_snipe_delay,
         series_wishlist,
         roll_speed
     ), daemon=True) # Set daemon=True so threads exit when main program exits
     thread.start()
     return thread # Return the thread object


def main_menu():
    """Displays the main menu and handles user selection."""
    show_banner()
    active_threads = []

    while True:
        # Clear finished threads (optional cleanup)
        active_threads = [t for t in active_threads if t.is_alive()]

        questions = [
            inquirer.List('option',
                          message=f"Select an option ({len(active_threads)} bots running):",
                          choices=[
                              'Select and Run Preset',
                              'Select and Run Multiple Presets',
                              'Exit'
                          ],
                          ),
        ]
        try:
            answers = inquirer.prompt(questions)
            if not answers: # Handle Ctrl+C or empty selection
                 print("\nExiting...")
                 break

            option = answers['option']

            if option == 'Select and Run Preset':
                preset_list = list(presets.keys())
                if not preset_list:
                    print("\033[91mNo presets found in presets.json.\033[0m")
                    continue
                preset_questions = [
                    inquirer.List('preset',
                                  message="Select a preset to run:",
                                  choices=preset_list,
                                  ),
                ]
                preset_answers = inquirer.prompt(preset_questions)
                if preset_answers:
                    selected_preset = preset_answers['preset']
                    thread = start_preset_thread(selected_preset, presets[selected_preset])
                    if thread:
                        active_threads.append(thread)

            elif option == 'Select and Run Multiple Presets':
                preset_list = list(presets.keys())
                if not preset_list:
                    print("\033[91mNo presets found in presets.json.\033[0m")
                    continue
                multi_preset_questions = [
                    inquirer.Checkbox('presets',
                                      message="Select presets to run (Spacebar to select, Enter to confirm):",
                                      choices=preset_list,
                                      ),
                ]
                multi_preset_answers = inquirer.prompt(multi_preset_questions)
                if multi_preset_answers:
                    selected_presets = multi_preset_answers['presets']
                    for preset_name in selected_presets:
                        thread = start_preset_thread(preset_name, presets[preset_name])
                        if thread:
                             active_threads.append(thread)

            elif option == 'Exit':
                print("\033[1;32mExiting MudaRemote. Stopping running bots...\033[0m")
                # Note: Daemon threads will exit automatically.
                # If explicit cleanup is needed, you'd signal threads to stop.
                break

        except KeyboardInterrupt:
             print("\nCtrl+C detected. Exiting MudaRemote...")
             break
        except Exception as e:
            print(f"\033[91mAn error occurred in the main menu: {e}\033[0m")
            # time.sleep(2)

if __name__ == "__main__":
    # Ensure logs.txt exists at startup and set encoding
    try:
        with open("logs.txt", "a", encoding='utf-8') as f: # Specify encoding
            f.write(f"\n--- MudaRemote Log Start: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    except Exception as e:
         print(f"\033[91mCould not initialize log file: {e}\033[0m")

    # Ensure stdout uses UTF-8 for potential non-ASCII preset names or logs
    # sys.stdout.reconfigure(encoding='utf-8') # Uncomment if needed, can cause issues in some terminals

    main_menu()
