from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.types.chat import ChatActions
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import torch
import neural_style_transfer_model
from config import TOKEN
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types.message import ContentType
import os
import torchvision.transforms as transforms

button_help = KeyboardButton('/help')
button_start = KeyboardButton('/start_transfer')
button_monet = KeyboardButton('/Monet')
button_my_style = KeyboardButton('/my_style')

kb_help_and_start = ReplyKeyboardMarkup(
    resize_keyboard=True, one_time_keyboard=True
).add(button_help).add(button_start)
kb_help = ReplyKeyboardMarkup(
    resize_keyboard=True, one_time_keyboard=True
).add(button_help)
kb_choose_style = ReplyKeyboardMarkup(
    resize_keyboard=True, one_time_keyboard=True
).add(button_my_style).add(button_monet).add(button_help)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


class WaitForPic(StatesGroup):


    waiting_for_start = State()
    waiting_for_type_of_transfer = State()
    waiting_for_content_monet = State()
    waiting_for_content_custom = State()
    waiting_for_style = State()


@dp.message_handler(commands=['start', 'restart'], state="*")
async def process_start_command(message: types.Message):
    await message.reply('Привет! Чтобы начать перенос стиля нажми /start_transfer и пришли мне 2 картинки - оригинал и стиль, '
                        'который ты хочешь на него перенести. '
                        'Если возникнут вопросы, то просто нажми /help.', reply_markup=kb_help_and_start)
    await WaitForPic.waiting_for_start.set()


@dp.message_handler(commands=['help'], state=WaitForPic.waiting_for_start)
async def process_help_command(message: types.Message):
    await message.reply('Чтобы начать процесс переноса стиля нажми /start_transfer и пришли мне 2 картинки.',
                        reply_markup=kb_help_and_start)

@dp.message_handler(commands=['help'], state=WaitForPic.waiting_for_type_of_transfer)
async def get_transfer_type(message: types.Message):
    await message.reply('Выбери тип стиля - свой собственный /my_style или стиль картин Моне /Monet.',
                        reply_markup=kb_choose_style)
    await WaitForPic.waiting_for_type_of_transfer.set()


@dp.message_handler(commands=['help'], state=[WaitForPic.waiting_for_content_monet, WaitForPic.waiting_for_content_custom])
async def process_help_command(message: types.Message):
    await message.reply('Пришли мне картинку, к которой мы будем применять стиль.', reply_markup=kb_help)


@dp.message_handler(commands=['help'], state=WaitForPic.waiting_for_style)
async def process_help_command(message: types.Message):
    await message.reply('Сейчас пришли картинку со стилем, который хочешь применить к картинке выше.')

@dp.message_handler(commands=['start_transfer'], state=WaitForPic.waiting_for_start)
async def get_transfer_type(message: types.Message):
    await message.reply('Выбери тип стиля - свой собственный /my_style или стиль картин Моне /Monet.',
                        reply_markup=kb_choose_style)
    await WaitForPic.waiting_for_type_of_transfer.set()


@dp.message_handler(commands=['Monet'], state=WaitForPic.waiting_for_type_of_transfer)
async def start_transfer_monet(message: types.Message):
    await message.reply('Пришли мне картинку, к которой мы будем применять стиль.', reply_markup=kb_help)
    await WaitForPic.waiting_for_content_monet.set()

@dp.message_handler(commands=['my_style'], state=WaitForPic.waiting_for_type_of_transfer)
async def start_transfer_custom(message: types.Message):
    await message.reply('Пришли мне картинку, к которой мы будем применять стиль.', reply_markup=kb_help)
    await WaitForPic.waiting_for_content_custom.set()

@dp.message_handler(content_types=['photo'], state=WaitForPic.waiting_for_content_monet)
async def monet_transfer(message):
    content_name = 'content_{}.jpg'.format(message.from_user.id)
    await message.photo[0].download(content_name)
    await message.reply('Отлично! Пожалуйста, подожди несколько минут, пока я применяю стили...')
    await bot.send_chat_action(message.from_user.id, ChatActions.UPLOAD_DOCUMENT)
    model = torch.load('monet.pth')
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    img = neural_style_transfer_model.image_loader(content_name, 512, device)
    img = model(img)

    unloader = transforms.ToPILImage()
    file = 'result_{}.jpg'.format(message.from_user.id)
    image = img.cpu().clone()
    image = image.squeeze(0)
    image = unloader(image)
    image.save(file)


    await bot.send_photo(message.from_user.id, open('result_{}.jpg'.format(message.from_user.id), 'rb'),
                         reply_to_message_id=message.message_id, caption='Готово! Чтобы попробовать снова просто нажми'
                                                                         ' /start_transfer.',
                         reply_markup=kb_help_and_start)

    os.remove('content_{}.jpg'.format(message.from_user.id))
    await WaitForPic.waiting_for_start.set()


@dp.message_handler(content_types=['photo'], state=WaitForPic.waiting_for_content_custom)
async def get_content_photo(message):
    content_name = 'content_{}.jpg'.format(message.from_user.id)
    await message.photo[0].download(content_name)
    await message.reply('Сейчас пришли картинку со стилем, который хочешь применить к картинке выше.',
                        reply_markup=kb_help)
    await WaitForPic.waiting_for_style.set()


@dp.message_handler(content_types=['photo'], state=WaitForPic.waiting_for_style)
async def get_content_photo(message):
    style_name = 'style_{}.jpg'.format(message.from_user.id)
    content_name = 'content_{}.jpg'.format(message.from_user.id)
    await message.photo[0].download(style_name)
    await message.reply('Отлично! Пожалуйста, подожди несколько минут, пока я применяю стили...')
    await bot.send_chat_action(message.from_user.id, ChatActions.UPLOAD_DOCUMENT)
    await neural_style_transfer_model.run(content_name, style_name, message.from_user.id)

    await bot.send_photo(message.from_user.id, open('result_{}.jpg'.format(message.from_user.id), 'rb'),
                         reply_to_message_id=message.message_id, caption='Готово! Чтобы попробовать снова просто нажми'
                                                                         ' /start_transfer.',
                         reply_markup=kb_help_and_start)
    await WaitForPic.waiting_for_start.set()
    os.remove('result_{}.jpg'.format(message.from_user.id))
    os.remove('style_{}.jpg'.format(message.from_user.id))
    os.remove('content_{}.jpg'.format(message.from_user.id))


@dp.message_handler(content_types=ContentType.ANY, state="*")
async def unknown_message(msg: types.Message):
    message_text = 'Я не знаю, что мне делать! \nЕсли у тебя есть вопросы нажми кнопку /help ' \
                   'или начни сначала, нажав /restart.'
    await msg.reply(message_text, reply_markup=kb_help)


if __name__ == '__main__':
    executor.start_polling(dp)