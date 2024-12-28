import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
import asyncio
from datetime import datetime
import gspread
from gspread.utils import ValueInputOption
from google.oauth2.service_account import Credentials

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("SERVER_ID"))

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = "keys.json"
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(os.getenv("GOOGLE_SHEET_KEY")).worksheet("withdrawal requests")

# Bot setup
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

BOOKS = [
    "FANDUEL", "888CASINO", "BALLY", "BET365", "BETANO", "BET99", "BETDSI", "BETMGM",
    "BETONLINE", "BETRIVERS", "BETSAFE", "BETUS", "BETVICTOR", "BETWAY", "BETWHALE",
    "BODOG", "BOOKMAKER", "BWIN", "CAESARS", "CASUMO", "DRAFTKINGS", "FITZDARES", "LEOVEGAS",
    "MYBOOKIE", "NEO", "NORTHSTAR BET", "PARTY SPORTS", "PINNY", "PLAY FALLSVIEW", "POINTSBET",
    "POWER PLAY", "RIVALRY", "SPORTSBETTING.AG", "SPORTS INTERACTION", "TITAN",
    "THE SCORE BET", "TONYBET", "XBET", "TD", "RBC", "BETCRIS", "WILDZ"
]

BOOKS_PER_PAGE = 25


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
    amount="Amount to withdraw (must be a positive number)"
)
async def withdrawal(interaction: discord.Interaction, amount: float):
    if amount <= 0:
        await interaction.response.send_message(
            content="Error: The `amount` must be a positive number. Please try again.",
            ephemeral=True
        )
        return

    class BookPaginator(discord.ui.View):
        def __init__(self):
            super().__init__()
            self.page = 0
            self.selected_book = None
            self.update_dropdown()

        def update_dropdown(self):
            try:
                start = self.page * BOOKS_PER_PAGE
                end = start + BOOKS_PER_PAGE
                options = [
                    discord.SelectOption(label=book) for book in BOOKS[start:end]
                ]
                self.clear_items()
                self.add_item(BookDropdown(options))
                self.add_item(PreviousButton(self))
                self.add_item(NextButton(self))
            except Exception as err:
                print("ERROR UPDATING DROPDOWN: ", err)

        async def update_view(self, interaction):
            self.update_dropdown()
            await interaction.response.edit_message(view=self)

    class BookDropdown(discord.ui.Select):
        def __init__(self, options):
            super().__init__(placeholder="Select a book", options=options)

        async def callback(self, interaction: discord.Interaction):
            selected_book = self.values[0]
            view.selected_book = selected_book
            print(f"Book selected: {selected_book}")

            # Proceed to payment method selection
            view.clear_items()
            view.add_item(MethodDropdown())
            await interaction.response.edit_message(content=f"Book selected: {selected_book}\nPlease select a withdrawal method:", view=view)

    class PreviousButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(style=discord.ButtonStyle.primary, label="Previous", disabled=True)
            self.parent_view = view
            self.update_disable_button()

        def update_disable_button(self):
            if self.parent_view.page > 0:
                self.disabled = self.parent_view.page == 0

        async def callback(self, interaction: discord.Interaction):
            if view.page > 0:
                view.page -= 1
                self.disabled = view.page == 0
                view.update_dropdown()
                await interaction.response.edit_message(view=view)

    class NextButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(style=discord.ButtonStyle.primary, label="Next", disabled=False)
            self.parent_view = view
            self.update_disable_button()

        def update_disable_button(self):
            if self.parent_view.page > 0:
                self.disabled = (self.parent_view.page + 1) * BOOKS_PER_PAGE >= len(BOOKS)

        async def callback(self, interaction: discord.Interaction):
            if (view.page + 1) * BOOKS_PER_PAGE < len(BOOKS):
                view.page += 1
                self.disabled = (view.page + 1) * BOOKS_PER_PAGE >= len(BOOKS)
                view.update_dropdown()
                await interaction.response.edit_message(view=view)

    class MethodDropdown(discord.ui.Select):
        def __init__(self):
            options = [discord.SelectOption(label=method) for method in PAYMENT_METHODS]
            super().__init__(placeholder="Select a withdrawal method", options=options)

        async def callback(self, interaction: discord.Interaction):
            selected_method = self.values[0]
            date = datetime.now().strftime("%m/%d/%Y")
            client_id = interaction.channel.name if interaction.channel else "Unknown"

            # Log the data into Google Sheets
            try:
                print(f"Logging data: Client ID: {client_id}, Amount: ${amount:.2f}, Book: {view.selected_book}, Method: {selected_method}, Date: {date}")
                val = ["", client_id, view.selected_book, f"${amount:.2f}", "", selected_method, "", date]
                sheet.append_row(val, value_input_option=ValueInputOption.user_entered)

                response = (
                    f"**Withdrawal logged successfully!**\n\n"
                    f"**Client ID:** {client_id}\n"
                    f"**Book:** {view.selected_book}\n"
                    f"**Amount:** ${amount:.2f}\n"
                    f"**Method:** {selected_method}\n"
                    f"**Date:** {date}"
                )
            except Exception as e:
                print(f"Error logging to Google Sheets: {e}")
                response = f"Failed to log data: {e}"

            await interaction.response.edit_message(content=response, view=None)

    view = BookPaginator()
    await interaction.response.send_message("Please select a book:", view=view)

bot.run(TOKEN)
