import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime
import os
import gspread
from google.oauth2.service_account import Credentials

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("SERVER_ID"))
SERVICE_ACCOUNT_FILE = "keys.json"
SPREADSHEET_KEY = "1WqGqTodq6spRqr66GiIfMoi5tmbfR70QmNT-rsGVAH8"

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_KEY).worksheet("withdrawal requests")

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
guild = discord.Object(id=GUILD_ID)

# Constants
PAYMENT_METHODS = [
    "Interac E-transfer",
    "Crypto",
    "Debit Card",
    "PayPal",
    "Customer Payout",
    "Invoice Payment"
]


# Helper Functions
def log_to_google_sheet(client_id, book, amount, method):
    """Logs the withdrawal request to Google Sheets."""
    date = datetime.now().strftime("%m/%d/%Y")
    try:
        sheet.append_row(["", client_id, book, f"${amount:.2f}", "", method, "", date])
        return (
            f"Withdrawal logged:\n"
            f"**Client ID**: {client_id}\n"
            f"**Book**: {book}\n"
            f"**Amount**: ${amount:.2f}\n"
            f"**Method**: {method}\n"
            f"**Date**: {date}"
        )
    except Exception as e:
        return f"Failed to log data: {e}"


def validate_amount(amount):
    """Validates the withdrawal amount."""
    if amount <= 0:
        return False, "Error: The amount must be a positive number."
    return True, None


# Dropdown Classes
class MethodDropdown(discord.ui.Select):
    def __init__(self, amount, book):
        options = [discord.SelectOption(label=method) for method in PAYMENT_METHODS]
        super().__init__(placeholder="Select a withdrawal method", options=options)
        self.amount = amount
        self.book = book

    async def callback(self, interaction: discord.Interaction):
        selected_method = self.values[0]
        client_id = interaction.channel.name if interaction.channel else "Unknown"
        response = log_to_google_sheet(client_id, self.book, self.amount, selected_method)
        await interaction.response.edit_message(content=response, view=None)


class MethodDropdownView(discord.ui.View):
    def __init__(self, amount, book):
        super().__init__()
        self.add_item(MethodDropdown(amount, book))

# Command Functions
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    try:
        await bot.tree.sync(guild=guild)
        print("Slash commands synced!")
    except Exception as e:
        print(f"Error syncing commands: {e}")


@bot.tree.command(name="withdrawal", description="Log a withdrawal request", guild=guild)
@app_commands.describe(
    amount="Amount to withdraw (must be a positive number)",
    book="Book name (e.g., fanduel)"
)
async def withdrawal(interaction: discord.Interaction, amount: float, book: str):
    is_valid, error_message = validate_amount(amount)
    if not is_valid:
        await interaction.response.send_message(error_message, ephemeral=True)
        return

    # Send the dropdown menu to the user
    view = MethodDropdownView(amount, book)
    await interaction.response.send_message(
        "Please select a withdrawal method:", view=view, ephemeral=True
    )

# Run the bot
bot.run(TOKEN)
