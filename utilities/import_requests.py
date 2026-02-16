import requests
import csv
import time

# --- CONFIGURATION ---
# Replace 'your-username' with your actual GitHub username (e.g., 'ajassra')
GITHUB_USERNAME = "avijassra" 
REPO_NAME = "ledger.ai"
# Generate this at https://github.com/settings/tokens (needs 'repo' scope)
GITHUB_TOKEN = "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"

CSV_FILE = "lumen_tasks.csv"
REPO_FULL_NAME = f"{GITHUB_USERNAME}/{REPO_NAME}"
# ---------------------

def create_issue(title, body, label):
    url = f"https://api.github.com/repos/{REPO_FULL_NAME}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Payload for the GitHub API
    issue_data = {
        "title": title,
        "body": body,
        "labels": [label.strip()] if label else []
    }
    
    response = requests.post(url, headers=headers, json=issue_data)
    
    if response.status_code == 201:
        print(f"✅ Successfully created: {title}")
    elif response.status_code == 403:
        print(f"❌ Rate limit exceeded or bad token. Check your permissions.")
    else:
        print(f"❌ Failed to create '{title}': {response.status_code} - {response.text}")

def main():
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            print(f"🚀 Starting import to {REPO_FULL_NAME}...")
            for row in reader:
                create_issue(row['title'], row['description'], row['label'])
                # Small pause to avoid hitting secondary rate limits
                time.sleep(1)
            print("\n🎉 Import complete! Check your 'Issues' tab on GitHub.")
    except FileNotFoundError:
        print(f"❌ Error: Could not find '{CSV_FILE}'. Make sure it's in this folder.")

if __name__ == "__main__":
    main()