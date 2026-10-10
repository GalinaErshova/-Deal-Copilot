# Deal Copilot: развёртывание на NORDIK и mini-PC

Инструкция для агента с доступом к обеим машинам. NORDIK публикует Next.js и передаёт
запросы /api/ по частному соединению на FastAPI на mini-PC. SQLite, загруженные
документы и Ollama остаются на mini-PC. Браузер не обращается к mini-PC напрямую.

## До начала

1. Уточните домен, частные адреса, способ соединения NORDIK с mini-PC и постоянный
   каталог данных. Не считайте адреса из примеров фактическими.
2. На mini-PC проверьте список уже установленных моделей командой ollama list и
   локальный ответ http://127.0.0.1:11434/api/tags. Не загружайте новые модели
   без решения владельца.
3. Сохраните текущие конфигурации и согласованную резервную копию прежней установки.
   Не заменяйте работающий Ask & Learn. Развёртывайте конкретный проверенный commit
   Deal Copilot; сохраните прежний релиз для отката.

## Mini-PC: API и данные

Пример для Windows и Python 3.11+ из каталога релиза:

    cd <DEAL_COPILOT_RELEASE>\backend
    py -3.11 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -e .
    Copy-Item .env.example .env

Заполните backend/.env. Значения в угловых скобках замените фактическими:

    DATABASE_URL=sqlite:///D:/DealCopilot/data/deal_copilot.db
    DATA_DIR=D:/DealCopilot/data
    UPLOAD_DIR=D:/DealCopilot/data/uploads
    LLM_PROVIDER=mock
    DEMO_MODE=true
    MIMO_API_KEY=
    OLLAMA_BASE_URL=http://127.0.0.1:11434
    OLLAMA_MODELS=<ИМЯ_ИЗ_OLLAMA_LIST>,<ВТОРОЕ_ИМЯ_ПРИ_НАЛИЧИИ>
    OLLAMA_TIMEOUT_SECONDS=120
    MODEL_ADMIN_TOKEN=<СЛУЧАЙНЫЙ_СЕКРЕТ_НЕ_КОРОЧЕ_32_СИМВОЛОВ>

Замените D:/DealCopilot/data на утверждённый постоянный каталог вне каталога релиза.
На локальном экземпляре оставьте MIMO_API_KEY пустым: список выбора не должен
содержать облачные профили. Секрет MODEL_ADMIN_TOKEN храните только на mini-PC.
Не помещайте его в Git, браузер, URL или журналы.
Перед запуском сохраните вместе файл SQLite и каталог загрузок. Новый релиз
добавляет таблицу runtime_model_selection при первом запуске, не удаляя сделки.

    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

Оформите запуск как постоянную службу средствами, установленными на mini-PC.
Разрешите вход на порт 8000 только с частного адреса NORDIK и локально. SQLite должен быть
локальным файлом рядом с API, не на сетевом диске. Ollama оставьте доступной только
по 127.0.0.1:11434. При системном HTTP-прокси исключите локальный адрес через NO_PROXY.

## NORDIK: сайт и прокси

Используйте тот же commit, что и на mini-PC. В frontend/.env.production.local задайте
NEXT_PUBLIC_API_URL=/api до сборки. Затем выполните:

    cd <DEAL_COPILOT_RELEASE>/frontend
    npm ci
    npm run build
    npm run start -- --hostname 127.0.0.1 --port 3000

Оформите Next.js как постоянный сервис. В отдельном HTTPS virtual host Deal Copilot
настройте Nginx так, чтобы путь /api/ сохранялся при проксировании:

    location ^~ /api/admin/ { return 403; }
    location /api/ {
        proxy_pass http://<MINI_PC_PRIVATE_IP>:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 180s;
        client_max_body_size 50m;
    }
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

Проверьте частный маршрут до mini-PC до переключения DNS. Включите HTTPS и ограничьте
доступ ко всему сайту существующим VPN или серверной аутентификацией: в Deal Copilot
пока нет учётных записей и прав пользователей. Публичный доступ без такого ограничения
не включайте. Административные маршруты закрыты на NORDIK; модель меняют на mini-PC.

## Выбор модели без перезапуска

На mini-PC вызовите административный API с токеном в заголовке. В PowerShell:

    $headers = @{ 'X-Model-Admin-Token' = '<MODEL_ADMIN_TOKEN_ИЗ_BACKEND_ENV>' }
    Invoke-RestMethod 'http://127.0.0.1:8000/api/admin/model-profiles' -Headers $headers
    Invoke-RestMethod 'http://127.0.0.1:8000/api/admin/model-profile' -Method Put -Headers $headers -ContentType 'application/json' -Body '{"profile_code":"ollama:<ИМЯ_ИЗ_СПИСКА>"}'

Для возврата к заглушке используйте тело {"profile_code":"mock"}. Активный профиль
хранится в SQLite, действует для следующих запусков обработки сразу и переживает
перезапуск. Уже начатая обработка завершится на прежнем профиле. Через GET /api/settings
проверьте llm_provider, llm_model и demo_mode. URL и секреты моделей этот ответ не отдаёт.
При удалении активной модели из OLLAMA_MODELS сначала переключите профиль: молчаливого
перехода в облако нет.

## Приёмка и откат

1. На mini-PC: /api/health отвечает; Ollama доступна локально; список профилей без
   токена даёт 403, с токеном — 200.
2. Через NORDIK: сайт и /api/settings доступны по HTTPS; /api/admin/model-profiles
   даёт 403; /api/health работает через частный прокси. Проверьте мобильную и широкую
   ширину экрана.
3. В тестовой сделке загрузите небольшой документ, выберите профиль Ollama и
   обработайте документ. Сверьте поля с источником. В шаге ai_extraction должны
   записаться model_profile и model. Переключитесь на mock без перезапуска и повторите.
4. При контролируемой недоступности Ollama обработка должна завершаться явной ошибкой,
   без перехода к облачной модели, а загруженный документ должен сохраниться.
5. Проверьте восстановление SQLite вместе с каталогом загрузок. Во время копирования
   остановите запись либо используйте SQLite backup API.

При неудаче верните прежний релиз и конфигурацию прокси. Для отката данных используйте
сохранённую согласованную копию базы и файлов; не удаляйте таблицы вручную. Запишите
фактические адреса, версии, commit, результаты проверок и откатный релиз в существующем
документе состояния развёртывания. Секреты туда не записывайте.
