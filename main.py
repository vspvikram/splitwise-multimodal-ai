"""Main entry point for running the Streamlit app"""
import subprocess
import sys
from pathlib import Path
import dotenv

dotenv.load_dotenv()

def main():
    """Run the Streamlit app"""
    app_path = Path(__file__).parent / "src" / "splitwise" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])

if __name__ == "__main__":
    main()