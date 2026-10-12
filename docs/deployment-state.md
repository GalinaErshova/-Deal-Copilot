# Deal Copilot: состояние развёртывания

Редакция от 12 октября 2026 года. Развёрнут commit `a7cf258` ветки `integration/apply-all-prs`.
Секреты здесь не записываются — только где они лежат.

## Схема

| Машина | Роль | Адрес в туннеле |
|---|---|---|
| gala-msk (5.42.101.153, SSH-порт 2222) | Сайт Next.js и прокси с паролем | 10.66.66.3 (wg0) |
| NORDIK (213.165.55.159) | API FastAPI и база SQLite | 10.66.66.16 (wg0) |
| mini-PC (minipc-01, Windows) | Ollama с локальными моделями | 10.66.68.2 (wg-mini-NORDIK) |

Путь запроса: браузер → прокси на gala-msk (пароль) → `/api/` по wg0 на NORDIK:8020 →
Ollama на mini-PC:11434. Браузер к NORDIK и mini-PC напрямую не обращается.

## NORDIK — API и база

- Релизы: `/opt/deal-copilot/releases/<commit>`, рабочий — ссылка `/opt/deal-copilot/current`.
- Данные: `/var/lib/deal-copilot/deal_copilot.db` и `/var/lib/deal-copilot/uploads`.
- Настройки и токен администратора моделей: `/etc/deal-copilot/backend.env` (права 640,
  владелец root, группа dealcopilot).
- Служба: `deal-copilot-api.service`, пользователь `dealcopilot`, Python 3.11,
  слушает `10.66.66.16:8020`.
- Порт 8020 принимает только gala-msk (10.66.66.3) и локальные запросы; правила iptables
  ставит сама служба при запуске.
- Модели в списке выбора: `qwen2.5:7b`, `qwen2.5:14b`, `llama3.1:8b`, `llama3.2:3b`,
  `sutyrin/saiga_mistral_7b:latest`. Активная — `ollama:qwen2.5:7b`.

## gala-msk — сайт

- Релиз: `/opt/deal-copilot/releases/<commit>`, ссылка `/opt/deal-copilot/current`.
  Фронтенд собран на NORDIK с `NEXT_PUBLIC_API_URL=/api`.
- Контейнеры: `deal-copilot-web` (node:22-slim, `next start`, лимит 512 МБ) и
  `deal-copilot-proxy` (nginx:alpine, лимит 64 МБ), сеть `deal-copilot-net`; прокси также
  подключён к `dokploy-network`.
- Прокси: `/opt/deal-copilot/proxy/default.conf`. Пароль на весь сайт, `/api/admin/` → 403,
  таймаут ответа API 900 с, размер загрузки до 50 МБ.
- Логин и пароль сайта: `/opt/deal-copilot/secrets/web-basic-auth.txt` (права 600).
- Порт прокси: `127.0.0.1:8095` и `10.66.66.3:8095`, наружу не открыт.

## Как открыть сайт сейчас

Пока нет DNS-записи, сайт открывается через SSH-туннель:

```bash
ssh -N -L 8095:127.0.0.1:8095 gala
```

Затем в браузере — `http://localhost:8095`, логин и пароль из файла выше.

## Как включить HTTPS по домену

1. Добавить A-запись `deal-copilot.tools01.ru` → `5.42.101.153`.
2. Скопировать готовый маршрут Traefik:

```bash
cp /opt/deal-copilot/proxy/traefik-deal-copilot.yml /etc/dokploy/traefik/dynamic/deal-copilot.yml
```

Traefik подхватит файл сам и выпустит сертификат Let's Encrypt.

## Смена модели

Только на NORDIK, токен — из `/etc/deal-copilot/backend.env`:

```bash
T=$(grep ^MODEL_ADMIN_TOKEN= /etc/deal-copilot/backend.env | cut -d= -f2-)
curl -s -H "X-Model-Admin-Token: $T" http://10.66.66.16:8020/api/admin/model-profiles
curl -s -X PUT -H "X-Model-Admin-Token: $T" -H 'Content-Type: application/json' -d '{"profile_code":"mock"}' http://10.66.66.16:8020/api/admin/model-profile
```

## Результаты приёмки 12 октября 2026 года

| Проверка | Результат |
|---|---|
| `/api/health` на NORDIK | ok |
| Список профилей без токена / с токеном | 403 / 200 |
| Через прокси без пароля | 401 |
| Через прокси: сайт, `/api/settings`, `/api/health` | 200 |
| Через прокси: `/api/admin/model-profiles` | 403 |
| Traefik → прокси | отвечает (401 без пароля) |
| Обработка документа через `ollama:qwen2.5:7b` | успешно, 50 с; в журнале `model_profile` и `model` |

Не проверено: отказ Ollama во время обработки (не останавливали Ollama на рабочей машине),
восстановление базы из копии, вид сайта на телефоне и широком экране.

## Откат и резервная копия

- Прежней установки не было, откатываться некуда; для следующих релизов — переключить
  ссылку `current` на прежний каталог в `releases` и перезапустить службу и контейнер.
- Копия базы вместе с файлами, без остановки службы:

```bash
sqlite3 /var/lib/deal-copilot/deal_copilot.db ".backup /var/backups/deal_copilot-$(date +%F).db" && tar -czf /var/backups/deal-copilot-uploads-$(date +%F).tgz -C /var/lib/deal-copilot uploads
```

## Ограничения

- Когда mini-PC выключен или Ollama не запущена, обработка документов завершается ошибкой.
  Расчёт, прайс-лист и уже извлечённые данные работают.
- Учётных записей в приложении нет: доступ ограничивает только пароль на прокси.

## Ollama для всей сети WireGuard

С 12 октября 2026 года Ollama на mini-PC доступна любому участнику сети WireGuard по адресу
`http://10.66.66.1:11434`, в том числе Telegram-ботам на серверах сети. Это служба
`ollama-wg-forward` на ALEX: `socat` слушает только адрес ALEX в wg0 и пересылает запросы
на mini-PC (10.66.68.2:11434). Из интернета порт недоступен.

API Deal Copilot на NORDIK по-прежнему ходит к mini-PC напрямую, без ALEX.

Проверено: из ALEX, NORDIK и gala-msk модель `llama3.2:3b` отвечает через `10.66.66.1:11434`.

Отключить: `systemctl disable --now ollama-wg-forward` на ALEX.
