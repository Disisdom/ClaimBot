import logging
import random
from datetime import datetime
import sqlite3

from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged so it don't spam
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Database connection
def connect_db() -> sqlite3.Connection:
    return sqlite3.connect("Input database file here")

# States for convhandler
(
    VERIFY_USER,
    INPUT_DETAILS,
    ADD_ITEMS,
    CONFIRM_ITEM,
    UPLOAD_RECEIPT,
) = range(5)

# Check if user exists in the whitelist
def user_not_recognised(user_id) -> bool:
    database = connect_db()
    results = database.cursor().execute("SELECT name FROM persons WHERE id = ?", (user_id,))
    return results.fetchone() is None

# Register new claim
def register_new_claim(claim_id, user_id, name, phone_num, date):
    database = connect_db()
    # Convert `date` to ISO 8601 string format for compatibility
    date_str = date.isoformat()

    database.cursor().execute(
        "INSERT INTO claims (claim_id, user_id, name, phone_num, date, status) VALUES (?, ?, ?, ?, ?, 'receiving')",
        (claim_id, user_id, name, phone_num, date_str),
    )
    database.commit()
    return True

# Add items to claim
def add_items_to_claim(claim_id, item_desc, price_per_item, qty, value_item):
    database = connect_db()

    database.cursor().execute(
        "INSERT INTO claim_items (claim_id, item_desc, price_per_item, qty, value_item) VALUES (?, ?, ?, ?, ?)",
        (claim_id, item_desc, price_per_item, qty, value_item),
    )
    database.commit()
    return True

# Define Handlers
async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # helper function to inform user of their Telegram ID for the purpose of registration
    user = update.effective_user
    chat = update.effective_chat
    await update.message.reply_html(
        f"Hi {user.username}, your telegram user ID is {user.id} and your chat ID is {chat.id}!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_not_recognised(user_id):
        await update.message.reply_text("You are not authorized to use this bot.")
        return ConversationHandler.END

    reply_keyboard = [["New Claim", "View Claims"]]
    await update.message.reply_text(
        "Welcome! What would you like to do?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
    )
    return VERIFY_USER

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "New Claim":
        await update.message.reply_text(
            "Please enter your details in the format: (Name),(Phone Number)",
            reply_markup=ReplyKeyboardMarkup([["Go Back"]], one_time_keyboard=True),
        )
        return INPUT_DETAILS
    elif choice == "View Claims":
        await update.message.reply_text("Feature coming soon!")
        return ConversationHandler.END

async def input_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Go Back":
        return await start(update, context)

    try:
        name, phone_number = text.split(",")
        claim_id = f"{phone_number}{random.randint(1, 999)}"
        date = datetime.now()

        context.user_data["claim"] = {"id": claim_id, "name": name, "phone_number": phone_number}
        # Create a temp dictionary to keep temp vars before writing in database
        register_new_claim(claim_id, update.effective_user.id, name, phone_number, date)

        await update.message.reply_text(
            "Claim started! Enter your first item in the format:\n(Item description),(Price Per Qty),(Qty of items)"
        )
        return ADD_ITEMS
    except ValueError:
        await update.message.reply_text("Invalid format. Please try again or click 'Go Back'.")
        return INPUT_DETAILS

async def add_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Go Back":
        await update.message.reply_text(
            "Please re-enter the previous item:\n(Item description),(Price Per Qty),(Qty of items)"
        )
        return ADD_ITEMS

    try:
        item_desc, price_per_item, qty = text.split(",")
        price_per_item, qty = float(price_per_item), int(qty)
        value_item = price_per_item * qty

        # Save the item to the context user_data as a temp dictionary
        if "items" not in context.user_data:
            context.user_data["items"] = []
        context.user_data["items"].append((item_desc, price_per_item, qty, value_item))

        await update.message.reply_text(
            f"Item added: {item_desc}, {qty} x {price_per_item:.2f} = {value_item:.2f}\n"
            "Do you want to add another item?",
            reply_markup=ReplyKeyboardMarkup([["Yes", "No", "Go Back"]], one_time_keyboard=True),
        )
        return CONFIRM_ITEM
    except ValueError:
        await update.message.reply_text("Invalid format. Please try again.")
        return ADD_ITEMS

async def confirm_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text

    if choice == "Yes":
        await update.message.reply_text("Enter the next item:")
        return ADD_ITEMS

    elif choice == "No":
        # Write collected items to the database
        claim_id = context.user_data.get("claim", {}).get("id")
        if claim_id and "items" in context.user_data:
            for item in context.user_data["items"]:
                item_desc, price_per_item, qty, value_item = item
                add_items_to_claim(claim_id, item_desc, price_per_item, qty, value_item)

            await update.message.reply_text(
                "All items have been added to your claim. Please upload a receipt image."
            )
            return UPLOAD_RECEIPT
        else:
            await update.message.reply_text("No items to add. Please start again.")
            return ConversationHandler.END

    elif choice == "Go Back":
        # Pops last item out of the stack if they want to re-input
        if "items" in context.user_data and context.user_data["items"]:
            removed_item = context.user_data["items"].pop()
            await update.message.reply_text(
                f"Removed the last item: {removed_item[0]}, {removed_item[2]} x {removed_item[1]:.2f} = {removed_item[3]:.2f}\n"
                "Please re-enter the previous item:\n(Item description),(Price Per Qty),(Qty of items)"
            )
        else:
            await update.message.reply_text(
                "No items to remove. Please add an item first:\n(Item description),(Price Per Qty),(Qty of items)"
            )
        return ADD_ITEMS


async def upload_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        # Get the largest image sent (highest resolution)
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        # Retrieve claim ID and other data
        claim_id = context.user_data.get("claim", {}).get("id")
        if claim_id:
            # Store the image in the database
            database = connect_db()
            database.cursor().execute(
                "INSERT INTO receipts (claim_id, image_data) VALUES (?, ?)",
                (claim_id, photo_bytes),
            )
            database.commit()

            # Save the image to a temporary file to send back
            with open("temp_image.jpg", "wb") as temp_file:
                temp_file.write(photo_bytes)

            # Reply with the receipt and claim number so they can trace
            await update.message.reply_photo(
                photo=open("temp_image.jpg", "rb"),
                caption=f"Receipt uploaded for Claim ID: {claim_id}. Claim submission complete!",
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text("No claim ID found. Please start again.")
            return ConversationHandler.END

    else:
        await update.message.reply_text("Please upload a valid image.")
        return UPLOAD_RECEIPT

# Main function
def main():
    application = Application.builder().token("Input bot token here").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            VERIFY_USER: [MessageHandler(filters.TEXT, handle_choice)],
            INPUT_DETAILS: [MessageHandler(filters.TEXT, input_details)],
            ADD_ITEMS: [MessageHandler(filters.TEXT, add_items)],
            CONFIRM_ITEM: [MessageHandler(filters.TEXT, confirm_item)],
            UPLOAD_RECEIPT: [MessageHandler(filters.PHOTO, upload_receipt)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    application.add_handler(CommandHandler("me", my_id))
    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
