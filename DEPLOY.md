# Запуск бота и Mini App на сервере

Эта инструкция проведёт вас от пустого сервера до работающего бота в Telegram.
Займёт примерно 30–40 минут. Все команды нужно выполнять на сервере по SSH.

## Как это устроено

```
Пользователь в Telegram
        │  /start или кнопка меню «Трекер»
        ▼
  Бот (webhook) ───► ваш сервер: https://ВАШ_ДОМЕН
                          │
                  Caddy (HTTPS, сертификат Let's Encrypt — автоматически)
                          │
                  Приложение (FastAPI + веб-страница)
                          │
                  PostgreSQL (данные пользователей)
```

* Бот — это то же приложение. Отдельный процесс не нужен: Telegram присылает
  сообщения на адрес `https://ВАШ_ДОМЕН/api/telegram/webhook`.
* Mini App — та же веб-страница. Внутри Telegram пользователь входит
  автоматически: сервер проверяет подпись `initData` токеном бота. Пароль
  и email не нужны.
* Telegram открывает Mini App **только по HTTPS**, поэтому нужен домен.
  Сертификат Caddy получит сам.

## Что понадобится

| Что | Где взять | Примерная цена |
|---|---|---|
| VPS: 1 vCPU, 1 ГБ RAM, 10 ГБ диска, **Ubuntu 22.04 или 24.04** | любой хостинг: Timeweb Cloud, Selectel, Aeza, Hetzner, DigitalOcean и т. п. | от ~300 ₽/мес |
| Домен или поддомен (например, `tracker.mysite.ru`) | reg.ru, nic.ru, Namecheap и т. п.; подойдёт поддомен уже имеющегося домена | от ~200 ₽/год |
| Аккаунт Telegram | — | бесплатно |

---

## Шаг 1. Создайте бота в @BotFather

1. Откройте в Telegram [@BotFather](https://t.me/BotFather) и отправьте `/newbot`.
2. Введите отображаемое имя (например, `Трекер калорий`).
3. Введите username. Он должен заканчиваться на `bot` (например, `my_calorie_tracker_bot`).
4. BotFather пришлёт **токен** вида `1234567890:AAH...`. Сохраните его.

> ⚠️ Токен — это пароль от бота. Не публикуйте его и не коммитьте в git.
> Если он утёк, отправьте BotFather команду `/revoke` и получите новый.

Необязательно, но приятно: `/setuserpic` задаёт аватар бота.

## Шаг 2. Направьте домен на сервер

1. В панели хостинга узнайте **IP-адрес** сервера (например, `203.0.113.10`).
2. В DNS-настройках домена создайте запись:
   * тип `A`;
   * имя: `tracker` (для поддомена `tracker.mysite.ru`) или `@` (для самого домена);
   * значение: IP сервера.
3. Подождите 5–30 минут, пока запись распространится. Проверить можно так
   (на своём компьютере):
   ```bash
   nslookup tracker.mysite.ru
   ```
   В ответе должен быть IP вашего сервера.

## Шаг 3. Подготовьте сервер

Подключитесь к серверу (логин и пароль даст хостинг):

```bash
ssh root@203.0.113.10
```

Обновите систему и установите Docker (вместе с Docker Compose):

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
docker --version && docker compose version    # обе команды должны вывести версии
```

Откройте в файрволе порты SSH, HTTP и HTTPS:

```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable
```

> Если у хостинга есть свой внешний файрвол («группы безопасности»), откройте
> порты 80 и 443 и там.

## Шаг 4. Скачайте проект

```bash
apt install -y git
git clone https://github.com/denis313/KBGU.git /opt/calorie-tracker
cd /opt/calorie-tracker
git checkout claude/nifty-johnson-63kr58   # не нужно, если изменения уже влиты в main
```

> Если репозиторий приватный, git запросит логин и пароль. Вместо пароля
> введите GitHub Personal Access Token (GitHub → Settings → Developer settings
> → Personal access tokens) или настройте на сервере deploy key.

## Шаг 5. Заполните настройки `.env`

```bash
cp .env.example .env
```

Сгенерируйте три случайных секрета:

```bash
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
echo "TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 32)"
```

Откройте файл (`nano .env`) и заполните поля:

```ini
SECRET_KEY=<первый сгенерированный секрет>
DOMAIN=tracker.mysite.ru                 # ваш домен, без https://
POSTGRES_PASSWORD=<второй секрет>        # только буквы и цифры
TELEGRAM_BOT_TOKEN=1234567890:AAH...     # токен из шага 1
TELEGRAM_WEBHOOK_SECRET=<третий секрет>
```

Строки `DATABASE_URL` и `WEBAPP_URL` оставьте как есть: в продакшене они
вычисляются автоматически из `POSTGRES_PASSWORD` и `DOMAIN`. Чтобы сохранить
файл в nano, нажмите `Ctrl+O`, затем `Enter`; выйти — `Ctrl+X`.

Закройте доступ к файлу для других пользователей:

```bash
chmod 600 .env
```

## Шаг 6. Запустите

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Первый запуск занимает 2–5 минут. При старте приложение само:

1. создаёт таблицы в PostgreSQL (миграции Alembic);
2. загружает каталог продуктов и готовых блюд;
3. регистрирует бота: webhook, кнопку меню «Трекер», команду `/start` и описание;
4. запускает веб-сервер. Caddy тем временем получает HTTPS-сертификат.

Проверьте, что всё поднялось:

```bash
docker compose -f docker-compose.prod.yml ps        # у всех трёх сервисов статус running/healthy
docker compose -f docker-compose.prod.yml logs api  # ищите строку «Bot @... is ready»
curl https://tracker.mysite.ru/api/health           # ответ должен быть {"status":"ok"}
```

## Шаг 7. Проверьте в Telegram

1. Найдите своего бота по username и нажмите **Start** (`/start`).
2. Бот ответит приветствием с кнопкой **«🥗 Открыть трекер»**.
3. Рядом с полем ввода появится кнопка меню **«Трекер»**. Она тоже открывает приложение.
4. При первом открытии заполните профиль (рост, вес, цель). Дальше всё
   сохраняется в базе и доступно с любого устройства под этим аккаунтом Telegram.

Если кнопка меню появилась не сразу, закройте и снова откройте чат с ботом.

### Необязательно: сделайте Mini App «главным приложением» бота

Тогда в профиле бота появится кнопка «Открыть», а приложение можно будет
открыть прямой ссылкой. В @BotFather: `/mybots` → выберите бота →
**Bot Settings** → **Configure Mini App** → **Enable Mini App** → вставьте
`https://tracker.mysite.ru/`. Названия пунктов в BotFather иногда меняются,
но раздел всегда связан с «Mini App». После этого приложение открывается
по ссылке `https://t.me/<username_бота>?startapp`.

---

## Обновление до новой версии

```bash
cd /opt/calorie-tracker
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Миграции базы применятся автоматически, данные пользователей сохранятся:
они лежат в Docker-томе `pgdata`, который не удаляется при пересборке.

## Резервные копии базы

Разовая копия:

```bash
cd /opt/calorie-tracker
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U calorie calorie_tracker | gzip > backup-$(date +%F).sql.gz
```

Ежедневная копия в 03:00 с хранением 14 дней. Откройте `crontab -e` и добавьте строку:

```cron
0 3 * * * cd /opt/calorie-tracker && mkdir -p backups && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U calorie calorie_tracker | gzip > backups/db-$(date +\%F).sql.gz && find backups -name 'db-*.sql.gz' -mtime +14 -delete
```

Восстановление на новом сервере (выполните шаги 1–5, но вместо шага 6 сделайте следующее):

```bash
docker compose -f docker-compose.prod.yml up -d db     # запустить только базу, пока она пустая
sleep 10                                               # дать PostgreSQL стартовать
gunzip -c backup-2026-09-23.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U calorie calorie_tracker
docker compose -f docker-compose.prod.yml up -d --build   # теперь запустить всё остальное
```

Копии лучше дополнительно переносить с сервера: в облачное хранилище или на свой компьютер через `scp`.

## Полезные команды

| Задача | Команда (из `/opt/calorie-tracker`) |
|---|---|
| Логи приложения в реальном времени | `docker compose -f docker-compose.prod.yml logs -f api` |
| Логи Caddy (HTTPS) | `docker compose -f docker-compose.prod.yml logs caddy` |
| Перезапуск | `docker compose -f docker-compose.prod.yml restart api` |
| Остановка | `docker compose -f docker-compose.prod.yml down` (данные сохранятся) |
| Состояние webhook бота | `docker compose -f docker-compose.prod.yml exec api python -m app.bot info` |
| Перерегистрировать бота (после смены токена или домена) | `docker compose -f docker-compose.prod.yml exec api python -m app.bot setup` |
| Консоль базы данных | `docker compose -f docker-compose.prod.yml exec db psql -U calorie calorie_tracker` |

> Чтобы не писать каждый раз `-f docker-compose.prod.yml`, выполните
> `export COMPOSE_FILE=docker-compose.prod.yml`. Тогда хватит `docker compose logs -f api`.

## Если что-то не работает

| Симптом | Причина и решение |
|---|---|
| `curl https://домен/...` выдаёт ошибку сертификата или соединения | DNS ещё не обновился или закрыты порты 80/443. Проверьте `nslookup домен`, `ufw status` и файрвол хостинга. Посмотрите `logs caddy`: Caddy пишет, почему не удалось получить сертификат. |
| В логах `api`: `WARNING: Telegram bot setup failed` | Неверный `TELEGRAM_BOT_TOKEN` или сервер не может достучаться до `api.telegram.org`. Исправьте `.env` и выполните `docker compose -f docker-compose.prod.yml up -d` (пересоздаст контейнер с новыми настройками). |
| Бот не отвечает на `/start` | Выполните `python -m app.bot info` (см. таблицу выше) и посмотрите поле `last_error_message`. Частые причины: сертификат ещё не выпущен или сменился `TELEGRAM_WEBHOOK_SECRET`. После исправления выполните `python -m app.bot setup`. |
| Приложение открывается, но пишет «Telegram sign-in failed: initData signature is invalid» | Токен в `.env` не от этого бота. Возьмите правильный токен и перезапустите. |
| «initData has expired» | Mini App было открыто больше суток назад. Закройте и откройте его заново. |
| Страница открывается в браузере, но в Telegram белый экран | Проверьте, что адрес начинается с `https://` и совпадает с `DOMAIN`. Затем выполните `python -m app.bot setup`. |

## Тестирование без сервера (на своём компьютере)

Telegram требует HTTPS, поэтому локальный сервер нужно временно открыть через туннель.

```bash
# 1. PostgreSQL и приложение — как в README (раздел Quick start)
# 2. Туннель: выдаст адрес вида https://xxxx.trycloudflare.com
cloudflared tunnel --url http://localhost:8000      # или: ngrok http 8000
# 3. В .env укажите:
#    WEBAPP_URL=https://xxxx.trycloudflare.com
#    TELEGRAM_BOT_TOKEN=...   TELEGRAM_WEBHOOK_SECRET=...
# 4. Перезапустите uvicorn и зарегистрируйте бота:
python -m app.bot setup
```

При каждом новом адресе туннеля повторяйте шаги 3–4. Для постоянной работы
используйте сервер с доменом, как описано выше.

## Безопасность: коротко

* Файл `.env` не попадает в git (он в `.gitignore`) и в Docker-образ (он в `.dockerignore`). Храните его только на сервере.
* PostgreSQL не открыт наружу: порт базы доступен только внутри Docker-сети.
* Входящие запросы webhook принимаются, только если в них есть `TELEGRAM_WEBHOOK_SECRET`. Вход в Mini App проверяет подпись `initData` токеном бота. Подделать пользователя нельзя.
* Держите сервер обновлённым: время от времени выполняйте `apt update && apt upgrade -y`.
