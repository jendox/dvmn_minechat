# MineChat Listener

Асинхронный клиент для подключения к чату minechat, сохранения истории сообщений и вывода в реальном времени.

---

## Требования

- Python **>= 3.13**

---

## Установка

#### Установите uv (если еще не установлен)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Клонируйте репозиторий

```bash
git clone https://github.com/jendox/dvmn_minechat.git  
cd dvmn_minechat
```

#### Установите зависимости

```bash
uv sync
```

## Использование

### Базовое

```bash
uv run python listen-minechat.py
```

### С указанием параметров

```bash
python listen-minechat.py \
  --host minechat.dvmn.org \
  --port 5000 \
  --history ./minechat_history.txt
```

### Можно задать параметры через переменные окружения

В корне проекта создайте файл `.env`:

```bash
touch .env
```

Добавьте переменные окружения:

```env
MINECHAT_HOST=minechat.dvmn.org
MINECHAT_PORT=5000
MINECHAT_HISTORY=~/minechat.history
```

### Завершение работы

Для завершения работы нажмите `Ctrl+C` в терминале.

## Параметры конфигурации

| Параметр    | По умолчанию           | Переменная окружения | Описание             |
|-------------|------------------------|----------------------|----------------------|
| `--host`    | `minechat.dvmn.org`    | `MINECHAT_HOST`      | Адрес сервера чата   |
| `--port`    | `5000`                 | `MINECHAT_PORT`      | Порт сервера чата    |
| `--history` | `minechat_history.txt` | `MINECHAT_HISTORY`   | Путь к файлу истории |

### Приоритет параметров

1. Аргументы командной строки (высший приоритет).
2. Переменные окружения.
3. Значения по умолчанию.