import logging
from functools import wraps
from urllib.parse import quote

from telegram import (InputMediaPhoto, ReplyKeyboardMarkup,
                      ReplyKeyboardRemove, Update)
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, ChatJoinRequestHandler,
                          CommandHandler, ContextTypes, ConversationHandler,
                          MessageHandler, filters)

from database import *
from ton import *
from values import *

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

WAITING, SETTING_TON_WALLET, AWAITING_PAYMENT = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [["Set wallet", "Confirm wallet ownership", "Get chat invite"]]

    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=f"Welcome! In order to get access to the private channel, you must have an NFT from Diamonds collection (https://ton.diamonds/collection/ton-diamonds) in your wallet. {'currently disabled by settings' if SKIP_NFT_CHECK else ''}\nYou will also need to confirm that you can access the wallet with a transaction\nPlease, choose an action:", 
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
        ),
    )
    logging.info(f"User {update.effective_message.from_user.id} started the conversation")
    
    return WAITING

async def set_wallet_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Please enter your TON wallet address",
    )
    logging.info(f"User {update.effective_message.from_user.id} setting up wallet")
    
    return SETTING_TON_WALLET


async def set_wallet_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    insert(update.effective_message.from_user.id, update.effective_message.text)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Wallet set",)
    logging.info(f"User {update.effective_message.from_user.id} set up wallet {update.effective_message.text}")
    
    return WAITING


async def request_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet_id_from_db = get_wallet_by_telegram_id(update.effective_message.from_user.id)
    wallet_id = wallet_id_from_db[0][0] if wallet_id_from_db else None
    if not wallet_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="We do not see your wallet. Please, set it up first.")
        return WAITING
    ton_link = f'ton://transfer/{TARGET_WALLET}?amount=500000&text=verify{update.effective_message.from_user.id}'
    qr_code_link = f'https://api.qrserver.com/v1/create-qr-code/?size=200x200&margin=10&data={quote(ton_link)}'
    await context.bot.send_media_group(chat_id=update.effective_chat.id, media=[InputMediaPhoto(qr_code_link)], 
        caption=f'''
            <a href="{ton_link}"><i>Click here</i></a> or scan QR code and send <b>0.0005 TON</b>\n\nFrom <code>{wallet_id}</code>\n\nto <code>{TARGET_WALLET}</code>\n\nwith comment <code>verify{update.effective_message.from_user.id}</code>\n\nAfter the transfer, wait 10-15 seconds, then send any message to the bot.
        ''',
        parse_mode=ParseMode.HTML,
        )
    logging.info(f"User {update.effective_message.from_user.id} is going to send TON")
    
    return AWAITING_PAYMENT

async def get_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet_id_from_db = get_wallet_by_telegram_id(update.effective_message.from_user.id)
    wallet_id = wallet_id_from_db[0][0] if wallet_id_from_db else None
    if not wallet_id:
        logging.info(f"User {update.effective_message.from_user.id} is trying to get access without wallet")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="We do not see your wallet. Please, set it up first.")
        return WAITING

    if not check_payment_existence(update.effective_message.from_user.id, wallet_id):
        logging.info(f"User {update.effective_message.from_user.id} is trying to get access without payment")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="We do not see a transaction from your wallet. Please, send TON first.")
        return WAITING

    if SKIP_NFT_CHECK or await get_user_nfts(wallet_id):
        logging.info(f"User {update.effective_message.from_user.id} is getting access")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"You have access to the chat! {INVITE_LINK}")
        return ConversationHandler.END


async def check_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet_id_from_db = get_wallet_by_telegram_id(update.effective_message.from_user.id)
    wallet_id = wallet_id_from_db[0][0] if wallet_id_from_db else None
    if wallet_id:
        owner_addresses = await get_ton_addresses(wallet_id)
        result = json.loads(requests.get(
            f'{TONCENTER_BASE}getTransactions?address={TARGET_WALLET}&limit=10&to_lt=0&archival=false').text)['result']
        is_verified = False
        for i in result:
            transaction = i['in_msg']
            value = transaction['value']
            msg = transaction['message']
            source = transaction['source']
            if (int(value) >= 500000) and (msg == f"verify{update.effective_message.from_user.id}") and (
                    source == owner_addresses['b64url']):
                is_verified = True
                break
        if not is_verified:
            logging.info(f"User {update.effective_message.from_user.id} is trying to check payment without payment")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="You have not paid yet.\nSend any message to the bot to check again or /cancel to reset conversation.")
            return AWAITING_PAYMENT
        else:
            if not check_payment_existence(update.effective_message.from_user.id, wallet_id):
                date = transaction['created_lt']
                insert_payment(update.effective_message.from_user.id, tonWallet=wallet_id, amount=0.0005, date=date)
            logging.info(f"User {update.effective_message.from_user.id} payment found")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="We have confirmed you have paid. You have access to the bot!")
            return WAITING
    else:
        logging.info(f"User {update.effective_message.from_user.id} is trying to check payment without wallet")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="We do not see your wallet. Please, set it up first.")
        return WAITING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logging.info(f"User {update.effective_message.from_user.id} canceled the conversation.")
    await update.message.reply_text(
        "Bye! I hope we can talk again some day.", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

async def chat_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.chat_join_request.from_user.id
    wallet_id_from_db = get_wallet_by_telegram_id(user_id)
    wallet_id = wallet_id_from_db[0][0] if wallet_id_from_db else None
    if not wallet_id:
        logging.info(f"User {user_id} is trying to join chat without wallet")
        await update.chat_join_request.decline()
        return
    if not check_payment_existence(user_id, wallet_id):
        logging.info(f"User {user_id} is trying to join chat without payment")
        await update.chat_join_request.decline()
        return
    if  SKIP_NFT_CHECK or await get_user_nfts(wallet_id):
        logging.info(f"User {user_id} is getting access")
        await update.chat_join_request.approve() 
        return
    else:
        logging.info(f"User {user_id} is trying to join chat without NFT")
        await update.chat_join_request.decline()
        return

if __name__ == '__main__':
    create_tables()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SETTING_TON_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_wallet_save)],
            WAITING: [
                MessageHandler(filters.Regex("^Set wallet$"), set_wallet_prompt),
                MessageHandler(filters.Regex("^Confirm wallet ownership$"), request_ton),
                MessageHandler(filters.Regex("^Get chat invite$"), get_access),
                    ],
            AWAITING_PAYMENT: [
                MessageHandler(filters.Regex("^Set wallet$"), set_wallet_prompt),
                MessageHandler(filters.TEXT, check_transaction), 
                ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # chat join handler
    application.add_handler(ChatJoinRequestHandler(chat_join))

    application.add_handler(conv_handler)
    
    application.run_polling()