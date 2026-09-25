import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)