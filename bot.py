import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
import database as db

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Ensure DB exists
db.init_db()
os.makedirs("images", exist_ok=True)

# === FSM states for upload and search ===
class UploadStates(StatesGroup):
    vin = State()
    oem = State()
    name = State()
    price = State()
    description = State()
    photo = State()
    confirm = State()

class SearchStates(StatesGroup):
    choose = State()
    query = State()
    price_range_min = State()
    price_range_max = State()

# --- Utility: build main menu keyboard
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Browse Parts", callback_data="browse_0")],
        [InlineKeyboardButton(text="🔧 Upload a Part", callback_data="upload")],
        [InlineKeyboardButton(text="🔍 Search Parts", callback_data="search")],
    ])

# === /start command ===
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Welcome to *DetalTap* — your digital garage!\nChoose an option below:",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )

# === Callback: Browse ===
@dp.callback_query(F.data == "browse")
async def cb_browse(query: types.CallbackQuery):
    await query.answer()
    rows = db.get_latest_parts(limit=10)
    if not rows:
        await query.message.answer("No parts uploaded yet. Be the first to upload!")
        return
    await query.message.answer("🛒 Latest parts:")
    for row in rows:
        part_id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date = row
        caption = f"🔧 *{name}*\nVIN: `{vin}` | OEM: `{oem}`\n💰 *{price} AZN*\n📝 {description}"
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Contact Seller", callback_data=f"contact_{part_id}")],
            [InlineKeyboardButton(text="View Details", callback_data=f"view_{part_id}")]
        ])
        if photo_path and os.path.exists(photo_path):
            try:
                await bot.send_photo(chat_id=query.from_user.id, photo=FSInputFile(photo_path), caption=caption, parse_mode="Markdown", reply_markup=buttons)
            except Exception:
                # fallback to text if photo sending fails
                await query.message.answer(caption, parse_mode="Markdown", reply_markup=buttons)
        else:
            await query.message.answer(caption, parse_mode="Markdown", reply_markup=buttons)

# === Callback: Upload start ===
@dp.callback_query(F.data == "upload")
async def cb_upload(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await query.message.answer("🔧 Upload flow started. Please enter the *VIN* code for the vehicle:", parse_mode="Markdown")
    await state.set_state(UploadStates.vin)

# === Upload flow handlers ===
@dp.message(UploadStates.vin, F.text)
async def upload_vin(message: Message, state: FSMContext):
    await state.update_data(vin=message.text.strip())
    await message.answer("Now enter the *OEM code* for the part (or type `none`):", parse_mode="Markdown")
    await state.set_state(UploadStates.oem)

@dp.message(UploadStates.oem, F.text)
async def upload_oem(message: Message, state: FSMContext):
    await state.update_data(oem=message.text.strip())
    await message.answer("What is the *part name*? (e.g., 'Front Brake Pads')", parse_mode="Markdown")
    await state.set_state(UploadStates.name)

@dp.message(UploadStates.name, F.text)
async def upload_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Enter the *price* in AZN (numbers only):", parse_mode="Markdown")
    await state.set_state(UploadStates.price)

@dp.message(UploadStates.price, F.text)
async def upload_price(message: Message, state: FSMContext):
    text = message.text.strip().replace(",", ".")
    try:
        val = float(text)
    except ValueError:
        await message.answer("Please enter a valid numeric price (e.g. 120 or 99.50).")
        return
    await state.update_data(price=val)
    await message.answer("Add a short *description* for the part (condition, notes):", parse_mode="Markdown")
    await state.set_state(UploadStates.description)

@dp.message(UploadStates.description, F.text)
async def upload_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("Finally, please *send a photo* of the part (clear photo).", parse_mode="Markdown")
    await state.set_state(UploadStates.photo)

@dp.message(UploadStates.photo, F.photo)
async def upload_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    
    # Save photo properly
    dest_path = f"images/{message.photo[-1].file_unique_id}.jpg"
    await bot.download(message.photo[-1], destination=dest_path)

    # 🟢 Store the photo path in FSM memory
    await state.update_data(photo_path=dest_path)

    vin = data.get("vin", "")
    oem = data.get("oem", "")
    name = data.get("name", "")
    price = data.get("price", 0)
    description = data.get("description", "")

    caption = (
        f"🔎 *Please confirm your listing:*\n\n"
        f"*Name:* {name}\n"
        f"*VIN:* `{vin}`\n"
        f"*OEM:* `{oem}`\n"
        f"*Price:* *{price} AZN*\n"
        f"*Description:* {description}"
    )

    uploader_id = message.from_user.id
    uploader_username = message.from_user.username if message.from_user.username else None
    await state.update_data(uploader_id=uploader_id, uploader_username=uploader_username)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm and Upload", callback_data="confirm_upload")],
        [InlineKeyboardButton(text="🔄 Cancel", callback_data="cancel_upload")]
    ])

    photo = FSInputFile(dest_path)
    await message.answer_photo(photo=photo, caption=caption, parse_mode="Markdown", reply_markup=kb)

    await state.set_state(UploadStates.confirm)

@dp.callback_query(F.data == "confirm_upload")
async def cb_confirm_upload(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()
    # Save to DB
    db.add_part(
        vin=data.get("vin", ""),
        oem=data.get("oem", ""),
        name=data.get("name", ""),
        price=float(data.get("price", 0)),
        description=data.get("description", ""),
        photo_path=data.get("photo_path", ""),
        uploader_id=int(data.get("uploader_id")),
        uploader_username=data.get("uploader_username")
    )
    await query.message.answer("✅ Your part was uploaded successfully! Thanks — it will appear in Browse/Search.")
    await state.clear()

@dp.callback_query(F.data == "cancel_upload")
async def cb_cancel_upload(query: types.CallbackQuery, state: FSMContext):
    await query.answer("Upload cancelled.")
    await state.clear()

# === Callback: Search start ===
@dp.callback_query(F.data == "search")
async def cb_search_start(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 By Name/Keyword", callback_data="search_name")],
        [InlineKeyboardButton(text="🚗 By VIN", callback_data="search_vin")],
        [InlineKeyboardButton(text="⚙️ By OEM", callback_data="search_oem")],
        [InlineKeyboardButton(text="💸 By Price Range", callback_data="search_price")],
        [InlineKeyboardButton(text="↩️ Back", callback_data="back_menu")]
    ])
    await query.message.answer("How do you want to search?", reply_markup=kb)
    await state.set_state(SearchStates.choose)

# specific search options

@dp.callback_query(F.data == "search_price")
async def cb_search_price(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await query.message.answer("Enter minimum price (AZN):")
    await state.set_state(SearchStates.price_range_min)

# handle search text (depending on state)
@dp.message(SearchStates.query, F.text)
async def process_search_query(message: Message, state: FSMContext):
    q = message.text.strip()
    cur_state = await state.get_state()
    # we determine which search mode by reading the previous callback; for simplicity store chosen type in storage
    # but here we read the state machine: if state is SearchStates.query it's used for name/vin/oem depending on prior action
    # To know which type the user selected, we'll rely on an extra stored key in state data
    data = await state.get_data()
    mode = data.get("mode")
    # Fallback: try keyword search
    if not mode:
        # assume name/keyword
        rows = db.search_parts_by_keyword(q)
    else:
        if mode == "name":
            rows = db.search_parts_by_keyword(q)
        elif mode == "vin":
            rows = db.search_parts_by_vin(q)
        elif mode == "oem":
            rows = db.search_parts_by_oem(q)
        else:
            rows = db.search_parts_by_keyword(q)

    if not rows:
        await message.answer("No results found.")
    else:
        await message.answer(f"🔍 Results for: *{q}*", parse_mode="Markdown")
        for row in rows:
            part_id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date = row
            caption = f"🔧 *{name}*\nVIN: `{vin}` | OEM: `{oem}`\n💰 *{price} AZN*\n📝 {description}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Contact Seller", callback_data=f"contact_{part_id}")],
                [InlineKeyboardButton(text="View Details", callback_data=f"view_{part_id}")]
            ])
            if photo_path and os.path.exists(photo_path):
                await message.answer_photo(photo=FSInputFile(photo_path), caption=caption, parse_mode="Markdown", reply_markup=kb)
            else:
                await message.answer(caption, parse_mode="Markdown", reply_markup=kb)

    await state.clear()

# handle price-range steps
@dp.message(SearchStates.price_range_min, F.text)
async def price_min(message: Message, state: FSMContext):
    try:
        vmin = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("Please enter a valid number for minimum price.")
        return
    await state.update_data(price_min=vmin)
    await message.answer("Enter maximum price (AZN):")
    await state.set_state(SearchStates.price_range_max)

@dp.message(SearchStates.price_range_max, F.text)
async def price_max(message: Message, state: FSMContext):
    try:
        vmax = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("Please enter a valid number for maximum price.")
        return
    data = await state.get_data()
    vmin = data.get("price_min", 0)
    rows = db.search_parts_by_price_range(vmin, vmax)
    if not rows:
        await message.answer("No parts found in that price range.")
    else:
        await message.answer(f"🔎 Results between {vmin} AZN and {vmax} AZN:")
        for row in rows:
            part_id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date = row
            caption = f"🔧 *{name}*\nVIN: `{vin}` | OEM: `{oem}`\n💰 *{price} AZN*\n📝 {description}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Contact Seller", callback_data=f"contact_{part_id}")],
                [InlineKeyboardButton(text="View Details", callback_data=f"view_{part_id}")]
            ])
            if photo_path and os.path.exists(photo_path):
                await message.answer_photo(photo=FSInputFile(photo_path), caption=caption, parse_mode="Markdown", reply_markup=kb)
            else:
                await message.answer(caption, parse_mode="Markdown", reply_markup=kb)
    await state.clear()

# To remember search mode (we need to set 'mode' before user types query)
@dp.callback_query(F.data == "search_name")
async def cb_search_name_set(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(mode="name")
    await query.message.answer("Enter name or keyword:")
    await state.set_state(SearchStates.query)

@dp.callback_query(F.data == "search_vin")
async def cb_search_vin_set(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(mode="vin")
    await query.message.answer("Enter VIN (exact match):")
    await state.set_state(SearchStates.query)

@dp.callback_query(F.data == "search_oem")
async def cb_search_oem_set(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(mode="oem")
    await query.message.answer("Enter OEM code (exact match):")
    await state.set_state(SearchStates.query)

# === View details handler (optional) ===
@dp.callback_query(F.data.startswith("view_"))
async def cb_view_detail(query: types.CallbackQuery):
    await query.answer()
    part_id = int(query.data.split("_", 1)[1])
    row = db.get_part_by_id(part_id)
    if not row:
        await query.message.answer("Part not found.")
        return
    part_id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date = row
    caption = (f"🔎 *{name}*\nVIN: `{vin}`\nOEM: `{oem}`\n💰 *{price} AZN*\n"
               f"📝 {description}\n\nUploaded by: @{uploader_username if uploader_username else str(uploader_id)}")
    if photo_path and os.path.exists(photo_path):
        await bot.send_photo(chat_id=query.from_user.id, photo=FSInputFile(photo_path), caption=caption, parse_mode="Markdown")
    else:
        await query.message.answer(caption, parse_mode="Markdown")

# === Contact seller flow ===
@dp.callback_query(F.data.startswith("contact_"))
async def cb_contact_seller(query: types.CallbackQuery):
    await query.answer()
    part_id = int(query.data.split("_", 1)[1])
    row = db.get_part_by_id(part_id)
    if not row:
        await query.message.answer("Part not found.")
        return
    _, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date = row

    # Notify seller: we'll forward a templated message to seller with buyer info
    buyer = query.from_user
    buyer_name = f"@{buyer.username}" if buyer.username else f"{buyer.full_name} (id:{buyer.id})"

    # send message to seller
    try:
        await bot.send_message(uploader_id,
                               f"🟢 Someone is interested in your listing *{name}*.\n"
                               f"Buyer: {buyer_name}\n"
                               f"Message from bot: If you want to contact, reply to this message or open chat with the buyer.",
                               parse_mode="Markdown")
        await query.message.answer("✅ I notified the seller. They will contact you soon (or check their Telegram).")
    except Exception:
        # If bot cannot message (seller blocked bot) fallback: provide seller username if available
        if uploader_username:
            await query.message.answer(f"Seller's username: @{uploader_username}. You can message them directly.")
        else:
            await query.message.answer("Could not message seller. Seller may have privacy settings. Try browsing other listings or ask admin for help.")

@dp.callback_query(F.data.startswith("browse_"))
async def browse_parts_handler(callback: CallbackQuery):
    page = int(callback.data.split("_")[1])
    PAGE_SIZE = 5  # change as you like

    offset = page * PAGE_SIZE

    # Fetch listings with limit/offset
    parts = db.fetch_parts(limit=PAGE_SIZE, offset=offset)
    total_count = db.count_parts()

    if not parts:
        await callback.message.edit_text("No parts found.")
        return

    text = "📦 *Car Parts*\n\n"

    for part in parts:
        text += (
            f"🆔 ID: {part['id']}\n"
            f"🚗 VIN: {part['vin']}\n"
            f"📦 OEM: {part['oem']}\n"
            f"💵 Price: {part['price']} AZN\n"
            f"📄 {part['description'][:50]}...\n"
            f"---\n"
        )

    # Build pagination buttons
    buttons = []

    # Previous
    if page > 0:
        buttons.append(
            InlineKeyboardButton(text="⬅ Previous", callback_data=f"browse_{page-1}")
        )

    # Next
    if offset + PAGE_SIZE < total_count:
        buttons.append(
            InlineKeyboardButton(text="Next ➡", callback_data=f"browse_{page+1}")
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])

    await callback.message.edit_text(
        text, reply_markup=keyboard, parse_mode="Markdown"
    )
    
# === Start polling ===
async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
