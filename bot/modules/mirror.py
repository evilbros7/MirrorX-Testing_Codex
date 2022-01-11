from telegram import InlineKeyboardMarkup, ParseMode
import requests
from telegram.ext import CommandHandler

from bot import Interval, INDEX_URL, BUTTON_THREE_NAME, BUTTON_THREE_URL, BUTTON_FOUR_NAME, BUTTON_FOUR_URL, BUTTON_FIVE_NAME, BUTTON_FIVE_URL, BLOCK_MEGA_LINKS, FSUB_ENABLED, FSUB_CHANNEL_ID, FSUB_CHANNEL_LINK, SOURCE_LOG
from bot import bot, dispatcher, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL, download_dict, download_dict_lock, SHORTENER, SHORTENER_API, LOG_UNAME
from bot import SUDO_USERS, OWNER_ID
from bot.helper.ext_utils import fs_utils, bot_utils
from bot.helper.ext_utils.bot_utils import setInterval
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException, NotSupportedExtractionArchive, PrivateMessage
from bot.helper.mirror_utils.download_utils.aria2_download import AriaDownloadHelper
from bot.helper.mirror_utils.download_utils.mega_downloader import MegaDownloadHelper
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.download_utils.telegram_downloader import TelegramDownloadHelper
from bot.helper.mirror_utils.status_utils import listeners
from bot.helper.mirror_utils.status_utils.extract_status import ExtractStatus
from bot.helper.mirror_utils.status_utils.tar_status import TarStatus
from bot.helper.mirror_utils.status_utils.upload_status import UploadStatus
from bot.helper.mirror_utils.status_utils.gdownload_status import DownloadStatus
from bot.helper.mirror_utils.upload_utils import gdriveTools
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import *
from bot.helper.telegram_helper import button_build
import urllib
import pathlib
import os
import subprocess
import threading
import re
import random
import string

ariaDlManager = AriaDownloadHelper()
ariaDlManager.start_listener()


class MirrorListener(listeners.MirrorListeners):
    def __init__(self, bot, update, pswd, isTar=False, tag=None, extract=False):
        super().__init__(bot, update)
        self.isTar = isTar
        self.tag = tag
        self.extract = extract
        self.pswd = pswd

    def onDownloadStarted(self):
        pass

    def onDownloadProgress(self):
        # We are handling this on our own!
        pass

    def clean(self):
        try:
            Interval[0].cancel()
            del Interval[0]
            delete_all_messages()
        except IndexError:
            pass

    def onDownloadComplete(self):
        with download_dict_lock:
            LOGGER.info(f"Download completed: {download_dict[self.uid].name()}")
            download = download_dict[self.uid]
            name = download.name()
            size = download.size_raw()
            if name is None: # when pyrogram's media.file_name is of NoneType
                name = os.listdir(f'{DOWNLOAD_DIR}{self.uid}')[0]
            m_path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        if self.isTar:
            download.is_archiving = True
            try:
                with download_dict_lock:
                    download_dict[self.uid] = TarStatus(name, m_path, size)
                path = fs_utils.tar(m_path)
            except FileNotFoundError:
                LOGGER.info('File to archive not found!')
                self.onUploadError('Internal error occurred!!')
                return
        elif self.extract:
            download.is_extracting = True
            try:
                path = fs_utils.get_base_name(m_path)
                LOGGER.info(
                    f"Extracting : {name} "
                )
                with download_dict_lock:
                    download_dict[self.uid] = ExtractStatus(name, m_path, size)
                pswd = self.pswd
                if pswd is not None:
                    archive_result = subprocess.run(["pextract", m_path, pswd])
                else:
                    archive_result = subprocess.run(["extract", m_path])
                if archive_result.returncode == 0:
                    threading.Thread(target=os.remove, args=(m_path,)).start()
                    LOGGER.info(f"Deleting archive : {m_path}")
                else:
                    LOGGER.warning('Unable to extract archive! Uploading anyway')
                    path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
                LOGGER.info(
                    f'got path : {path}'
                )

            except NotSupportedExtractionArchive:
                LOGGER.info("Not any valid archive, uploading file as it is.")
                path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        else:
            path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        up_name = pathlib.PurePath(path).name
        if up_name == "None":
            up_name = "".join(os.listdir(f'{DOWNLOAD_DIR}{self.uid}/'))
        up_path = f'{DOWNLOAD_DIR}{self.uid}/{up_name}'
        LOGGER.info(f"Upload Name : {up_name}")
        drive = gdriveTools.GoogleDriveHelper(up_name, self)
        size = fs_utils.get_path_size(up_path)
        upload_status = UploadStatus(drive, size, self)
        with download_dict_lock:
            download_dict[self.uid] = upload_status
        update_all_messages()
        drive.upload(up_name)

    def onDownloadError(self, error):
        error = error.replace('<', ' ')
        error = error.replace('>', ' ')
        LOGGER.info(self.update.effective_chat.id)
        with download_dict_lock:
            try:
                download = download_dict[self.uid]
                del download_dict[self.uid]
                LOGGER.info(f"Deleting folder: {download.path()}")
                fs_utils.clean_download(download.path())
                LOGGER.info(str(download_dict))
            except Exception as e:
                LOGGER.error(str(e))
                pass
            count = len(download_dict)
        if self.message.from_user.username:
            uname = f"@{self.message.from_user.username}"
        else:
            uname = f'<a href="tg://user?id={self.message.from_user.id}">{self.message.from_user.first_name}</a>'
        msg = f"{uname} your download has been stopped due to: {error}"
        sendMessage(msg, self.bot, self.update)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

    def onUploadStarted(self):
        pass

    def onUploadProgress(self):
        pass

    def onUploadComplete(self, link: str, size):
        with download_dict_lock:
            msg = f'<u>𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗕𝘆</u> <a href="https://t.me/CoursesDrive">📚 Courses Drive 📚</a>\n\n𝗙𝗶𝗹𝗲𝗻𝗮𝗺𝗲🗂 : <code>{download_dict[self.uid].name()}</code>\n𝗦𝗶𝘇𝗲 ⚖️ : <code>{download_dict[self.uid].size()}</code>\n\nOnly Use TeamDrive Link if you have Access.\nDon\'t request access through this link'

            buttons = button_build.ButtonMaker()
            if SHORTENER is not None and SHORTENER_API is not None:
                surl = requests.get(f'https://{SHORTENER}/api?api={SHORTENER_API}&url={link}&format=text').text
                buttons.buildbutton("📚 Course Link 📚", surl)
            else:
                buttons.buildbutton("📚 Course Link 📚", link)
            LOGGER.info(f'Done Uploading {download_dict[self.uid].name()}')
            if INDEX_URL is not None:
                url_path = requests.utils.quote(f'{download_dict[self.uid].name()}')
                share_url = f'{INDEX_URL}/{url_path}'
                if os.path.isdir(f'{DOWNLOAD_DIR}/{self.uid}/{download_dict[self.uid].name()}'):
                    share_url += '/'
                if SHORTENER is not None and SHORTENER_API is not None:
                    siurl = requests.get(f'https://{SHORTENER}/api?api={SHORTENER_API}&url={share_url}&format=text').text
                    buttons.buildbutton("🚀Index Link🚀", siurl)
                else:
                    buttons.buildbutton("🚀Index Link🚀", share_url)
            if BUTTON_THREE_NAME is not None and BUTTON_THREE_URL is not None:
                buttons.buildbutton(f"{BUTTON_THREE_NAME}", f"{BUTTON_THREE_URL}")
            if BUTTON_FOUR_NAME is not None and BUTTON_FOUR_URL is not None:
                buttons.buildbutton(f"{BUTTON_FOUR_NAME}", f"{BUTTON_FOUR_URL}")
            if BUTTON_FIVE_NAME is not None and BUTTON_FIVE_URL is not None:
                buttons.buildbutton(f"{BUTTON_FIVE_NAME}", f"{BUTTON_FIVE_URL}")
            if self.message.from_user.username:
                uname = f"@{self.message.from_user.username}"
            else:
                uname = f'<a href="tg://user?id={self.message.from_user.id}">{self.message.from_user.first_name}</a>'
            if uname is not None:
                msg += f'\n\nUploaded By 👉 : {uname}\n\n'
            try:
                fs_utils.clean_download(download_dict[self.uid].path())
            except FileNotFoundError:
                pass
            del download_dict[self.uid]
            count = len(download_dict)
        reply_to = self.message.reply_to_message
        if reply_to is not None:
            reply_to.delete()
       #sendMarkup(msg, self.bot, self.update, InlineKeyboardMarkup(buttons.build_menu(2)))

        # Log Channel
        logmsg = sendLog(msg, self.bot, self.update, InlineKeyboardMarkup(buttons.build_menu(2)))

        # Private Message
        try:
            pmmsg = sendPrivate(msg, self.bot, self.update, InlineKeyboardMarkup(buttons.build_menu(2)))
        except PrivateMessage as e:
            if "Message" in str(e):
                prouser = f"<b> You Haven't Started the Bot In PM for Getting Links\nPlease Start Bot In PM\nFor Now Get Links From @{LOG_UNAME}</b>"
                botstart = f"http://t.me/{bot.username}?start=start"
                pmb = button_build.ButtonMaker()
                pmb.buildbutton("Start Bot", f"{botstart}")
                pmb.buildbutton("Get Your Links", f"{logmsg.link}")
                sendMarkup(msg + prouser, self.bot, self.update, InlineKeyboardMarkup(pmb.build_menu(2)))
                return
  
        # Group Message
        fwdpm = f"<b> Check Your PM For Ur Uploaded Course Link</b>"
        if pmmsg:
            sendMessage(msg + fwdpm, self.bot, self.update)
        else:
            pass


        if count == 0:
            self.clean()
        else:
            update_all_messages()

    def onUploadError(self, error):
        e_str = error.replace('<', '').replace('>', '')
        with download_dict_lock:
            try:
                fs_utils.clean_download(download_dict[self.uid].path())
            except FileNotFoundError:
                pass
            del download_dict[self.message.message_id]
            count = len(download_dict)
        sendMessage(e_str, self.bot, self.update)
        if count == 0:
            self.clean()
        else:
            update_all_messages()


def _mirror(bot, update, isTar=False, extract=False):
    mesg = update.message.text.split('\n')
    message_args = mesg[0].split(' ')
    name_args = mesg[0].split('|')
    
    user_id = update.effective_user.id
    chat_id  = update.effective_chat.id
    admins = bot.get_chat_member(chat_id, user_id).status in ['creator', 'administrator'] or user_id in [OWNER_ID]
    uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
    uid = f"{update.message.from_user.id}"
    chatname = f"{update.message.chat.title}"
    
    user_is_normal = True
    if (user_id == OWNER_ID) or (user_id in SUDO_USERS):
        user_is_normal = False

    if user_is_normal:
        print("Normal User trying to access")
        if FSUB_ENABLED is True:
            member_sub_status = bot.get_chat_member(
                chat_id=FSUB_CHANNEL_ID,
                user_id=user_id
            )
            if member_sub_status.status not in ["creator", "administrator", "member", "restricted"]:
                update.effective_message.reply_markdown(
                    f"𝗙𝗶𝗿𝘁𝘀𝘁 𝗝𝗼𝗶𝗻 {FSUB_CHANNEL_LINK} 𝗔𝗻𝗱 𝗖𝗼𝗺𝗲 𝗕𝗮𝗰𝗸 𝗔𝗴𝗮𝗶𝗻 𝗨𝘀𝗲 𝗠𝗲"
                )
                return

    try:
        link = message_args[1]
        print(link)
        if link.startswith("|") or link.startswith("pswd: "):
            link = ''
    except IndexError:
        link = ''

    try:
        name = name_args[1]
        name = name.strip()
        if name.startswith("pswd: "):
            name = ''
    except IndexError:
        name = ''
    try:
        ussr = urllib.parse.quote(mesg[1], safe='')
        pssw = urllib.parse.quote(mesg[2], safe='')
    except:
        ussr = ''
        pssw = ''
    if ussr != '' and pssw != '':
        link = link.split("://", maxsplit=1)
        link = f'{link[0]}://{ussr}:{pssw}@{link[1]}'
    pswd = re.search('(?<=pswd: )(.*)', update.message.text)
    if pswd is not None:
      pswd = pswd.groups()
      pswd = " ".join(pswd)
    LOGGER.info(link)
    link = link.strip()
    reply_to = update.message.reply_to_message
    if reply_to is not None:
        file = None
        tag = reply_to.from_user.username
        media_array = [reply_to.document, reply_to.video, reply_to.audio]
        for i in media_array:
            if i is not None:
                file = i
                break



        if not bot_utils.is_url(link) and not bot_utils.is_magnet(link) or len(link) == 0:
            if reply_to and file is None:
                link = reply_to.text
                if link.startswith("BotCommands.MirrorCommand"):
                    sendMessage(f"Use /{BotCommands.UnzipMirrorCommand} [Magnet/Mega/Direct Links]\nOr use /{BotCommands.UnzipMirrorCommand} in the reply of Telegram File/Torrents to mirror 'em", bot, update)
                elif link.startswith("BotCommands.TarMirrorCommand"):
                    sendMessage(f"Use /{BotCommands.TarMirrorCommand} [Drive/Magnet/Mega/Direct Links]\nOr use /{BotCommands.TarMirrorCommand} in the reply of Torrents to archive 'em", bot, update)
                elif link.startswith("BotCommands.UnzipMirrorCommand"):
                    sendMessage(f"Use /{BotCommands.UnzipMirrorCommand} [Drive/Magnet/Mega/Direct Links]\nOr use /{BotCommands.UnzipMirrorCommand} in the reply of Telegram File/Torrents to extract 'em", bot, update)
                    return

        if not bot_utils.is_url(link) and not bot_utils.is_magnet(link) or len(link) == 0:
            if file is not None:
                if file.mime_type != "application/x-bittorrent":
                    listener = MirrorListener(bot, update, pswd, isTar, tag, extract)
                    tg_downloader = TelegramDownloadHelper(listener)
                    tg_downloader.add_download(reply_to, f'{DOWNLOAD_DIR}{listener.uid}/', name)
                    sendStatusMessage(update, bot)
                    if len(Interval) == 0:
                        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))
                    return
                else:
                    link = file.get_file().file_path
    else:
        tag = None
    if not bot_utils.is_url(link) and not bot_utils.is_magnet(link):
        sendMessage('No download source provided', bot, update)
        return

    try:
        link = direct_link_generator(link)
    except DirectDownloadLinkException as e:
        LOGGER.info(f'{link}: {e}')
    listener = MirrorListener(bot, update, pswd, isTar, tag, extract)

    if reply_to is not None and file is not None:
        itext = f"<b>Filename:</b> <code>{file.file_name}</code>\n<b>Size:</b> <code>{get_readable_file_size(file.file_size)}</code>\n\n"
        itext += f"<b>Sent By:</b> {uname}\n<b>User ID:</b> {uid}\n\n<b>To:</b> @{bot.username}\n<b>In: {chatname}</b>"
        info_ = copyFile(itext, bot, update)
        #info = sendInfo(itext, bot, update)
    else:
        info = sendInfo(f"<b>User:</b> {uname}\n<b>User ID:</b> <code>{uid}</code>\n<b>Sent:</b> <code>{link}</code>\n\n<b>To:</b> @{bot.username}\n<b>In: {chatname}</b>", bot, update)

    if bot_utils.is_gdrive_link(link):
        if not isTar and not extract:
            sendMessage(f"Use /{BotCommands.CloneCommand} To Copy File/Folder", bot, update)
            return
        res, size, name = gdriveTools.GoogleDriveHelper().clonehelper(link)
        if res != "":
            sendMessage(res, bot, update)
            return
        LOGGER.info(f"Download Name : {name}")
        drive = gdriveTools.GoogleDriveHelper(name, listener)
        gid = ''.join(random.SystemRandom().choices(string.ascii_letters + string.digits, k=12))
        download_status = DownloadStatus(drive, size, listener, gid)
        with download_dict_lock:
            download_dict[listener.uid] = download_status
        if len(Interval) == 0:
            Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))
        sendStatusMessage(update, bot)
        drive.download(link)

    elif bot_utils.is_mega_link(link):
        if BLOCK_MEGA_LINKS:
            sendMessage("Mega Links Are Blocked ✋", bot, update)
        else:
            mega_dl = MegaDownloadHelper()
            mega_dl.add_download(link, f'{DOWNLOAD_DIR}/{listener.uid}/', listener)
            sendStatusMessage(update, bot)
    else:
        ariaDlManager.add_download(link, f'{DOWNLOAD_DIR}/{listener.uid}/', listener, name)
        sendStatusMessage(update, bot)
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


def mirror(update, context):
    _mirror(context.bot, update)


def tar_mirror(update, context):
    _mirror(context.bot, update, True)


def unzip_mirror(update, context):
    _mirror(context.bot, update, extract=True)


mirror_handler = CommandHandler(BotCommands.MirrorCommand, mirror,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
tar_mirror_handler = CommandHandler(BotCommands.TarMirrorCommand, tar_mirror,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
unzip_mirror_handler = CommandHandler(BotCommands.UnzipMirrorCommand, unzip_mirror,
                                      filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
dispatcher.add_handler(mirror_handler)
dispatcher.add_handler(tar_mirror_handler)
dispatcher.add_handler(unzip_mirror_handler)
