import json
import datetime as dt
import asyncio

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, RetryAfter, TimedOut, NetworkError
import os
import cairo
import math
import io

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


def wrap_text(context, text, max_width):
    """Функция для переноса текста на новые строки, если он превышает максимальную ширину."""
    words = text.split()
    lines = []
    current_line = []
    current_width = 0

    for word in words:
        word_extents = context.text_extents(word + ' ')  # Ширина слова с пробелом
        word_width = word_extents.width

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


def text_to_image(text, padding=40, right_padding_ratio=0.15, line_spacing=1.5, font_size=30,
                  font='Franklin Gothic Medium'):
    # Настройки текста
    text_color = (0, 0, 0)  # Черный текст
    background_color = (1, 1, 1)  # Белый фон (формат RGB с плавающей запятой)

    # Создаем временную поверхность для расчета размеров
    temp_surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 1, 1)
    temp_context = cairo.Context(temp_surface)
    temp_context.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    temp_context.set_font_size(font_size)

    # Определяем максимальную ширину строки (например, 600 пикселей) с учетом правого отступа
    max_width = 600
    max_text_width = max_width * (1 - right_padding_ratio)  # Учитываем отступ справа

    # Получаем строки с переносом
    lines = wrap_text(temp_context, text, max_text_width)

    # Рассчитываем высоту и ширину изображения
    line_extents = temp_context.text_extents('X')  # Высота строки
    line_height = line_extents.height
    text_height = line_height * len(lines) * line_spacing  # Высота всего текста с учетом межстрочного интервала

    # Добавляем отступы
    img_width = max_width + 2 * padding
    img_height = math.ceil(text_height + 2 * padding)

    # Создаем реальную поверхность с нужными размерами
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, img_width, img_height)
    context = cairo.Context(surface)

    # Заливаем фон белым цветом
    context.set_source_rgb(*background_color)
    context.paint()

    # Настройки текста
    context.set_source_rgb(*text_color)
    context.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    context.set_font_size(font_size)

    # Рисуем текст по строкам
    y_offset = padding + line_height  # Начинаем рисовать с учетом верхнего отступа

    for line in lines:
        line_extents = context.text_extents(line)
        x_offset = padding  # Слева отступ фиксированный
        context.move_to(x_offset, y_offset)
        context.show_text(line)
        y_offset += line_height * line_spacing  # Смещаем по вертикали с учетом интервала между строками

    # Сохраняем изображение
    image_data = io.BytesIO()
    surface.write_to_png(image_data)  # Сохраняем изображение в поток
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


async def send_photo_with_retry(bot, chat_id, photo_file, caption, retries=5):
    """Отправка сообщения с повторной попыткой при возникновении ошибок."""
    for attempt in range(retries):
        try:
            # Попытка отправки сообщения
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
    if user_id in pending_messages:
        await update.message.reply_text("✅ Сообщение отправлено ✅")
        rendered_photo = text_to_image(update.message.text)
        for target_user_id in users_data[:]:
            log(f'Trying to send "{update.message.text[0:40]}" from {user_id} to {target_user_id}')
            a = ''
            if target_user_id in super_admins:
                a = '\n\nот @' + str(update.message.from_user['username'])

            await send_photo_with_retry(context.bot, chat_id=target_user_id, photo_file=rendered_photo,
                                        caption=f"{a}")

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
