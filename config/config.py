from decouple import config

class AppConfig:
    # 1. Database Configuration
    DB_USER = config("POSTGRES_USER", default="postgres")
    DB_PASSWORD = config("POSTGRES_PASSWORD")
    DB_HOST = config("POSTGRES_HOST", default="localhost")
    DB_PORT = config("POSTGRES_PORT", default="5432")
    DB_NAME = config("POSTGRES_DB", default="energy_db")

    # 2. MQTT / EMQX Configuration
    MQTT_USER = config("MQTT_USER", default='admin')
    MQTT_PASSWORD = config("MQTT_PASSWORD", default='admin')
    MQTT_HOST = config("MQTT_HOST", default="localhost")
    MQTT_PORT = config("MQTT_PORT", default=1883, cast=int)
    MQTT_TOPIC = config("MQTT_TOPIC", default="energy/meters/#")
    MQTT_Client_ID = config("MQTT_Client_ID", default="database_ingestion_service")
    
    # 3. Simulation Configuration (Strict validation rules)
    NUM_METERS = config("NUM_METERS", default=1000, cast=int)
    PUBLISH_INTERVAL_SEC = config("PUBLISH_INTERVAL_SEC", default=300, cast=int)
    HISTORICAL_WEEKS = config("HISTORICAL_WEEKS", default=4, cast=int)

    @property
    def db_url(self):
        """Returns the fully formatted PostgreSQL connection string."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

# Initialize the config
config = AppConfig()