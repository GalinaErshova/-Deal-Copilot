# Deal Copilot: состояние развёртывания

Редакция от 12 октября 2026 года, вечер. На NORDIK и gala-msk развёрнут commit `c74056d` ветки
`main` (PR #5, #6, #8). Прежние релизы `2c5154d` и `a7cf258` оставлены для отката.
Архитектура и восстановление с нуля — `docs/deployment-architecture.md`.
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
- Модели в списке выбора (`DEAL_COPILOT_OLLAMA_MODELS`): `qwen2.5:14b`, `qwen2.5:7b`,
  `qwen2.5:14b-ctx65k`, `gemma4:12b`, `gemma2:9b`, `mistral:7b`, `llama3.2:3b`, `llama2:7b`.
  Активная — `ollama:qwen2.5:14b`. Размер контекста `OLLAMA_NUM_CTX=16384`.
- Список должен совпадать с моделями, установленными на mini-PC. Если модель удалили
  из Ollama, уберите её и из списка, иначе обработка этой моделью вернёт ошибку.

## gala-msk — сайт

- Релиз: `/opt/deal-copilot/releases/<commit>`, ссылка `/opt/deal-copilot/current`.
  Фронтенд собран на NORDIK с `NEXT_PUBLIC_API_URL=/api`.
- Контейнеры: `deal-copilot-web` (node:22-slim, `next start`, лимит 512 МБ) и
  `deal-copilot-proxy` (nginx:alpine, лимит 64 МБ), сеть `deal-copilot-net`; прокси также
  подключён к `dokploy-network`.
- Прокси: `/opt/deal-copilot/proxy/default.conf`. Пароль на весь сайт, `/api/admin/` → 403,
  таймаут ответа API 900 с, размер загрузки до 50 МБ.
- Логин и пароль сайта хранятся на NORDIK: `/opt/deal-copilot/secrets/web-basic-auth.txt`
  (права 600). На gala-msk остаётся только хеш пароля в `/opt/deal-copilot/proxy/htpasswd`.
- Порт прокси: `127.0.0.1:8095` и `10.66.66.3:8095`, наружу не открыт; снаружи сайт
  доступен только через Traefik по домену.

## Адрес сайта

`https://deal-copilot.tools01.ru` — HTTPS через Traefik (Dokploy), сертификат Let's Encrypt.
Маршрут: `/etc/dokploy/traefik/dynamic/deal-copilot.yml` (копия — `/opt/deal-copilot/proxy/`).
Вход по логину и паролю из файла на NORDIK; учётная запись одна.

Запасной путь без домена — SSH-туннель, затем `http://localhost:8095`:

```bash
ssh -N -L 8095:127.0.0.1:8095 gala
```

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
| `/api/health` на NORDIK | ok, `model_configured: true` |
| Список профилей без токена / с токеном | 403 / 200 |
| `http://deal-copilot.tools01.ru` | 301 на HTTPS |
| `https://deal-copilot.tools01.ru` без пароля / с паролем | 401 / 200 |
| `https://deal-copilot.tools01.ru/api/admin/model-profiles` | 403 |
| Обработка через `ollama:qwen2.5:14b` | площадь 1200, срок 12, режим найдены, источники подтверждены; 81 с |
| Обработка через `ollama:qwen2.5:7b` | вместо чисел мусор (`a2`, `c`); поля помечены `needs_review` |

Не проверено: отказ Ollama во время обработки, восстановление базы из копии, вид сайта
на телефоне и широком экране.

## Откат и резервная копия

- Откат: переключить ссылку `current` на `/opt/deal-copilot/releases/a7cf258` на NORDIK
  и gala-msk, вернуть `/etc/deal-copilot/backend.env` из копии, перезапустить
  `deal-copilot-api` и `docker restart deal-copilot-web`.
- Копии перед выпуском `2c5154d` лежат на NORDIK в `/var/backups/deal-copilot/`: база,
  загрузки и `backend.env`.
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
