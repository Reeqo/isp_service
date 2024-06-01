import asyncio
import datetime
import re
import time

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject, CommandStart
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from tokens import (API_TOKEN, HYDRA_LOGIN, HYDRA_PASSWORD, STALKER_LOGIN, STALKER_PASSWORD, BILLING_URL, STALKER_URL,
                    ISP_NAME, USERS, ADMINS)

API_TOKEN = API_TOKEN

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


def search_input(input_var, driver):  # billing search func
    driver.find_element(By.CLASS_NAME, 'search-query').clear()
    search_form = driver.find_element(By.CLASS_NAME, 'search-query')
    search_form.send_keys(input_var)
    time.sleep(3)  # sleep to avoid search stacking
    search_form.send_keys(Keys.ARROW_DOWN)
    search_form.send_keys(Keys.ARROW_DOWN)
    driver.find_element(By.XPATH, '//li[contains(@class,"item ui-menu-item focused")]').click()


def driver_start():
    """
    chrome driver launching func
    """
    s = Service(executable_path='chromedriver-win64/chromedriver.exe')  # /usr/bin/chromedriver for linux cli
    driver = webdriver.Chrome(service=s)  # +options=options if linux cli
    driver.set_window_size(1920, 1080)
    driver.maximize_window()
    return driver


def format_mac(mac: str, delim: str) -> str:
    mac = re.sub('[.:-]', '', mac).lower()  # remove delimiters and convert to lower case
    mac = ''.join(mac.split())  # remove whitespaces
    assert len(mac) == 12  # length should be now exactly 12 (eg. 008041aefd7e)
    assert mac.isalnum()  # should only contain letters and numbers
    # convert mac in canonical form (eg. 00:80:41:ae:fd:7e)
    mac = delim.join(["%s" % (mac[i:i + 2]) for i in range(0, 12, 2)])
    return mac


async def log_cmd(message, user=USERS, bypass=0):
    dtn = datetime.datetime.now()
    botlogfile = open('Bot.log', 'a')  # /var/log/Bot.log for linux cli

    '''
    logging + authorization by whitelist using USERS/ADMINS lists
    '''

    if message.from_user.id in user and bypass == 0:
        print(dtn.strftime("%d-%m-%Y %H:%M"), 'Пользователь ' + message.from_user.first_name,
              'написал следующее: ' + message.text, file=botlogfile)
        botlogfile.close()
        return 0
    elif bypass == 1 or message.from_user.id not in user:
        print(dtn.strftime("%d-%m-%Y %H:%M"), 'Неавторизованное сообщение от Пользователя ' +
              message.from_user.first_name + " ID:", message.from_user.id, 'написал следующее: ' +
              message.text, file=botlogfile)
        botlogfile.close()
        return 1


@dp.message(Command(commands=["log"]))
async def loglast20(message: types.Message):
    if await log_cmd(message, ADMINS) == 0:
        botlogfile = open('Bot.log', 'r')  # /var/log/Bot.log
        for line in (botlogfile.readlines()[-15:]):
            await bot.send_message(message.from_user.id, line)
        botlogfile.close()
    else:
        return


@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    await message.reply(f"Я {ISP_NAME} Бот! \nЧтобы посмотреть список комманд введи /faq")


@dp.message(Command(commands=["faq"]))
async def faq(message: types.Message):
    if await log_cmd(message) == 0:
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


@dp.message(Command(commands=["add"]))
async def add_service(message: types.Message, command=CommandObject):
    if await log_cmd(message) == 0:
        pass
    else:
        return
    tv = "IPTV Расширенный XL"  # stating default TV plan

    if command.args is None:
        print("Аргументов нет")
        await bot.send_message(message.from_user.id, "Ошибка: не введен MAC или SSV\n" \
                                                     "Введите команду в формате \n/add mac ssv00000 00:00:00:00:00:00" \
                                                     "\nИли \n/add tv ssv00000")

    else:
        input_list = command.args.split(" ")  # 0 - mac/tv/camera, 1 - ssv, 2 - mac/camera address if applicable
        try:
            driver = driver_start()
            driver.get(BILLING_URL)
            login_input = driver.find_element(By.ID, 'user_login')
            login_input.clear()
            login_input.send_keys(HYDRA_LOGIN)
            password_input = driver.find_element(By.ID, 'user_password')
            password_input.clear()
            password_input.send_keys(HYDRA_PASSWORD)
            password_input.send_keys(Keys.ENTER)
            if input_list[0] in ["mac", "mak", "мак", "мас"]:
                try:
                    search_input(format_mac(input_list[2], delim=":"), driver)
                    mac = format_mac(input_list[2], delim="-").upper()
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
                search_input(input_list[1], driver)
                mac = format_mac(input_list[2], delim=":")
                entry = driver.current_url.rsplit('/', 1)[-1]
                driver.find_element(By.CLASS_NAME, 'add_link').click()
                time.sleep(1)  # sleep to avoid stacking
                driver.find_element(By.XPATH, f'//button[(@id="account_types_{entry}")]').click()
                driver.find_element(By.XPATH, '//ul//li[contains(.,"MAC-адрес")]').click()
                time.sleep(1)  # sleep to avoid stacking
                mac_input = driver.find_element(By.NAME, 'obj_address[vc_code]')
                mac_input.send_keys(mac)
                driver.find_element(By.XPATH, '//input[@value="Добавить"]').click()
                time.sleep(1)
                await bot.send_message(message.from_user.id, "Мак успешно добавлен!")
            elif input_list[0] in ['tv', 'tb', 'тв']:
                search_input(input_list[1], driver)
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
                try:
                    tv = driver.find_element(By.XPATH, '//button[contains(.,"IPTV Расширенный XL")]')
                    tv = "IPTV Расширенный XL"
                except:
                    pass
                if tv == "—":
                    driver.find_element(By.XPATH, '//button[contains(.,"—")]').click()
                    driver.find_element(By.XPATH, '//ul//li[contains(.,"IPTV Расширенный XL")]').click()
                    driver.find_element(By.XPATH, '//input[@value="Сохранить"]').click()
                else:
                    time.sleep(2)
                    driver.find_element(By.XPATH, '//a[contains(@class,"icon-plus")]').click()
                    driver.find_element(By.XPATH, '//div[contains(@id,"field_undefined")]//button[contains(@class,'
                                                  '"btn dropdown-toggle clearfix")]').click()
                    driver.find_element(By.XPATH,
                                        f'//ul[contains(@style,"display: block")]//li[contains(.,"{tv}")]').click()
                    driver.find_element(By.XPATH, '//input[@value="Сохранить"]').click()
                await bot.send_message(message.from_user.id, "ТВ успешно добавлено!")
            elif input_list[0] == "camera":
                search_input(input_list[1], driver)
                driver.find_element(By.XPATH, '//a[contains(@class,"icon-plus")]').click()
                driver.find_element(By.XPATH, '//div[contains(@id,"field_undefined")]//button[contains(@class,'
                                              '"btn dropdown-toggle clearfix")]').click()
                driver.find_element(By.XPATH,
                                    f'//ul[contains(@style,"display: block")]//li[contains(.,"{input_list[2]}")]').click()
                driver.find_element(By.XPATH, '//input[@value="Сохранить"]').click()
                await bot.send_message(message.from_user.id, "Камеры успешно добавлены!")

        except Exception as ex:
            await bot.send_message(message.from_user.id, f"Возникла ошибка: \n{ex}")
        finally:
            driver.close()
            driver.quit()


'''
command to delete used TV stations by mac address
'''


@dp.message(Command(commands=["deltv"]))
async def add(message: types.Message, command=CommandObject):
    if await log_cmd(message) == 0:
        pass
    else:
        return
    input_list = command.args.split(" ")  # 0 - mac
    driver = driver_start()
    driver.get(STALKER_URL)
    login_input = driver.find_element(By.NAME, 'login')
    login_input.send_keys(STALKER_LOGIN)
    password_input = driver.find_element(By.NAME, 'password')
    password_input.send_keys(STALKER_PASSWORD)
    password_input.send_keys(Keys.ENTER)
    search = driver.find_element(By.NAME, 'search')
    search.send_keys(format_mac(input_list[0], delim=':'))
    search.send_keys(Keys.ENTER)
    driver.find_element(By.XPATH, '//a[contains(.,"del")]').click()
    driver.switch_to.alert.accept()
    await bot.send_message(message.from_user.id, 'Теперь перезагрузи приставку и сделай /add tv')
    driver.close()
    driver.quit()


@dp.message()
async def message_logging(message: types.Message):
    await log_cmd(message, bypass=1)  # logging all uncaught messages defined as unauthorized with bypass argument


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
