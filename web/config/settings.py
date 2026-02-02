from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    TESTING = False


class ProductionConfig(Config):
    DATABASE_URI = os.getenv("DATABASE_PRODUCTION_URI")
    SECRET_KEY = os.getenv("SECRET_KEY")
    DEBUG = False
    LOG_LEVEL = "INFO"
    REDIS_URI = os.getenv("REDIS_PRODUCTION_URI")
    LOG_FILE = "logs/production.log"


class DevelopmentConfig(Config):
    DATABASE_URI = os.getenv("DATABASE_DEVELOPMENT_URI")
    SECRET_KEY = os.getenv("SECRET_KEY")
    DEBUG = True
    REDIS_URI = os.getenv("REDIS_DEVELOPMENT_URI")
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/development.log"


class TestingConfig(Config):
    DATABASE_URI = os.getenv("DATABASE_TESTING_URI")
    TESTING = True
