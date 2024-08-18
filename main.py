import asyncio
import os
import sys
import httpx
import random
import time
import uuid
from loguru import logger
from datetime import datetime, timedelta
import traceback

# Disable logging for httpx
httpx_log = logger.bind(name="httpx").level("WARNING")
logger.remove()
logger.add(sink=sys.stdout, format="<white>{time:YYYY-MM-DD HH:mm:ss}</white>"
                                   " | <level>{level: <8}</level>"
                                   " | <cyan><b>{line}</b></cyan>"
                                   " - <white><b>{message}</b></white>")
logger = logger.opt(colors=True)

games = {
    1: {
        'name': 'Riding Extreme 3D',
        'appToken': 'd28721be-fd2d-4b45-869e-9f253b554e50',
        'promoId': '43e35910-c168-4634-ad4f-52fd764a843f',
    },
    2: {
        'name': 'Chain Cube 2048',
        'appToken': 'd1690a07-3780-4068-810f-9b5bbf2931b2',
        'promoId': 'b4170868-cef0-424f-8eb9-be0622e8e8e3',
    },
    3: {
        'name': 'My Clone Army',
        'appToken': '74ee0b5b-775e-4bee-974f-63e7f4d5bacb',
        'promoId': 'fe693b26-b342-4159-8808-15e3ff7f8767',
    },
    4: {
        'name': 'Train Miner',
        'appToken': '82647f43-3f87-402d-88dd-09a90025313f',
        'promoId': 'c4480ac7-e178-4973-8061-9ed5b2e17954',
    },
    5: {
        'name': 'Merge Away',
        'appToken': '8d1cc2ad-e097-4b86-90ef-7a27e19fb833',
        'promoId': 'dc128d28-c45b-411c-98ff-ac7726fbaea4',
        'timing': 20000 / 1000,
        'attempts': 25,
    },
    6: {
        'name': 'Twerk Race 3D',
        'appToken': '61308365-9d16-4040-8bb0-2f4a4c69074c',
        'promoId': '61308365-9d16-4040-8bb0-2f4a4c69074c',
        'timing': 20000 / 1000,
        'attempts': 20,
    }
}

EVENTS_DELAY = 20000 / 1000  # converting milliseconds to seconds

async def load_proxies(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                proxies = [line.strip() for line in file if line.strip()]
                return proxies
        else:
            logger.info(f"Proxy file {file_path} not found. No proxies will be used.")
            return []
    except Exception as e:
        logger.error(f"Error reading proxy file {file_path}: {e}")
        return []

async def generate_client_id():
    timestamp = int(time.time() * 1000)
    random_numbers = ''.join(str(random.randint(0, 9)) for _ in range(19))
    return f"{timestamp}-{random_numbers}"

async def login(client_id, app_token, proxy=None):
    async with httpx.AsyncClient(proxies=proxy) as client:
        response = await client.post(
            'https://api.gamepromo.io/promo/login-client',
            json={'appToken': app_token, 'clientId': client_id, 'clientOrigin': 'deviceid'}
        )
        response.raise_for_status()
        data = response.json()
        return data['clientToken']

async def emulate_progress(client_token, promo_id, proxy=None):
    async with httpx.AsyncClient(proxies=proxy) as client:
        response = await client.post(
            'https://api.gamepromo.io/promo/register-event',
            headers={'Authorization': f'Bearer {client_token}'},
            json={'promoId': promo_id, 'eventId': str(uuid.uuid4()), 'eventOrigin': 'undefined'}
        )
        response.raise_for_status()
        data = response.json()
        return data['hasCode']

async def generate_key(client_token, promo_id, proxy=None):
    async with httpx.AsyncClient(proxies=proxy) as client:
        response = await client.post(
            'https://api.gamepromo.io/promo/create-code',
            headers={'Authorization': f'Bearer {client_token}'},
            json={'promoId': promo_id}
        )
        response.raise_for_status()
        data = response.json()
        return data['promoCode']

async def generate_key_process(app_token, promo_id, proxies):
    client_id = await generate_client_id()
    proxy = random.choice(proxies) if proxies else None
    try:
        client_token = await login(client_id, app_token, proxy)
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to login: {e.response.json()}")
        return None

    for _ in range(11):
        await asyncio.sleep(EVENTS_DELAY * (random.random() / 3 + 1))
        proxy = random.choice(proxies) if proxies else None
        try:
            has_code = await emulate_progress(client_token, promo_id, proxy)
        except httpx.HTTPStatusError as e:
            continue

        if has_code:
            break

    proxy = random.choice(proxies) if proxies else None
    try:
        key = await generate_key(client_token, promo_id, proxy)
        return key
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to generate key: {e.response.json()}")
        return None

async def generate_keys_for_game(game, key_count, proxies):
    tasks = [generate_key_process(game['appToken'], game['promoId'], proxies) for _ in range(key_count)]
    keys = await asyncio.gather(*tasks)
    valid_keys = [key for key in keys if key]
    
    if valid_keys:
        logger.success(f"Generated {len(valid_keys)} key(s) for {game['name']}")
        with open('keys.txt', 'a') as file:
            for key in valid_keys:
                formatted_key = f"{key}"
                logger.success(formatted_key)
                file.write(f"{formatted_key}\n")
    else:
        logger.warning(f"No keys were generated for {game['name']} in this iteration.")

async def main(key_count, proxies):
    while True:
        try:
            for game_number, game in games.items():
                logger.info(f"Generating keys for {game['name']}")
                try:
                    await generate_keys_for_game(game, key_count, proxies)
                except Exception as game_error:
                    logger.error(f"Error generating keys for {game['name']}: {str(game_error)}")
                    logger.error(f"Error type: {type(game_error).__name__}")
                    logger.error(f"Error details: {game_error.args}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    continue  # Move to the next game even if there's an error
            
            next_run = datetime.now() + timedelta(minutes=4)
            logger.info(f"Completed a full cycle. Waiting for 4 minutes. Next cycle starts at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            await asyncio.sleep(360)  # 4 minutes delay
        except Exception as e:
            logger.error(f"An error occurred in main loop: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {e.args}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await asyncio.sleep(360)  # Wait 4 minutes before retrying if an error occurs

if __name__ == "__main__":
    key_count = int(input("Enter the number of keys to generate per game per cycle: "))
    proxy_file = input("Enter the proxy file path (leave empty to use 'proxy.txt'): ") or 'proxy.txt'

    proxies = asyncio.run(load_proxies(proxy_file))

    logger.info(f"Starting continuous key generation for all games using proxies from {proxy_file if proxies else 'no proxies'}")
    logger.info(f"Will attempt to generate {key_count} key(s) for each game every cycle")

    try:
        asyncio.run(main(key_count, proxies))
    except KeyboardInterrupt:
        logger.info("Program stopped by user. Exiting...")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {e.args}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        logger.info("Program ended. Check keys.txt for generated keys.")