from random import randint
import json
import datetime as dt
import asyncio
from PIL import Image, ImageDraw, ImageFont

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, RetryAfter, TimedOut, NetworkError
import os
import math
import io
import re

DATA_FILE = 'users_data.json'

users_data = []
super_admins = []
pending_messages = []

help_text = '''Это новый бот подслушки для анонимных сообщений написанный - @justafriendt
Здесь можно отправлять в админам подслушки как обычные сообщения, как все привыкли, так и фото
По любым вопросам и предложениям можете писать в личку, почитаю учту исправлю. Надеюсь это станет лучшей заменой
других анонимок для нашей подслушки, приятного пользования!'''


def log(a):
    print(f'[] {dt.datetime.now()} - {a}')


def links_slice(s):
    pattern = r'(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)'
    links = re.findall(pattern, s)

    for i, j in enumerate(links):
        s = s.replace(j, f'*link {i + 1}*')

    links = [f'lnk{i + 1}: {j}' for i, j in enumerate(links[:])]

    return s, '\n'.join(links)


def load_users_data():
    global users_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            users_data = json.load(file)
    else:
        users_data = []

    global super_admins
    if os.path.exists('admins.json'):
        with open('admins.json', 'r') as file:
            super_admins = json.load(file)
    else:
        super_admins = []
    log('Admins info loaded')


def save_users_data():
    with open(DATA_FILE, 'w') as file:
        json.dump(users_data, file, indent=4)
    with open('admins.json', 'w') as file:
        json.dump(super_admins, file, indent=4)
    log('Admins info saved')


def wrap_text_pil(draw, text, font, max_width):
    """Функция для переноса текста на новые строки, если он превышает максимальную ширину."""
    lines = []
    words = text.split()

    current_line = []
    current_width = 0

    for word in words:
        # Получаем размеры текста с пробелом
        word_bbox = draw.textbbox((0, 0), word + ' ', font=font)
        word_width = word_bbox[2] - word_bbox[0]  # Ширина текста

        if current_width + word_width <= max_width:
            current_line.append(word)
            current_width += word_width
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
            current_width = word_width

    if current_line:
        lines.append(' '.join(current_line))

    return lines


def text_to_image(text, color, padding=40, right_padding_ratio=0.15, line_spacing=1.5, font_size=30,
                  font_path='ofont.ru_Franklin Gothic Medium.ttf'):
    # Настройки текста
    text_color = (0, 0, 0)  # Черный текст
    background_color = (255, 255, 255)  # Белый фон (RGB)

    # Загрузить шрифт
    if font_path is None:
        font = ImageFont.load_default()  # Использовать стандартный шрифт
    else:
        font = ImageFont.truetype(font_path, font_size)  # Использовать кастомный шрифт

    # Создаем временное изображение для расчета размеров текста
    temp_image = Image.new('RGB', (1, 1), background_color)
    draw = ImageDraw.Draw(temp_image)

    # Определяем максимальную ширину строки с учетом правого отступа
    max_width = 600
    max_text_width = max_width * (1 - right_padding_ratio)  # Учитываем отступ справа

    # Получаем строки с переносом
    lines = wrap_text_pil(draw, text, font, max_text_width)

    # Рассчитываем высоту и ширину изображения
    line_height = draw.textbbox((0, 0), 'X', font=font)[3]  # Высота одной строки
    text_height = line_height * len(lines) * line_spacing  # Высота всего текста с учетом межстрочного интервала

    # Добавляем отступы
    img_width = max_width + 2 * padding
    img_height = math.ceil(text_height + 2 * padding)

    # Создаем изображение с нужными размерами
    image = Image.new('RGB', (img_width, img_height), background_color)
    draw = ImageDraw.Draw(image)

    # Рисуем текст по строкам
    y_offset = padding  # Начинаем рисовать с учетом верхнего отступа

    for line in lines:
        line_bbox = draw.textbbox((0, 0), line, font=font)
        line_width = line_bbox[2] - line_bbox[0]  # Ширина строки
        x_offset = padding + 60  # Отступ слева
        draw.text((x_offset, y_offset), line, font=font, fill=text_color)
        y_offset += line_height * line_spacing  # Смещаем по вертикали с учетом интервала между строками

    tree = Image.open('per.png').convert('RGBA')
    pixels = tree.load()
    for x in range(tree.width):
        for y in range(tree.height):
            if pixels[x, y][0:3] == (108, 25, 255):
                pixels[x, y] = color
    we, he = tree.size
    tree = tree.resize((he - 10, we - 10))
    tree_alpha = tree.split()[-1]
    image.paste(tree, (0, img_height // 2 - 48), mask=tree_alpha)

    #santa = Image.open(f'santa{1 if color[0] > 125 else 2}.png').convert('RGB')
    #we, he = santa.size
    #santa = santa.resize((we // 20, he // 20))
    #image.paste(santa, (15, img_height // 2 - 30))

    # Сохраняем изображение в поток (BytesIO)
    image_data = io.BytesIO()
    image.save(image_data, format='PNG')  # Сохраняем изображение в поток как PNG
    image_data.seek(0)  # Возвращаем указатель в начало потока

    return image_data


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin1_key = ''
    admin2_key = ''
    with open('keys.txt') as file:
        data = file.read().split()
        admin1_key, admin2_key = data[1], data[3]
    if not context.args:
        a = ''
        if update.message.chat_id in users_data:
            a = '\n\n👉 Вы уже являетесь админом 👈'
        await update.message.reply_text(
            f'Введите код администратора в формате /admin <key>\n\nЧтобы снять с себя админку /admin 0{a}')
    else:
        if context.args[0] == admin1_key:
            user_id = update.message.chat_id
            if user_id not in users_data:
                users_data.append(user_id)
                await update.message.reply_text('Регистрация в качестве администратора выполнена успешно!')
                await update.message.delete()
                log('@' + str(update.message.from_user['username']) + ' зашёл как админ')
                save_users_data()
            else:
                await update.message.reply_text('Вы уже являетесь администратором')
        elif context.args[0] == '0':
            try:
                await update.message.reply_text('Вы больше не получаете анонимные сообщения пользователей')
                log('@' + str(update.message.from_user['username']) + ' больше не админ')
                await update.message.delete()
                users_data.remove(update.message.chat_id)
                try:
                    super_admins.remove(update.message.chat_id)
                except:
                    pass
                save_users_data()
            except ValueError:
                pass
        elif context.args[0] == admin2_key:
            user_id = update.message.chat_id
            if user_id not in users_data:
                users_data.append(user_id)
                super_admins.append(user_id)
                await update.message.reply_text('Регистрация в качестве супер-администратора выполнена успешно!')
                log('@' + str(update.message.from_user['username']) + 'зашёл как супер-админ')
                save_users_data()
                await update.message.delete()
            else:
                await update.message.reply_text('Вы уже являетесь администратором')
        else:
            await update.message.reply_text('Неверный код')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending_messages.append(update.message.chat_id)
    await update.message.reply_text(
        "Отправьте сообщение или фото 👇")


# async def send_message_with_retry(bot, chat_id, text, retries=5):
#     """Отправка сообщения с повторной попыткой при возникновении ошибок."""
#     for attempt in range(retries):
#         try:
#             # Попытка отправки сообщения
#             await bot.send_photo(chat_id=chat_id, photo=ttm.text_to_image(text))
#             log(f"Message sent successfully to {chat_id}")
#             return  # Если сообщение отправлено успешно, выходим из функции
#         except RetryAfter as e:
#             # Ошибка: Telegram просит подождать перед следующим запросом (лимит превышен)
#             log(f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
#             await asyncio.sleep(e.retry_after)  # Ждем указанное количество секунд
#         except (TimedOut, NetworkError) as e:
#             # Ошибка: проблемы с сетью или таймаут
#             log(f"Network error: {e}. Retrying in 5 seconds...")
#             await asyncio.sleep(5)  # Ждем 5 секунд перед повторной попыткой
#         except TelegramError as e:
#             # Другие ошибки Telegram API (например, блокировка пользователя)
#             log(f"Failed to send message to {chat_id}. Error: {e}")
#             break  # Прерываем попытки, так как ошибка непреодолима
#     else:
#         log(f"Failed to send message to {chat_id} after {retries} attempts.")


async def send_photo_with_retry(bot, chat_id, photo_file, caption, color=(0, 0, 0), retries=5, ismes=False):
    """Отправка сообщения с повторной попыткой при возникновении ошибок."""
    for attempt in range(retries):
        try:
            # Попытка отправки сообщения
            if ismes:
                await bot.send_photo(chat_id=chat_id, photo=text_to_image(photo_file, color), caption=caption)
            else:
                await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=caption)
            log(f"Photo sent successfully to {chat_id}")
            return  # Если сообщение отправлено успешно, выходим из функции
        except RetryAfter as e:
            # Ошибка: Telegram просит подождать перед следующим запросом (лимит превышен)
            log(f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)  # Ждем указанное количество секунд
        except (TimedOut, NetworkError) as e:
            # Ошибка: проблемы с сетью или таймаут
            log(f"Network error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)  # Ждем 5 секунд перед повторной попыткой
        except TelegramError as e:
            # Другие ошибки Telegram API (например, блокировка пользователя)
            log(f"Failed to send photo to {chat_id}. Error: {e}")
            break  # Прерываем попытки, так как ошибка непреодолима
    else:
        log(f"Failed to send photo to {chat_id} after {retries} attempts.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.chat_id
    text_to_send, links = links_slice(update.message.text)
    if user_id in pending_messages:
        await update.message.reply_text("✅ Сообщение отправлено ✅")
        colors = (randint(0, 255), randint(0, 255), randint(0, 255))
        for target_user_id in users_data[:]:
            log(f'Trying to send "{update.message.text[0:40]}" from {user_id} to {target_user_id}')
            a = links
            if target_user_id in super_admins:
                a = '\n\nот @' + str(update.message.from_user['username'])

            await send_photo_with_retry(context.bot, color=colors, chat_id=target_user_id,
                                        photo_file=text_to_send,
                                        caption=f"{a}", ismes=True)

        pending_messages.remove(user_id)
    else:
        await update.message.reply_text("Используйте команду /send, чтобы отправить сообщение")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.chat_id
    if user_id in pending_messages:
        await update.message.reply_text("✅ Фото отправлено ✅")

        for target_user_id in users_data[:]:
            log(f'Trying to send photo from "{user_id}" to {target_user_id}')
            photo_file = update.message.photo[-1].file_id
            desc = update.message.caption
            if desc is None:
                desc = ''
            else:
                desc = '\n\n' + desc
            a = ''
            if target_user_id in super_admins:
                a = '\n\nот @' + str(update.message.from_user['username'])

            await send_photo_with_retry(context.bot, chat_id=target_user_id, photo_file=photo_file,
                                        caption=f"{desc}{a}")

        # Удаляем отправителя из списка ожидающих
        pending_messages.remove(user_id)
    else:
        await update.message.reply_text("Используйте команду /send, чтобы отправить фото")


async def helpbot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(help_text)


def main():
    token = "7794871532:AAHRRQNSPrNMF8MLvteouXGpFG1tNsLsh2o"

    load_users_data()

    app = ApplicationBuilder().token(token).build()

    log('App started')

    app.add_handler(CommandHandler(["start", 'send'], start))

    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(CommandHandler("help", helpbot))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.run_polling()


if __name__ == "__main__":
    main()
