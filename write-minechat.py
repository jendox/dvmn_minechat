import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

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


def get_token(filepath: str) -> str | None:
    try:
        filepath = Path(filepath)
        if not filepath.exists():
            logger.debug(f"Файл учетных данных не найден: {filepath}")
            return None

        with open(filepath, encoding="utf-8") as file:
            credentials_data = json.load(file)
        return credentials_data["account_hash"]

    except (json.JSONDecodeError, KeyError, IOError) as error:
        logger.warning(f"Ошибка чтения учетных данных: {str(error)}")
        return None


def save_credentials(credentials: dict[str, str], filepath: str) -> None:
    try:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(credentials, file, indent=2, ensure_ascii=False)
        logger.info(f"Учетные данные сохранены в {filepath}")
    except IOError as error:
        logger.error(f"Ошибка сохранения учетных данные: {str(error)}")


async def register(host: str, port: int, nickname: str, filepath: str) -> tuple[str, str] | None:
    try:
        logger.info(f"Регистрация нового пользователя: {nickname}")
        reader, writer = await asyncio.open_connection(host, port)
        # Читаем приветствие
        message = await reader.read(1024)
        logger.debug(message.decode(errors="ignore").strip())
        # Отправляем пустую строку для начала регистрации
        await submit_message(writer)
        # Запрос ника
        message = await reader.read(1024)
        logger.debug(message.decode(errors="ignore").strip())
        await submit_message(writer, nickname)
        # Ответ с токеном
        message = await reader.read(1024)
        message = message.decode(errors="ignore").strip()
        logger.debug(message)
        credentials = json.loads(message.split("\n", 1)[0])
        nickname = credentials.get("nickname", nickname)
        token = credentials.get("account_hash")
        if not token:
            logger.info(f"Не найден токен в ответе сервера")
            return None

        save_credentials(credentials, filepath)
        writer.close()
        await writer.wait_closed()
        return nickname, token
    except Exception as exc:
        logger.error(f"Ошибка регистрации: {exc}")
        return None


async def authorize(host: str, port: int, token: str) -> asyncio.StreamWriter | None:
    try:
        reader, writer = await asyncio.open_connection(host, port)
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
            logger.error("Неизвестный токен. Проверьте его или зарегистрируйте заново.")
            writer.close()
            await writer.wait_closed()
            return None
        return writer
    except Exception as exc:
        logger.error(f"Ошибка авторизации: {str(exc)}")


async def submit_message(writer: asyncio.StreamWriter, message: str = "") -> None:
    logger.debug(message)
    clean_message = message.strip().replace("\n", " ")
    writer.write(f"{clean_message}\n\n".encode())
    await writer.drain()


async def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    load_dotenv()
    args = parse_args()

    token = args.token
    if not token:
        token = get_token(args.credentials)

    if not token and args.nickname:
        result = await register(args.host, args.port, args.nickname, args.credentials)
        if not result:
            logger.error("Не удалось зарегистрировать пользователя.")
            return
        nickname, token = result
    elif not token:
        logger.error("Не указаны токен и никнейм.")
        return

    writer = await authorize(args.host, args.port, token)
    if not writer:
        logger.error("Не удалось авторизоваться.")
        return
    try:
        await submit_message(writer, args.message)
    except Exception:
        logger.error("Не удалось отправить сообщение.")
    finally:
        if writer and not writer.is_closing():
            writer.close()
            await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
