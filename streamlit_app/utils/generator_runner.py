"""Generator runner utilities."""
import subprocess
import sys
from pathlib import Path
import streamlit as st
import pandas as pd

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
GENERATOR_SCRIPT = BASE_DIR / "generator_consumo_diario_standalone.py"
CONSUMO_DIR = BASE_DIR / "data" / "consumo"


def check_generator_exists():
    """Check if generator script exists."""
    return GENERATOR_SCRIPT.exists()


def run_generator(meses=2):
    """
    Run the consumption generator.

    Args:
        meses: Number of months to generate

    Returns:
        dict: Result with success status and message
    """
    if not check_generator_exists():
        return {
            "success": False,
            "message": f"Generator script not found at {GENERATOR_SCRIPT}"
        }

    try:
        # Change to the generator's directory
        cmd = [
            sys.executable,
            str(GENERATOR_SCRIPT),
            "--meses", str(meses)
        ]

        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            return {
                "success": True,
                "message": "✅ Generator executed successfully",
                "output": result.stdout
            }
        else:
            return {
                "success": False,
                "message": f"Generator failed with error: {result.stderr}",
                "output": result.stdout
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Generator execution timed out (>5 minutes)"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error running generator: {str(e)}"
        }


def get_generated_files():
    """Get list of generated consumption report files."""
    if not CONSUMO_DIR.exists():
        return []

    files = sorted(CONSUMO_DIR.glob("ReporteConsumos_*.xlsx"))
    return [
        {
            "filename": f.name,
            "path": str(f),
            "size_kb": f.stat().st_size / 1024,
            "date": pd.Timestamp(f.stat().st_mtime, unit='s')
        }
        for f in files
    ]


def load_generated_report(filepath):
    """Load a generated Excel report."""
    try:
        df = pd.read_excel(filepath)
        return df
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return pd.DataFrame()
