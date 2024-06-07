import asyncio
import datetime
import re
import time

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from tokens import (API_TOKEN, HYDRA_LOGIN, HYDRA_PASSWORD, STALKER_LOGIN, STALKER_PASSWORD, BILLING_URL, STALKER_URL,
                    ISP_NAME, USERS, ADMINS)


class User(StatesGroup):
    deltv = State()
    ssv = State()
    action = State()
    mac = State()
    camera = State()
    tv = State()


bot = Bot(token=API_TOKEN)
dp = Dispatcher()

'''
options for linux cli headless mode 
'''


# options = webdriver.ChromeOptions()
# options.add_argument('--disable-gpu')
# options.add_argument('--headless')
# options.add_argument("--disable-dev-shm-usage")
# options.add_argument("--no-sandbox")


def driver_start():
    """
    chrome driver launching func
    """
    s = Service(executable_path='chromedriver-win64/chromedriver.exe')  # /usr/bin/chromedriver for linux cli
    driver = webdriver.Chrome(service=s)  # +options=options if linux cli
    driver.set_window_size(1920, 1080)
    driver.maximize_window()
    return driver


def search_input(input_var, driver):  # billing search func
    driver.find_element(By.CLASS_NAME, 'search-query').clear()
    search_form = driver.find_element(By.CLASS_NAME, 'search-query')
    search_form.send_keys(input_var)
    time.sleep(3)  # sleep to avoid search stacking
    search_form.send_keys(Keys.ARROW_DOWN)
    search_form.send_keys(Keys.ARROW_DOWN)
    driver.find_element(By.XPATH, '//li[contains(@class,"item ui-menu-item focused")]').click()


def driver_hydra(driver):
    driver.get(BILLING_URL)
    login_input = driver.find_element(By.ID, 'user_login')
    login_input.clear()
    login_input.send_keys(HYDRA_LOGIN)
    password_input = driver.find_element(By.ID, 'user_password')
    password_input.clear()
    password_input.send_keys(HYDRA_PASSWORD)
    password_input.send_keys(Keys.ENTER)


def format_mac(mac: str, delim: str) -> str:
    mac = re.sub('[.:-]', '', mac).lower()  # remove delimiters and convert to lower case
    mac = ''.join(mac.split())  # remove whitespaces
    # convert mac in canonical form (eg. 00:80:41:ae:fd:7e)
    mac = delim.join(["%s" % (mac[i:i + 2]) for i in range(0, 12, 2)])
    return mac


async def log_cmd(message, text, user=USERS, bypass=0):
    dtn = datetime.datetime.now()
    botlogfile = open('Bot.log', 'a')  # /var/log/Bot.log for linux cli

    '''
    logging + authorization by whitelist using USERS/ADMINS lists
    '''

    if message.from_user.id in user and bypass == 0:
        print(dtn.strftime("%d-%m-%Y %H:%M"), 'Пользователь ' + message.from_user.first_name,
              'написал следующее: ', text, file=botlogfile)
        botlogfile.close()
        return 0
    elif bypass == 1 or message.from_user.id not in user:
        print(dtn.strftime("%d-%m-%Y %H:%M"), 'Неавторизованное сообщение от Пользователя ' +
              message.from_user.first_name + " ID:", message.from_user.id, 'написал следующее: ',
              text, file=botlogfile)
        botlogfile.close()
        return 1


@dp.message(Command(commands=["log"]))
async def loglast20(message: types.Message):
    if await log_cmd(message=message, text=message.text, user=ADMINS) == 0:
        botlogfile = open('Bot.log', 'r')  # /var/log/Bot.log
        for line in (botlogfile.readlines()[-15:]):
            await bot.send_message(message.from_user.id, line)
        botlogfile.close()
    else:
        return


@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    await message.reply(f"Я {ISP_NAME} Бот! \nЧтобы посмотреть список комманд введи /faq")


@dp.message(StateFilter(None), Command(commands=["user"]))
async def command_start(message: types.Message, state: FSMContext) -> None:
    await state.set_state(User.ssv)
    await message.answer(
        "\nВведите ssv абонента чтобы начать",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(User.ssv)
async def process_ssv(message: types.Message, state: FSMContext) -> None:
    text = f'Выбран ssv{message.text}'
    if await log_cmd(message=message, text=text) == 0 and len(message.text) == 5 and message.text.isdigit():
        pass
    else:
        await bot.send_message(message.from_user.id, 'Неверный ssv, введите номер абонента без букв (прим. 12345)')
        await state.set_state(User.ssv)
        return

    await state.update_data(ssv='ssv' + message.text.lower())
    user_data = await state.get_data()
    await state.set_state(User.action)
    driver = driver_start()
    driver_hydra(driver)
    search_input(user_data['ssv'], driver)
    address = 'Не определен'
    ip = 'Не определен'
    balance = 'Не определен'
    service = 'Услуги не определены'
    try:
        address = driver.find_element(By.XPATH,
                                      '//tr//tr//tr[@class="" and contains(.,"Обычный адрес (основной)")]//td['
                                      'contains(.,"кв.")]').text
        ip = driver.find_element(By.XPATH,
                                 '//tr//tr//tr[@class="" and contains(.,"IP-адрес (основной)")]//td[contains(.,'
                                 '"10.2")][1]').text
        driver.find_element(By.XPATH, '//span[contains(@id,"_n_owner_id_edit_")]').click()
        time.sleep(4)
        driver.switch_to.window(driver.window_handles.pop())
        balance = driver.find_element(By.XPATH, '//td[contains(@class,"align_right")][1]').text
        service = driver.find_element(By.XPATH, '//i[contains(@class,"icon-large")][1]').get_attribute('data-original'
                                                                                                       '-title')
    except Exception as ex:
        await bot.send_message(message.from_user.id, f'{ex}')
    mark = '\u2705' if 'Услуга' in service else '\u274C'
    await message.answer(
        f"Выбран абонент с ssv{message.text}!\n"
        f"Адрес: {address}\n"
        f"Баланс: {balance}руб\n"
        f"IP-адрес: {ip}\n"
        f"{mark}{service}\n"
        f"Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="МАК"),
                    KeyboardButton(text="ТВ"),
                    KeyboardButton(text="Камеры"),
                    KeyboardButton(text="Удалить"),
                    KeyboardButton(text="Завершить")
                ]
            ],
            resize_keyboard=True,
        ),
    )


@dp.message(Command(commands=["faq"]))
async def faq(message: types.Message):
    if await log_cmd(message=message, text=message.text) == 0:
        pass
    else:
        return
    await message.reply("Чтобы добавить мак введи " \
                        "\n/add mac ssv00000 00:00:00:00:00:00" \
                        "\nЧтобы дернуть ТВ введи " \
                        "\n/add tv ssv00000" \
                        "\nЧтобы добавить камеры введи" \
                        "\n/add camera ssv00000 16А-67 (в адресе русские буквы)" \
                        "\n/deltv 00:00:00:00:00:00 Если нет видеоклуба")


'''
command to add mac/tv plan/cameras to the account by ssv number
'''


@dp.message(User.action, F.text.casefold() == "мак")
async def action_mac(message: types.Message, state: FSMContext):
    await state.set_state(User.mac)
    user_data = await state.get_data()
    await bot.send_message(message.from_user.id, f"Введите мак, который надо добавить к {user_data['ssv']}")


@dp.message(User.mac)
async def add_router_mac(message: types.Message, state: FSMContext):
    user_data = await state.update_data(router_mac=format_mac(message.text, delim=':'))
    text = f"К {user_data['ssv']} добавляю мак роутера {user_data['router_mac']}"
    await state.set_state(User.action)
    if await log_cmd(message=message, text=text) == 0:
        pass
    else:
        return
    try:
        driver = driver_start()
        driver_hydra(driver)
        try:
            search_input(user_data['router_mac'], driver)
            mac = format_mac(user_data['router_mac'], delim='-')
            script = (f"document.evaluate('//tr//tr//tr[contains(.,\"{mac}\")]//a[contains(@class,"
                      f"\"icon-remove\")]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, "
                      f"null).singleNodeValue.click();")
            time.sleep(2)
            driver.execute_script(script)
            driver.switch_to.alert.accept()
            driver.switch_to.default_content()
            await bot.send_message(message.from_user.id, f"Был найден дубль мака. Перезагрузи роутер и проверь")
        except:
            pass
        driver.refresh()
        search_input(user_data['ssv'], driver)
        temp_mac = format_mac(user_data['router_mac'], delim=":")
        entry = driver.current_url.rsplit('/', 1)[-1]
        driver.find_element(By.CLASS_NAME, 'add_link').click()
        time.sleep(1)  # sleep to avoid stacking
        driver.find_element(By.XPATH, f'//button[(@id="account_types_{entry}")]').click()
        driver.find_element(By.XPATH, '//ul//li[contains(.,"MAC-адрес")]').click()
        time.sleep(1)  # sleep to avoid stacking
        mac_input = driver.find_element(By.NAME, 'obj_address[vc_code]')
        mac_input.send_keys(temp_mac)
        driver.find_element(By.XPATH, '//input[@value="Добавить"]').click()
        time.sleep(1)
        await bot.send_message(message.from_user.id, "Мак успешно добавлен!")
    except Exception as ex:
        await bot.send_message(message.from_user.id, f"Возникла ошибка: \n{ex}")
    finally:
        driver.close()
        driver.quit()


@dp.message(User.action, F.text.casefold() == "тв")
async def add_tv(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    await state.set_state(User.action)
    text = f'Добавляю ТВ к {user_data["ssv"]}'
    if await log_cmd(message=message, text=text) == 0:
        pass
    else:
        return
    driver = driver_start()
    driver_hydra(driver)
    tv = "IPTV Расширенный XL"  # stating default TV plan
    try:
        search_input(user_data['ssv'], driver)
        try:
            tv = driver.find_element(By.XPATH, '//button[contains(.,"—")]')
            tv = "—"
        except:
            pass
        try:
            tv = driver.find_element(By.XPATH, '//button[contains(.,"IPTV Социальный")]')
            tv = "IPTV Социальный"
        except:
            pass
        if tv == "—":
            driver.find_element(By.XPATH, '//button[contains(.,"—")]').click()
            driver.find_element(By.XPATH, '//ul//li[contains(.,"IPTV Расширенный XL")]').click()
            driver.find_element(By.XPATH, '//input[@value="Сохранить"]').click()
        else:
            time.sleep(2)
            driver.find_element(By.XPATH, f'//button[contains(.,"{tv}")]').click()
            driver.find_element(By.XPATH,
                                '//ul[contains(@style,"display: block")]//li[contains(.,"—")]').click()
            driver.find_element(By.XPATH, '//input[@value="Сохранить"]').click()
            time.sleep(2)
            driver.find_element(By.XPATH, '//a[contains(@class,"icon-plus")]').click()
            driver.find_element(By.XPATH, '//div[contains(@id,"field_undefined")]//button[contains(@class,'
                                          '"btn dropdown-toggle clearfix")]').click()
            driver.find_element(By.XPATH,
                                f'//ul[contains(@style,"display: block")]//li[contains(.,"{tv}")]').click()
            driver.find_element(By.XPATH, '//input[@value="Сохранить"]').click()
        await bot.send_message(message.from_user.id, "ТВ успешно добавлено!")
    except Exception as ex:
        await bot.send_message(message.from_user.id, f"Возникла ошибка: \n{ex}")
    finally:
        driver.close()
        driver.quit()


@dp.message(User.action, F.text.casefold() == "камеры")
async def action_mac(message: types.Message, state: FSMContext):
    await state.set_state(User.camera)
    await bot.send_message(message.from_user.id, f"Введите адрес по которому надо добавить камеры")


@dp.message(User.camera)
async def ssv_camera(message: types.Message, state: FSMContext):
    user_data = await state.update_data(cam_address=message.text)
    await state.set_state(User.action)
    text = f'Добавляю камеры {user_data["cam_address"]} к {user_data["ssv"]}'
    if await log_cmd(message=message, text=text) == 0:
        pass
    else:
        return
    driver = driver_start()
    driver_hydra(driver)
    try:
        search_input(user_data['ssv'], driver)
        driver.find_element(By.XPATH, '//a[contains(@class,"icon-plus")]').click()
        driver.find_element(By.XPATH, '//div[contains(@id,"field_undefined")]//button[contains(@class,'
                                      '"btn dropdown-toggle clearfix")]').click()
        driver.find_element(By.XPATH,
                            f'//ul[contains(@style,"display: block")]//li[contains(.,"{message.text}")]').click()
        driver.find_element(By.XPATH, '//input[@value="Сохранить"]').click()
        await bot.send_message(message.from_user.id, f"Камеры {user_data['cam_address']} успешно добавлены!")
    except Exception as ex:
        await bot.send_message(message.from_user.id, f"Возникла ошибка: \n{ex}")
    finally:
        driver.close()
        driver.quit()


'''
command to delete used TV stations by mac address
'''


@dp.message(User.action, F.text.casefold() == "удалить")
async def action_mac(message: types.Message, state: FSMContext):
    await state.set_state(User.deltv)
    await bot.send_message(message.from_user.id, f"Введите мак-адрес приставки которую нужно удалить")


@dp.message(User.deltv)
async def add(message: types.Message, state: FSMContext):
    user_data = await state.update_data(tv_mac=format_mac(message.text, delim=':'))
    text = f'Удаляем мак приставки {message.text}'
    await state.set_state(User.action)
    if await log_cmd(message=message, text=text) == 0:
        pass
    else:
        return
    driver = driver_start()
    driver.get(STALKER_URL)
    login_input = driver.find_element(By.NAME, 'login')
    login_input.send_keys(STALKER_LOGIN)
    password_input = driver.find_element(By.NAME, 'password')
    password_input.send_keys(STALKER_PASSWORD)
    password_input.send_keys(Keys.ENTER)
    search = driver.find_element(By.NAME, 'search')
    search.send_keys(user_data['tv_mac'])
    search.send_keys(Keys.ENTER)
    driver.find_element(By.XPATH, '//a[contains(.,"del")]').click()
    driver.switch_to.alert.accept()
    await bot.send_message(message.from_user.id, 'Теперь перезагрузи приставку и сделай /add tv')
    driver.close()
    driver.quit()


@dp.message(User.action, F.text.casefold() == "завершить")
async def action_mac(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    await state.clear()
    await state.set_data({})
    await message.answer(
        text=f"Работа с {user_data['ssv']} окончена",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message()
async def message_logging(message: types.Message):
    text = message.text
    await log_cmd(message=message, text=text,
                  bypass=1)  # logging all uncaught messages defined as unauthorized with bypass argument


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
