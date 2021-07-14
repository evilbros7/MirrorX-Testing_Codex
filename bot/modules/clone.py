from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler
from bot import FSUB_ENABLED, FSUB_CHANNEL_ID, FSUB_CHANNEL_LINK, SUDO_USERS, OWNER_ID
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import *
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.bot_utils import new_thread
from bot import dispatcher


def cloneNode(update,context):
    args = update.message.text.split(" ",maxsplit=1)
    
    user_id = update.effective_user.id

    user_is_normal = True
    if (user_id == OWNER_ID) or (user_id in SUDO_USERS):
        user_is_normal = False

    if user_is_normal:
        if FSUB_ENABLED is True:
            member_sub_status = bot.get_chat_member(
                chat_id=FSUB_CHANNEL_ID,
                user_id=user_id
            )
            if member_sub_status.status not in ["creator", "administrator", "member", "restricted"]:
                update.effective_message.reply_markdown(
                    f"*In order to use this bot, you have to be the member of {FSUB_CHANNEL_LINK}.\n\nJoin {FSUB_CHANNEL_LINK} and try using the bot again.*"
                )
                return
    
    if len(args) > 1:
        link = args[1]
        msg = sendMessage(f"Cloning: <code>{link}</code>",context.bot,update)
        gd = GoogleDriveHelper()
        result, button = gd.clone(link)
        deleteMessage(context.bot,msg)
        if button == "":
            sendMessage(result,context.bot,update)
        else:
            if update.message.from_user.username:
                uname = f'@{update.message.from_user.username}'
            else:
                uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
            if uname is not None:
                cc = f'\n\nReq. By: {uname}'
            sendMarkup(result + cc, context.bot, update, button)
    else:
        sendMessage("Provide G-Drive Shareable Link to Clone.",context.bot,update)

clone_handler = CommandHandler(BotCommands.CloneCommand,cloneNode,filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
dispatcher.add_handler(clone_handler)
