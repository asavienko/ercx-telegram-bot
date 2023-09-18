import logging
import re

import requests
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters, CallbackContext, )
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Read environment variables
TG_TOKEN = os.environ.get('TG_TOKEN')
ERCX_API_KEY = os.environ.get('ERCX_API_KEY')

# Enable logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

ERC20 = "ERC-20"
ERC4626 = "ERC-4626"
MAINNET = "Mainnet"
SEPOLIA = "Sepolia"
GOERLI = "Goerli"
MAIN_MENU = "Main Menu"

STANDARDS = [ERC20, ERC4626]
NETWORKS = [MAINNET, SEPOLIA, GOERLI]

URL = "https://ercx.runtimeverification.com"

NETWORKS_DICT = {
    MAINNET: 1,
    SEPOLIA: 11155111,
    GOERLI: 5
}

STANDARDS_DICT = {
    ERC20: "ERC20",
    ERC4626: "ERC4626"
}


def is_valid_ethereum_address(address):
    pattern = "^0x[a-fA-F0-9]{40}$"
    return bool(re.match(pattern, address))


def count_properties(data):
    # Initialize a dictionary to keep track of property counts
    count_dict = {}

    # Iterate through the data to update the counts
    for entry in data:
        level = entry['test']['level']
        result = entry['result']
        if level not in count_dict:
            count_dict[level] = {'total': 0, 'success': 0}

        if result >= 0:
            count_dict[level]['total'] += 1
            count_dict[level]['success'] += result
    message = ""
    # Add summary
    for level, counts in count_dict.items():
        message += f"{level.capitalize()} {counts['success']}/{counts['total']}\n"

    return message


async def handle_text(update: Update, context: CallbackContext) -> None:
    message_text = update.message.text
    user_id = update.effective_user.id

    # Initialize the user's selection list if it doesn't exist
    if "selections" not in context.user_data:
        context.user_data["selections"] = {}

    if user_id not in context.user_data["selections"]:
        context.user_data["selections"][user_id] = {"network": None, "standard": None}

    if message_text in NETWORKS:
        # Append the current selection to the user's selection dictionary
        context.user_data["selections"][user_id]['network'] = message_text
    elif message_text in STANDARDS:
        # Append the current selection to the user's selection dictionary
        context.user_data["selections"][user_id]['standard'] = message_text

    if message_text == ERC20:
        await select_standard_menu(update, context)
    elif message_text == ERC4626:
        await select_standard_menu(update, context)

    elif message_text == MAINNET:
        await select_network_menu(update, context)
    elif message_text == SEPOLIA:
        await select_network_menu(update, context)
    elif message_text == GOERLI:
        await select_network_menu(update, context)

    elif message_text == MAIN_MENU:
        await start(update, context)
    elif context.user_data["selections"][user_id]['network'] and context.user_data["selections"][user_id][
        'standard'] and is_valid_ethereum_address(message_text):
        await test_token_address(update, context)


async def test_token_address(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    network = context.user_data["selections"][user_id]['network']
    standard = context.user_data["selections"][user_id]['standard']
    address = update.message.text
    keyboard = [
        [KeyboardButton(MAIN_MENU)]
    ]
    headers = {
        'Authentication': f'Bearer {ERCX_API_KEY}'
    }
    params = {
        'standard': STANDARDS_DICT[standard],
    }

    response = requests.get(f"{URL}/api/v1/tokens/{NETWORKS_DICT[network]}/{address}/levels/all", headers=headers,
                            params=params)

    data = response.json()

    message = f'Your {standard} token address is {address} deployed on {network} network.\n\n'
    message += count_properties(data)
    message += f"\nFull report: {URL}/token/{address}"
    await update.effective_message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup(keyboard))
    await update.effective_message.reply_text(
        f"Please enter another token address to test {standard} standard on {network} network.\n\n"
        f"Or press {MAIN_MENU} to go back to main menu.",
        reply_markup=ReplyKeyboardMarkup(keyboard)
    )


async def select_network_menu(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    network = context.user_data["selections"][user_id]['network']
    standard = context.user_data["selections"][user_id]['standard']
    keyboard = [
        [KeyboardButton(MAIN_MENU)]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(f'Please send token address {standard} standard for {network} network:',
                                              reply_markup=reply_markup)


async def select_standard_menu(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [KeyboardButton(MAINNET),
         KeyboardButton(SEPOLIA),
         KeyboardButton(GOERLI),
         KeyboardButton(MAIN_MENU)
         ]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard)
    await update.effective_message.reply_text('Please choose a network:', reply_markup=reply_markup)

    # Define a `/start` command handler.


async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id

    # Initialize the user's selection list if it doesn't exist
    if "selections" not in context.user_data:
        context.user_data["selections"] = {}

    # Clear the user's selections if it exists
    context.user_data["selections"][user_id] = {"network": None, "standard": None}
    keyboard = [
        [KeyboardButton(ERC20),
         KeyboardButton(ERC4626)]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard)
    await update.effective_message.reply_text('Please choose token standard to test:', reply_markup=reply_markup)


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TG_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
