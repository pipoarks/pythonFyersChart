from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json
import time

# CHANGE THESE
CHROME_PROFILE_PATH = r"C:\Users\arkan\AppData\Local\Google\Chrome\User Data"
PROFILE_NAME = "Default"   # or "Profile 1"

options = Options()
options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
options.add_argument(f"--profile-directory={PROFILE_NAME}")
options.add_argument("--start-maximized")

driver = webdriver.Chrome(options=options)

# Open the site where you are already logged in
driver.get("https://chartink.com/screener/di-ve-green-watchlist-scanner")

# Wait for page & cookies to load
time.sleep(5)

cookies = driver.get_cookies()

# Save cookies to file
with open("cookies.json", "w", encoding="utf-8") as f:
    json.dump(cookies, f, indent=2)

print("Cookies saved to cookies.json")

driver.quit()
