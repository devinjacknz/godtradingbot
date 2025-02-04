"""Helper script to process API responses."""

import json
import sys


def process_json():
    """Process JSON from stdin and print formatted output."""
    try:
        data = json.load(sys.stdin)
        if isinstance(data, dict):
            if "access_token" in data:
                print(data["access_token"])
            else:
                print(json.dumps(data, indent=2))
        else:
            print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print("Error: Invalid JSON input")
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    process_json()
