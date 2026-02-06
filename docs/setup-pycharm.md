# PyCharm Setup Guide

Step-by-step guide for configuring PyCharm to work with this project.

## 1. Open the Project

1. **File > Open** and select the `DiscordBot` directory
2. PyCharm will detect it as a Python project

## 2. Configure Python Interpreter

1. **File > Settings > Project > Python Interpreter**
2. Click the gear icon > **Add Interpreter > Add Local Interpreter**
3. Select **Virtualenv Environment > New**
4. Set base interpreter to Python 3.11+
5. Location: `<project>/venv`
6. Click **OK**

## 3. Install Dependencies

Open the terminal in PyCharm and run:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 4. Configure Environment Variables

1. **Run > Edit Configurations**
2. For each run configuration, add an **EnvFile** or set environment variables
3. Point to the `.env` file in the project root

Alternatively, install the **EnvFile** plugin:
1. **File > Settings > Plugins > Marketplace**
2. Search for "EnvFile" and install it
3. In run configurations, check "Enable EnvFile" and add `.env`

## 5. Run Configurations

### API Server

1. **Run > Edit Configurations > + > Python**
2. Name: `API Server`
3. Module name: `uvicorn`
4. Parameters: `api.main:app --reload --host 0.0.0.0 --port 8000`
5. Working directory: project root
6. Environment variables: from `.env`

### Discord Bot

1. **Run > Edit Configurations > + > Python**
2. Name: `Discord Bot`
3. Module name: `bot.main`
4. Working directory: project root
5. Environment variables: from `.env`

### Tests

1. **Run > Edit Configurations > + > pytest**
2. Name: `All Tests`
3. Target: `tests/`
4. Working directory: project root
5. Environment variables:
   - `JWT_SECRET_KEY=test-secret`
   - `SECRET_KEY=test-secret`
   - `BOT_API_KEY=test-key`
   - `DATABASE_URL=sqlite+aiosqlite:///:memory:`
   - `DEBUG=true`

## 6. Code Style

The project uses **Black** for formatting and **Ruff** for linting.

### Configure Black

1. **File > Settings > Tools > Black**
2. Enable "On code reformat" and "On save"
3. Line length: 100

### Configure Ruff

1. Install the Ruff plugin from the marketplace
2. **File > Settings > Tools > Ruff**
3. Enable Ruff inspections

## 7. Database Tools

1. **View > Tool Windows > Database**
2. Click **+** > **Data Source > PostgreSQL**
3. Enter your database credentials from `.env`
4. Test the connection and click **OK**

## 8. Useful Shortcuts

| Shortcut | Action |
|----------|--------|
| `Shift+F10` | Run current configuration |
| `Shift+F9` | Debug current configuration |
| `Ctrl+Shift+F10` | Run current test |
| `Alt+Enter` | Quick fix |
| `Ctrl+Alt+L` | Reformat code |
| `Double Shift` | Search everywhere |

## 9. Recommended Plugins

- **EnvFile** - Load `.env` files in run configurations
- **Pydantic** - Pydantic model support
- **.env files support** - Syntax highlighting for `.env`
- **Tailwind CSS** - Tailwind class completion (for templates)
