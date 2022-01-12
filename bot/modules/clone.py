from telegram.ext import CommandHandler
from bot import FSUB_ENABLED, FSUB_CHANNEL_ID, FSUB_CHANNEL_LINK, SUDO_USERS, OWNER_ID
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import *
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.bot_utils import new_thread
from bot.helper.telegram_helper import button_build
from bot import bot, dispatcher, LOG_UNAME


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
                    f"Why don't you join {FSUB_CHANNEL_LINK} first and try using me again?"
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
                cc = f'\n\nReq. By: {uname}\n\n'
            logmsg = sendLog(result + cc, context.bot, update, button)

            try:
                pmmsg = sendPrivate(result + cc, context.bot, update, button)
            except PrivateMessage as e:
            
                if "Message" in str(e):
                    prouser = f"<b>You Haven't Started the Bot In PM for Getting Links\nPlease Start Bot In PM\nFor Now Get Links From @{LOG_UNAME}</b>"
                    botstart = f"http://t.me/{bot.username}?start=start"
                    pmb = button_build.ButtonMaker()
                    pmb.buildbutton("Start Bot", f"{botstart}")
                    pmb.buildbutton("Get Your Links", f"{logmsg.link}")
                    sendMarkup(result + cc + prouser, context.bot, update, InlineKeyboardMarkup(pmb.build_menu(2)))
                    return

        fwdpm = f"<b>Check Your PM For Ur Uploaded Course Link</b>"
        if pmmsg:
            sendMessage(result + cc + fwdpm, context.bot, update)
        else:
            pass
    else:
        sendMessage("Provide G-Drive Shareable Link to Clone.",context.bot,update)

clone_handler = CommandHandler(BotCommands.CloneCommand,cloneNode,filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
dispatcher.add_handler(clone_handler)
