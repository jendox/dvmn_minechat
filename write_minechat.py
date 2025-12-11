import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from listen_minechat import chat_connection

logger = logging.getLogger("sender")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Отправка сообщений в чат minechat",
        epilog="""
            Примеры использования:
            1. python %(prog)s --message "Привет" --nickname MyNick
            2. python %(prog)s --message "Привет" --token ваш-токен
            3. export MINECHAT_TOKEN=ваш-токен; python %(prog)s --message "Привет"
            """,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--message",
        "-m",
        required=True,
        help="Текст сообщения для отправки (обязательный аргумент)",
    )

    parser.add_argument(
        "--host",
        default=os.environ.get("MINECHAT_HOST", "minechat.dvmn.org"),
        help="Адрес сервера чата (можно установить через переменную окружения MINECHAT_HOST)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MINECHAT_WRITE_PORT", "5050")),
        help="Порт сервера чата (можно установить через MINECHAT_WRITE_PORT)",
    )

    auth_group = parser.add_mutually_exclusive_group()

    auth_group.add_argument(
        "--token",
        default=os.environ.get("MINECHAT_TOKEN"),
        help="Токен для авторизации (можно установить через MINECHAT_TOKEN)",
    )

    auth_group.add_argument(
        "--nickname",
        default=os.environ.get("MINECHAT_NICKNAME"),
        help="Никнейм для регистрации нового пользователя (можно установить через MINECHAT_NICKNAME)",
    )

    parser.add_argument(
        "--credentials",
        default=os.environ.get("MINECHAT_CREDENTIALS", "credentials.json"),
        help="Путь к файлу для сохранения учетных данных",
    )

    return parser.parse_args()


def read_token_from_file(filepath: str) -> str | None:
    try:
        filepath = Path(filepath)
        if not filepath.exists():
            logger.debug(f"Файл учетных данных не найден: {filepath}")
            return None

        with open(filepath, encoding="utf-8") as file:
            credentials_data = json.load(file)
        return credentials_data["account_hash"]

    except (json.JSONDecodeError, KeyError, OSError) as error:
        logger.warning(f"Ошибка чтения учетных данных: {str(error)}")
        return None


def save_credentials(credentials: dict[str, str], filepath: str) -> None:
    try:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(credentials, file, indent=2, ensure_ascii=False)
        logger.info(f"Учетные данные сохранены в {filepath}")
    except OSError as error:
        logger.error(f"Ошибка сохранения учетных данные: {str(error)}")


async def register(host: str, port: int, nickname: str, filepath: str) -> str | None:
    async with chat_connection(host, port) as (reader, writer):
        logger.info(f"Регистрация нового пользователя: {nickname}")
        try:
            # Читаем приветствие
            message = await reader.read(1024)
            logger.debug(message.decode(errors="ignore").strip())
            # Отправляем пустую строку для начала регистрации
            writer.write(b"\n")
            await writer.drain()
            # Запрос ника
            message = await reader.read(1024)
            logger.debug(message.decode(errors="ignore").strip())
            await submit_message(writer, nickname)
            # Ответ с токеном
            message = await reader.read(1024)
            message = message.decode(errors="ignore").strip()
            logger.debug(message)
            credentials = json.loads(message.split("\n", 1)[0])
            token = credentials.get("account_hash")
            if not token:
                raise ValueError("Не найден токен в ответе сервера")

            save_credentials(credentials, filepath)
            return token
        except Exception as exc:
            logger.error(f"Ошибка регистрации пользователя: {exc}")
            return None


async def authorize(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    token: str,
) -> None:
    try:
        # Читаем приветствие
        message = await reader.read(1024)
        logger.debug(message.decode(errors="ignore").strip())
        # Отправляем хэш
        await submit_message(writer, token)
        # Читаем "Добро пожаловать"
        message = await reader.read(1024)
        message = message.decode(errors="ignore").strip()
        logger.debug(message)
        credentials = json.loads(message.split("\n", 1)[0])
        if credentials is None:
            raise ValueError("Неизвестный токен. Проверьте его или зарегистрируйте заново.")

    except Exception as exc:
        logger.error(f"Ошибка авторизации: {str(exc)}")
        raise


async def submit_message(writer: asyncio.StreamWriter, message: str) -> None:
    logger.debug(message)
    clean_message = message.strip().replace("\n", " ")
    writer.write(f"{clean_message}\n\n".encode())
    await writer.drain()
    await asyncio.sleep(0.2)


async def get_token(args: argparse.Namespace) -> str | None:
    token = args.token or read_token_from_file(args.credentials)
    if not token and args.nickname:
        token = await register(args.host, args.port, args.nickname, args.credentials)

    if not token:
        message = "Не удалось зарегистрировать пользователя." \
            if args.nickname else "Для регистрации пользователя нужно указать никнейм."
        logger.error(message)

    return token


async def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    load_dotenv()
    args = parse_args()

    token = await get_token(args)
    if not token:
        return

    async with chat_connection(args.host, args.port) as (reader, writer):
        try:
            await authorize(reader, writer, token)
            await submit_message(writer, args.message)
        except Exception:
            logger.error("Не удалось отправить сообщение.")


if __name__ == "__main__":
    asyncio.run(main())
