"""Central paths and constants (configuration lives here, not in the UI)."""
import os

APP_NAME = "VIGILENS"
APP_FULL_NAME = "Visual Monitoring for Driver Alertness"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "vigilens.db")
SOUNDS_DIR = os.path.join(PROJECT_ROOT, "assets", "sounds")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
