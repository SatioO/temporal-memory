from schema.config import AppConfig

# Eager singleton — fails fast at startup if env is misconfigured
config = AppConfig.from_env()
