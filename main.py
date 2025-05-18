import logging
from telegram.constants import ParseMode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Tambahan: Mode Maintenance
MAINTENANCE_MODE = {"active": False, "message_ids": {}}

# Command untuk ON/OFF Maintenance
async def maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args or args[0].lower() not in ["on", "off"]:
        await update.message.reply_text("Gunakan: /maintenance on atau /maintenance off")
        return

    MAINTENANCE_MODE["active"] = args[0].lower() == "on"
    status = "AKTIF (Bot Maintenance)" if MAINTENANCE_MODE["active"] else "NON-AKTIF (Bot Aktif)"

    # Notifikasi ke semua user yang disetujui
    if MAINTENANCE_MODE["active"]:
        for uid in approved_users:
            if uid == ADMIN_ID:
                continue
            try:
                msg = await context.bot.send_message(uid, "⚙️ Bot is under maintenance ⚙️\n\nSilakan coba kembali beberapa saat lagi.")
                MAINTENANCE_MODE["message_ids"][uid] = msg.message_id
            except:
                pass
    else:
        for uid in approved_users:
            if uid == ADMIN_ID:
                continue
            try:
                if uid in MAINTENANCE_MODE["message_ids"]:
                    await context.bot.delete_message(uid, MAINTENANCE_MODE["message_ids"][uid])
                    del MAINTENANCE_MODE["message_ids"][uid]
            except:
                pass
            try:
                msg = await context.bot.send_message(uid, "🟢 Bot is active again 🟢\n\nSilakan gunakan layanan seperti biasa.")
                MAINTENANCE_MODE["message_ids"][uid] = msg.message_id
            except:
                pass

    await update.message.reply_text(f"✅ MODE {status}")

# Cek sebelum setiap interaksi
async def check_maintenance(update: Update) -> bool:
    if MAINTENANCE_MODE["active"] and update.effective_user.id != ADMIN_ID:
        if update.message:
            await update.message.reply_text("⚙️ Bot is under maintenance ⚙️\n\nSilakan coba kembali beberapa saat lagi.")
        elif update.callback_query:
            await update.callback_query.answer("Bot is under maintenance", show_alert=True)
        return True
    return False

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

USER_DATA_FILE = "users.json"

approved_users = set()
blocked_users = set()
requests_db = {}
user_requests = {}  # Tambahan untuk blokir spam

def save_users():
    with open(USER_DATA_FILE, "w") as f:
        json.dump({
            "approved": list(approved_users),
            "blocked": list(blocked_users)
        }, f)

def load_users():
    global approved_users, blocked_users
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            data = json.load(f)
            approved_users = set(data.get("approved", []))
            blocked_users = set(data.get("blocked", []))
    approved_users.add(ADMIN_ID)

def is_allowed(user_id: int) -> bool:
    return user_id in approved_users and user_id not in blocked_users

async def list_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if approved_users:
        msg = "✅ <b>Daftar Pengguna Disetujui:</b>\n"
        for uid in approved_users:
            try:
                user = await context.bot.get_chat(uid)
                username = user.username or user.first_name or "(tanpa nama)"
                msg += f"🆔 <code>{uid}</code> | @{username}\n"
            except:
                msg += f"- <code>{uid}</code> | (tidak ditemukan)\n"
    else:
        msg = "(Kosong) Tidak ada pengguna yang disetujui."

    await update.message.reply_text(msg, parse_mode="HTML")

async def list_blocked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if blocked_users:
        msg = "⛔ <b>Daftar Pengguna Diblokir:</b>\n"
        for uid in blocked_users:
            try:
                user = await context.bot.get_chat(uid)
                username = user.username or user.first_name or "(tanpa nama)"
                msg += f"🆔 <code>{uid}</code> | @{username}\n"
            except:
                msg += f"- <code>{uid}</code> | (tidak ditemukan)\n"
    else:
        msg = "(Kosong) Tidak ada pengguna yang diblokir."

    await update.message.reply_text(msg, parse_mode="HTML")

async def admin_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        return

    parts = update.message.text.split()
    if len(parts) != 2:
        await update.message.reply_text("Format salah. Gunakan:\n/approve user_id atau /block user_id")
        return

    command, uid = parts
    try:
        uid = int(uid)
    except ValueError:
        await update.message.reply_text("User ID harus berupa angka.")
        return

    if command == "/approve":
        approved_users.add(uid)
        blocked_users.discard(uid)
        save_users()

        if uid in requests_db and requests_db[uid].get("waiting_message_id"):
            try:
                await context.bot.delete_message(chat_id=uid, message_id=requests_db[uid]["waiting_message_id"])
            except:
                pass
            try:
                await context.bot.send_message(
                    uid,
                    "✅ Selamat! Anda telah mendapatkan akses.\n\n"
                    "📌 Silakan ketik /start untuk memulai.\n\n"
                    "⚠️ Kami tidak bertanggung jawab atas segala risiko hukum atau konsekuensi yang timbul akibat penyalahgunaan alat ini.",
                )

            except:
                pass
            del requests_db[uid]

        await update.message.reply_text(f"✅ Pengguna {uid} telah disetujui.")
    elif command == "/block":
        blocked_users.add(uid)
        approved_users.discard(uid)
        save_users()
        approved_users.discard(uid)
        # Hapus notifikasi sebelumnya jika ada
        if uid in requests_db and requests_db[uid].get("waiting_message_id"):
            try:
                await context.bot.delete_message(chat_id=ADMIN_ID, message_id=requests_db[uid]["waiting_message_id"])
            except:
                pass
        await update.message.reply_text(f"⛔ Pengguna {uid} telah diblokir.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_maintenance(update):
        if update.message and update.message.message_id:
            try:
                await update.message.delete()
            except:
                pass
        return
    if not is_allowed(update.effective_user.id):
        # Kirim notifikasi ke admin jika belum ada
        if update.effective_user.id not in requests_db:
            # Buat entry awal jika belum ada
            requests_db[update.effective_user.id] = {"waiting_message_id": None, "request_type": "approval_pending"}
            requests_db[update.effective_user.id] = {"waiting_message_id": None, "request_type": "approval_pending"}
            notify_text = (
                f"🔔 *Permintaan Akses Baru dari @{update.effective_user.username or 'User'}*\n"
                f"🆔 *User ID:* `{update.effective_user.id}`\n"
                f"✅ /approve `{update.effective_user.id}`\n"   
                f"⛔ /block `{update.effective_user.id}`"
            )

            await context.bot.send_message(ADMIN_ID, notify_text, parse_mode="Markdown")
        msg = await update.message.reply_text("⛔Illegal Access Attempt Detected⛔")
        requests_db[update.effective_user.id]["waiting_message_id"] = msg.message_id
        return
        return
    keyboard = [
        [InlineKeyboardButton("Lokasi", callback_data='lokasi'), InlineKeyboardButton("Profiling", callback_data='profiling')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text("Selamat datang di layanan kami. Silakan pilih apa yang ingin Anda lakukan", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Selamat datang di layanan kami. Silakan pilih apa yang ingin Anda lakukan", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_maintenance(update): return
    if not is_allowed(update.effective_user.id):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("⛔Illegal Access Attempt Detected⛔")
        return
    query = update.callback_query
    await query.answer()

    if query.data == 'profiling':
        keyboard = [
            [InlineKeyboardButton("📜 Registrasi Number", callback_data='reg_number')],
            [InlineKeyboardButton("📑 KK", callback_data='kk'), InlineKeyboardButton("🆔 NIK", callback_data='nik')],
            [InlineKeyboardButton("📸 Foto", callback_data='foto'), InlineKeyboardButton("🚗 Plat No", callback_data='plat_no')],
            [InlineKeyboardButton("🔍 FR", callback_data='fr'), InlineKeyboardButton("📞 NIK2Phone", callback_data='nik2phone')],
            [InlineKeyboardButton("🪪 Name2KTP", callback_data='name_ktp'), InlineKeyboardButton("📧 Email", callback_data='email')],
            [InlineKeyboardButton("🗺️ Lini Masa", callback_data='lini_masa'), InlineKeyboardButton("📦 Ekspedisi", callback_data='expedisi')],
            [InlineKeyboardButton("📲 MSISDN", callback_data='msisdn'), InlineKeyboardButton("🔢 IMEI Info", callback_data='imei_info')],
            [InlineKeyboardButton("📶 IMEI2Phone", callback_data='imei2phone'), InlineKeyboardButton("💳 BPJS", callback_data='bpjs')],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.effective_user.id in MAINTENANCE_MODE["message_ids"]:
            try:
                await context.bot.delete_message(chat_id=update.effective_user.id, message_id=MAINTENANCE_MODE["message_ids"][update.effective_user.id])
                del MAINTENANCE_MODE["message_ids"][update.effective_user.id]
            except:
                pass
        await query.edit_message_text('Silahkan pilih data profiling:', reply_markup=reply_markup)

    elif query.data == 'lokasi':
        keyboard = [
            [InlineKeyboardButton("📡 TELKOMSEL", callback_data='telkomsel'), InlineKeyboardButton("📡 XL", callback_data='xl')],
            [InlineKeyboardButton("📡 INDOSAT", callback_data='indosat'), InlineKeyboardButton("📡 SMARTFREN", callback_data='smartfren')],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.effective_user.id in MAINTENANCE_MODE["message_ids"]:
            try:
                await context.bot.delete_message(chat_id=update.effective_user.id, message_id=MAINTENANCE_MODE["message_ids"][update.effective_user.id])
                del MAINTENANCE_MODE["message_ids"][update.effective_user.id]
            except:
                pass
        await query.edit_message_text('Silakan pilih layanan provider dibawah ini:', reply_markup=reply_markup)

    elif query.data == 'telkomsel':
        await query.edit_message_text('Masukkan nomor TELKOMSEL dengan format yang benar.\n\nExample:\n#CPTELKOMSEL 081234567890')

    elif query.data == 'xl':
        await query.edit_message_text('Masukkan nomor XL dengan format yang benar.\n\nExample:\n#CPXL 081234567890')

    elif query.data == 'indosat':
        await query.edit_message_text('Masukkan nomor INDOSAT dengan format yang benar.\n\nExample:\n#CPINDOSAT 081234567890')

    elif query.data == 'smartfren':
        await query.edit_message_text('Masukkan nomor SMARTFREN dengan format yang benar.\n\nExample:\n#CPSMARTFREN 081234567890')

    elif query.data == 'start':
        await start(update, context)
    else:
        responses = {
            'reg_number': "Masukkan nomor HP dengan format yang benar.\n\nExample:\n#REG +6281231231234",
            'kk': "Masukkan nomor KK sesuai format.\n\nExample:\n#KK 3201234567890001",
            'nik': "Masukkan nomor NIK yang valid.\n\nExample:\n#NIK 3201234567890001",
            'foto': "Masukkan nomor NIK untuk menampilkan foto.\n\nExample:\n#FOTO 3201234567890001",
            'plat_no': "Masukkan nomor plat kendaraan.\n\nExample:\n#PLAT B1234CD",
            'fr': "Waktu FR habis, coba lagi besok pukul 07.00 - 10.00 WIB.",
            'nik2phone': "Dapatkan nomor HP dari NIK.\n\nExample:\n#N2P 3201234567890001",
            'name_ktp': "Cari data KTP dengan nama & tempat lahir.\n\nExample:\n#NTP Intan#Jakarta",
            'email': "Masukkan email dengan format yang benar.\n\nExample:\n#MAIL intan@gmail.com",
            'lini_masa': "Layanan lini masa untuk Tsel only.\n\nExample:\n#TI 081231231234",
            'expedisi': "Cek ekspedisi transaksi.\n\nExample:\n#NTM Intan-Jakarta\n#NTM 081231231234",
            'msisdn': "Cek nama provider dari nomor HP.\n\nExample:\n#MSISDN 081231231234",
            'imei_info': "Cek informasi IMEI.\n\nExample:\n#IMEI 123456789012345",
            'imei2phone': "Cek nomor HP dari IMEI untuk Telkomsel Only.\n\nExample:\n#IMEI2Phone 123456789012345",
            'bpjs': "Input NIK untuk mencari data BPJS.\n\nExample:\n#BPJS 123456789012345",
            }
        await query.edit_message_text(responses.get(query.data, 'Fitur sedang dikembangkan'))

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_maintenance(update): return
    user = update.message.from_user

    if not is_allowed(user.id):
        await update.message.reply_text("⛔Illegal Access Attempt Detected⛔")
        return

    if user.id in user_requests:
        if user_requests[user.id]["status"]:
            spam_msg = await update.message.reply_text("⏳ Processing... Please wait. Don't spam the bot.")
            user_requests[user.id]["spam_message_id"] = spam_msg.message_id
            return


    request_text = update.message.text.strip()

    logging.info(f"🔍 User {user.id} mengirim request: {request_text}")  # Debugging

    # Daftar kata kunci dan keterangan otomatis untuk semua request (termasuk lokasi)
    request_map = {
        "#REG": "Get REG NUMBER",
        "#KK": "Get KK",
        "#NIK": "Get NIK",
        "#FOTO": "Get FOTO",
        "#PLAT": "Get NOPOL",
        "#FR": "Get FR",
        "#N2P": "Get NIK2PHONE",
        "#NTP": "Get NAME2KTP",
        "#MAIL": "Get EMAIL",
        "#TI": "Get LINI MASA",
        "#NTM": "Get EXPEDISI",
        "#MSISDN": "Get MSISDN",
        "#IMEI": "Get IMEI INFORMATION",
        "#IMEI2Phone": "Get IMEI2PHONE",
        "#BPJS": "Get BPJS",

        # 🔥 Tambahan untuk Lokasi
        "#CPTELKOMSEL": "Get TELKOMSEL Location",
        "#CPXL": "Get XL Location",
        "#CPINDOSAT": "Get INDOSAT Location",
        "#CPSMARTFREN": "Get SMARTFREN Location"
    }

    # Cek apakah pesan mengandung kata kunci yang dikenali
    request_type = "Success"
    for key in request_map:
        if request_text.startswith(key):
            request_type = request_map[key]
            break

    # Jika tidak ada keyword yang cocok, beri peringatan ke pengguna
    if request_type == "Success":
        logging.warning(f"❌ Request dari {user.id} tidak dikenali: {request_text}")
        await update.message.reply_text("❌ Format permintaan tidak dikenali. Harap gunakan format yang benar.")
        return

    # Inisialisasi status user hanya jika request valid
    user_requests[user.id] = {
        "status": True,
        "spam_message_id": None
    }

    # Kirim konfirmasi ke pengguna bahwa permintaan mereka diterima
    sent_message = await update.message.reply_text('✅ Server kami sedang memproses permintaan Anda.\n\n⏳ Harap tunggu beberapa saat.')

    # Simpan request di database sementara untuk diproses admin
    requests_db[user.id] = {
        "waiting_message_id": sent_message.message_id,
        "request_type": request_type
    }

    # 🔥 Kirim permintaan ke admin dengan informasi lengkap
    admin_message = (
        f"🔔 *Permintaan Baru dari @{user.username if user.username else 'User'}*\n"
        f"📌 *Pesan:* `{request_text}`\n"
        f"🆔 *User ID:* `{user.id}`"
    )

    try:
        await context.bot.send_message(ADMIN_ID, admin_message, parse_mode="Markdown")
        logging.info(f"✅ Permintaan dari {user.id} berhasil dikirim ke admin.")
    except Exception as e:
        logging.error(f"⚠️ Gagal mengirim permintaan ke admin: {e}")

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID or not update.message.text.startswith("/reply"):
        return

    parts = update.message.text.split("\n", 1)
    if len(parts) < 2:
        await update.message.reply_text("Format salah! Gunakan:\n/reply user_id\n[Hasil]")
        return

    user_id = int(parts[0].split()[1])
    result = parts[1]

    if user_id in requests_db:
        request_type = requests_db[user_id].get("request_type", "Success")
        waiting_message_id = requests_db[user_id].get("waiting_message_id")
        if waiting_message_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=waiting_message_id)
            except:
                pass

        from telegram.helpers import escape_markdown

        escaped_result = escape_markdown(result, version=2)

        await context.bot.send_message(
            chat_id=user_id,
            text=f"Code: 200\n"
                 f"Keterangan: {request_type}\n\n"
                 f"Kami Tidak Bertanggung Jawab Atas Segala Dampak Atau Kerugian Yang Ditimbulkan Akibat Penyalahgunaan Alat Ini.\n\n"
                 f"{result}\n\n"
                 f"++===ꦄꦤꦏ꧀ ꦧꦤ꧀ꦒ꧀ꦱ===++",
            parse_mode=None  # non-Markdown to avoid escape error
        )
        await update.message.reply_text("✅ Hasil telah dikirim ke pengguna.")

        # Hapus pesan spam jika ada dan reset status user
        if user_id in user_requests:
            spam_msg_id = user_requests[user_id].get("spam_message_id")
            if spam_msg_id:
                try:
                    await context.bot.delete_message(chat_id=user_id, message_id=spam_msg_id)
                except:
                    pass
            del user_requests[user_id]

        del requests_db[user_id]
    else:
        await update.message.reply_text("⚠️ ID pengguna tidak ditemukan atau sudah diproses sebelumnya.")

async def admin_media_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        return

    # Cek apakah pesan berupa media dengan caption /reply
    if not update.message.caption or not update.message.caption.startswith("/reply"):
        return

    # Pastikan ini media
    if not (update.message.photo or update.message.document):
        return

    parts = update.message.caption.strip().split()

    # Minimal harus ada 2 elemen: /reply dan user_id
    if len(parts) != 2 or parts[0] != "/reply":
        await update.message.reply_text("Format salah! Gunakan:\n/reply user_id")
        return

    try:
        user_id = int(parts[1])
    except:
        await update.message.reply_text("User ID tidak valid.")
        return

    # Default pesan jika tidak ada hasil tambahan
    result = ""

    if user_id not in requests_db:
        await update.message.reply_text("⚠️ ID pengguna tidak ditemukan atau sudah diproses sebelumnya.")
        return

    # Hapus loading message jika ada
    waiting_message_id = requests_db[user_id].get("waiting_message_id")
    if waiting_message_id:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=waiting_message_id)
        except:
            pass

    try:
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=update.message.photo[-1].file_id,
                caption=(
                    f"*Code: 200*\n"
                    f"*Keterangan: {requests_db[user_id].get('request_type', 'Success')}*\n\n"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        elif update.message.document:
            await context.bot.send_document(
                chat_id=user_id,
                document=update.message.document.file_id,
                caption=result,
                parse_mode=ParseMode.MARKDOWN
            )
        # Tambah dukungan lain (audio/video) bila diperlukan
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal kirim media: {e}")
        return

    await update.message.reply_text("✅ Media dan hasil telah dikirim ke pengguna.")

    # Hapus spam dan reset
    if user_id in user_requests:
        spam_msg_id = user_requests[user_id].get("spam_message_id")
        if spam_msg_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=spam_msg_id)
            except:
                pass
        del user_requests[user_id]
    del requests_db[user_id]

if __name__ == '__main__':
    load_users()
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_admin))
    application.add_handler(MessageHandler(filters.Chat(int(ADMIN_ID)) & filters.TEXT & filters.Regex('^/reply'), admin_reply))
    application.add_handler(MessageHandler(filters.Chat(int(ADMIN_ID)) & filters.TEXT & filters.Regex(r'^/(approve|block) \d+$'), admin_control))
    application.add_handler(CommandHandler("list_approved", list_approved, filters.Chat(ADMIN_ID)))
    application.add_handler(CommandHandler("list_blocked", list_blocked, filters.Chat(ADMIN_ID)))
    application.add_handler(CommandHandler("maintenance", maintenance, filters.Chat(ADMIN_ID)))

    print("Starting bot...")

    application.add_handler(MessageHandler(
        filters.Chat(int(ADMIN_ID)) & filters.ALL,
        admin_media_reply
    ))

    application.run_polling()
