import argparse
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime

import aiofiles
from aiofiles.threadpool import AsyncTextIOWrapper
from dotenv import load_dotenv

DATETIME_FORMAT = "%d.%m.%y %H:%M"
RECONNECT_TIME = 5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Подключиться к чату и сохранить историю сообщений",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--host",
        default=os.environ.get("MINECHAT_HOST", "minechat.dvmn.org"),
        help="Адрес сервера чата (можно установить через переменную окружения MINECHAT_HOST)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MINECHAT_PORT", "5000")),
        help="Порт сервера чата (можно установить через переменную окружения MINECHAT_PORT)",
    )

    parser.add_argument(
        "--history",
        default=os.environ.get("MINECHAT_HISTORY", "minechat_history.txt"),
        help="Путь к файлу для сохранения истории (можно установить через MINECHAT_HISTORY)",
    )

    return parser.parse_args()


@asynccontextmanager
async def chat_connection(server: str, port: int):
    try:
        reader, writer = await asyncio.open_connection(host=server, port=port)
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        print(f"[{timestamp}] Соединение установлено.")
        try:
            yield reader, writer
        finally:
            writer.close()
            await writer.wait_closed()
    except ConnectionRefusedError:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        print(f"[{timestamp}] Не удалось подключиться к серверу.")
        raise


async def process_messages(reader: asyncio.StreamReader, file: AsyncTextIOWrapper) -> None:
    async for raw_message in reader:
        try:
            message = raw_message.decode().strip()
            if not message:
                continue

            timestamp = datetime.now().strftime(DATETIME_FORMAT)
            formatted_message = f"[{timestamp}] {message}\n"
            await file.write(formatted_message)

            print(formatted_message, end="")
        except Exception as exc:
            timestamp = datetime.now().strftime(DATETIME_FORMAT)
            print(f"[{timestamp}] Ошибка обработки сообщения: {str(exc)}")


async def main():
    load_dotenv()
    args = parse_args()
    while True:
        try:
            async with aiofiles.open(file=args.history, mode="a", encoding="utf-8") as file:
                async with chat_connection(args.host, args.port) as (reader, writer):
                    await process_messages(reader, file)

        except ConnectionRefusedError:
            await asyncio.sleep(RECONNECT_TIME)
        except ConnectionError:
            timestamp = datetime.now().strftime(DATETIME_FORMAT)
            print(f"[{timestamp}] Соединение разорвано, переподключение...")
        except Exception as exc:
            timestamp = datetime.now().strftime(DATETIME_FORMAT)
            print(f"[{timestamp}] Ошибка: {str(exc)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Работа завершена.")
