import asyncio
import json
import logging
import re

import requests
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters, CallbackContext, CallbackQueryHandler, )
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
GQL_URL = URL + "/graphql"

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


async def create_report(standard, address, network):
    logger.info(f"Creating report for {standard} {address} {network}")
    query = '''
    mutation CreateReportMutation($standard: TestSuiteStandard!, $address: String!, $network: Int!) {
        createReport(input: {
            address: $address,
            forceCreate: false,
            network: $network,
            standard: $standard
        }) {
            id
            tokenId
            tokenClass
            standard
            userId
            createdAt
            updatedAt
            version
            jsonReport
            progress
            token {
              id
              address
              name
              symbol
              network
              isSourceContract
              isBookmarked
              createdAt
              updatedAt
            }
            executeTestsTask {
              id
              reportId
              status
              terminalOutputs
              createdAt
              updatedAt
            }
        }}
    '''

    variables = {
        'standard': standard,
        'address': address,
        'network': network,
    }

    headers = {
        'Authentication': f'Bearer {ERCX_API_KEY}'
    }
    response = requests.post(
        GQL_URL,
        json={'query': query, 'variables': variables},
        headers=headers
    )
    logger.info(response)
    logger.info(response.content)
    if response.status_code == 200:
        result = json.loads(response.content.decode('utf-8'))
        return result
    else:
        return None


async def generate_report(update: Update, context: CallbackContext):
    standard = context.user_data["selections"][update.effective_user.id]['standard']
    address = context.user_data["selections"][update.effective_user.id]['address']
    network = context.user_data["selections"][update.effective_user.id]['network']
    await create_report(STANDARDS_DICT[standard], address, NETWORKS_DICT[network])


async def check_report_is_ready(update: Update, context: CallbackContext):
    standard = context.user_data["selections"][update.effective_user.id]['standard']
    address = context.user_data["selections"][update.effective_user.id]['address']
    network = context.user_data["selections"][update.effective_user.id]['network']
    counter = 0
    if update.message:
        message = await update.message.reply_text("Report generating...")
        chat_id = update.message.chat_id
    elif update.callback_query:
        message = await update.callback_query.message.reply_text("Report generating...")
        chat_id = update.callback_query.message.chat_id
    else:
        print(f"Unexpected update: {update}")
        return

    while counter < 300:
        data = get_report(address, STANDARDS_DICT[standard], NETWORKS_DICT[network])
        if data:
            await test_token_address(update, context)
            return
        else:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message.message_id,
                text=f"Report generating...\n{counter}sec"
            )
            counter += 10
            await asyncio.sleep(10)


async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == "Yes":
        await query.edit_message_text(
            text=f"You selected generate report for this  address:\n\n"
                 f"{context.user_data['selections'][update.effective_user.id]['address']}"
                 "\n\nPlease wait while we are generating the report."
        )
        await generate_report(update, context)

        await check_report_is_ready(update, context)

    elif query.data == "No":
        await start(update, context)
        # Your logic for "No" goes here


async def handle_text(update: Update, context: CallbackContext) -> None:
    message_text = update.message.text
    user_id = update.effective_user.id

    logger.info(context.user_data)
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


def get_report(address, standard, network):
    headers = {
        'Authentication': f'Bearer {ERCX_API_KEY}'
    }
    params = {
        'standard': standard,
    }
    response = requests.get(f"{URL}/api/v1/tokens/{network}/{address}/levels/all", headers=headers,
                            params=params)
    if response.status_code == 404:
        return None

    data = response.json()

    return data


async def test_token_address(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    network = context.user_data["selections"][user_id]['network']
    standard = context.user_data["selections"][user_id]['standard']
    if 'address' in context.user_data["selections"][user_id]:
        address = context.user_data["selections"][user_id]['address']
    else:
        address=  update.message.text

    keyboard = [
        [KeyboardButton(MAIN_MENU)]
    ]

    nested_keyboard = [
        [InlineKeyboardButton("Yes", callback_data="Yes"),
         InlineKeyboardButton("No", callback_data="No")]
    ]

    data = get_report(address, STANDARDS_DICT[standard], NETWORKS_DICT[network])

    if not data:
        context.user_data["selections"][user_id]['address'] = address
        await update.effective_message.reply_text(
            f"Token address {address} {standard} standard for {network} network is not found in our database.\n\n"
            f"Would you like to generate a report for this token address?",
            reply_markup=InlineKeyboardMarkup(nested_keyboard))
        return

    message = f'Your {standard} token address is {address} deployed on {network} network.\n\n'
    message += count_properties(data)
    message += f"\nFull report: {URL}/token/{address}?network={NETWORKS_DICT[network]}"
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
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
