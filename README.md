# babkacli

Utilities for parsing agent JSON responses and executing workspace commands.

## Agent CLI

### Установка и запуск (Windows / PowerShell)

Из корня проекта создайте окружение и установите зависимости:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Если файла `.env` ещё нет, скопируйте `.env.example` в `.env`.
Приложение использует локальную Ollama:

```dotenv
AI_ENDPOINT=http://localhost:11434/v1
AI_MODEL=gemma4:latest
DEBUG_COLORS=false
```


Для DeepSeek заполните переменную DEEPSEEK_TOKEN в .env.
Модель выбирается в списке над чатом или через --model:
например, babkacli cli --model deepseek-flash или babkacli ui --model deepseek-v4-pro.
Чтобы вернуться к Ollama: --model gemma4:latest.
Модель по умолчанию задаётся через AI_MODEL.
Модели deepseek-* используют https://api.deepseek.com и DEEPSEEK_TOKEN,
независимо от локального AI_ENDPOINT. Сообщения отправляются в облачный API.
Список моделей: https://api-docs.deepseek.com/api/create-chat-completion/.

Ollama должна быть запущена, а модель установлена (`ollama pull gemma4`).
Для локальной Ollama ключ не требуется. Для другого совместимого API задайте
базовый `AI_ENDPOINT` без `/chat/completions`, `AI_MODEL` и `AI_API_KEY`.
`DEBUG_COLORS=true` включает отладочные фоны и рамки; по умолчанию они выключены.
GitHub Models больше не поддерживается: сервис закрыт.

Запуск графического приложения без активации окружения:

```powershell
.\.venv\Scripts\babkacli.exe ui
```

Запуск консольного агента:

```powershell
.\.venv\Scripts\babkacli.exe cli
```

Для выбора рабочего проекта добавьте `--workspace "C:\path\to\project"`.
Без этого параметра используется папка `test_project`.
Для веб-чата в Windows нужен установленный Microsoft Edge WebView2 Runtime.

Run the LLM agent from the repository root:

```bash
babkacli
```

It starts in `test_project` by default and accepts natural language tasks.
The agent can inspect files, create folders, create files, write code, run Python scripts, and finish with a `done` command.

For a one-off task:

```bash
babkacli --once "Inspect the project and summarize the main entrypoint."
```

If you want the older command-testing CLI, run:

```bash
python -m src.cli
```

For the PySide6 UI:

```bash
babkacli-ui
```

or directly:

```bash
python -m src.ui
```

## Testing

```
.\.venv\Scripts\python.exe -m pytest -q
```

### UI terminal

The embedded terminal is a PySide6 interactive ANSI/VT100 terminal. On Windows it uses `winpty` for live streaming output and full-screen control sequences; `QProcess` remains the fallback transport backend. It starts PowerShell with `-NoProfile`, `POWERSHELL_DISABLE_TELEMETRY=1`, `TERM=xterm-256color`, and `COLORTERM=truecolor`.
