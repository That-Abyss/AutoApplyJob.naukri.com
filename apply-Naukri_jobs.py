import os
import time
import datetime
import requests
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Load environment variables
load_dotenv()
NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL")
NAUKRI_PASS = os.getenv("NAUKRI_PASS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")
CHAT_IDS = [int(chat_id.strip()) for chat_id in CHAT_IDS.split(",") if chat_id.strip()]










job_titles = ["python Developer, Software Developer"]
MAX_JOBS_PER_TITLE = 5   #how many applies it will make per job title
job_experience = 0
job_freshness_days = 1   #Sorting the job post timing



allow_third_party_apply = True
applied_jobs = set()














def random_delay(min_seconds=1, max_seconds=3):
    time.sleep(random.uniform(min_seconds, max_seconds))

def slow_typing(element, text, delay=0.1):
    for char in text:
        element.send_keys(char)
        time.sleep(delay)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    for chat_id in CHAT_IDS:
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()  # Raise exception for HTTP errors
        except Exception as e:
            print(f"Telegram Error sending to {chat_id}:", e)

def get_brave_driver():
    brave_path = r"C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"  //For Other browser Make changes accordingly
    user_data_dir = r"Path for your browser i prefer use Brave"
    options = Options()
    # options.add_argument("--headless=new")  # comment out to see browser
    options.binary_location = brave_path
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")
    return webdriver.Chrome(options=options)











# Check if today is Sunday and file wasn't updated today
def should_reset_visited_jobs(file_path="visited_jobs.txt"):
    if not os.path.exists(file_path):
        return False

    today = datetime.datetime.now().weekday()  # 0 = Monday, 6 = Sunday
    if today != 6:
        return False

    file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
    return file_time.date() < datetime.datetime.now().date()

# Load visited jobs with weekly (Sunday) reset
def load_visited_jobs(file_path="visited_jobs.txt"):
    if should_reset_visited_jobs(file_path):
        print("♻️ Sunday reset: clearing visited jobs...")
        try:
            os.remove(file_path)
        except:
            pass
        send_telegram_message("♻️ *Visited job cache reset* (Sunday schedule).")
        return set()
    
    try:
        with open(file_path, "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

# Save visited jobs
def save_visited_jobs(jobs_set, file_path="visited_jobs.txt"):
    with open(file_path, "w") as f:
        for job in jobs_set:
            f.write(f"{job}\n")

# Initialize visited jobs
visited_jobs = load_visited_jobs()






def send_remaining_external_tabs(driver):
    print("📤 Scanning open tabs for 3rd-party sites before quitting...")
    for handle in driver.window_handles:
        try:
            driver.switch_to.window(handle)
            url = driver.current_url
            if "naukri.com" not in url:
                title = driver.title or "Unknown Site"
                send_telegram_message(f"🔗 *External Link Detected Before Exit*\n🌐 `{title}`\n🔗 [Click here]({url})")
        except:
            continue























def naukri_apply(driver):
    print("🚀 Navigating to Naukri...")
    driver.get("https://www.naukri.com/mnjuser/login")
    time.sleep(3)

    if "mnjuser/homepage" not in driver.current_url:
        try:
            slow_typing(driver.find_element(By.ID, "usernameField"), NAUKRI_EMAIL)
            slow_typing(driver.find_element(By.ID, "passwordField"), NAUKRI_PASS)
            driver.find_element(By.XPATH, "//button[@type='submit']").click()
            time.sleep(5)
        except:
            print("🔓 Login skipped or failed — maybe already logged in.")

    for title in job_titles:
        search_url = f"https://www.naukri.com/{title.lower().replace(' ', '-')}-jobs?experience={job_experience}&freshtype=1"
        if job_freshness_days:
            search_url += f"&jobAge={job_freshness_days}"
        driver.get(search_url)
        time.sleep(4)

        job_links = driver.find_elements(By.CSS_SELECTOR, "a.title")
        applied_count = 0

        for job_link in job_links[:MAX_JOBS_PER_TITLE * 2]:
            try:
                job_url = job_link.get_attribute("href")
                if job_url in visited_jobs:
                    print(f"⏭️ Already visited: {job_url}")
                    continue

                driver.execute_script("window.open(arguments[0]);", job_url)
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(3)

                try:
                    apply_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//button[contains(text(),'Apply') or contains(text(),'interested')]")
                        )
                    )
                    apply_btn.click()
                    time.sleep(4)

                    # ✅ Check for error/limit
                    error_elements = driver.find_elements(By.XPATH, "//*[contains(text(),'There was an error while processing your request')]")
                    if error_elements:
                        send_telegram_message("🛑 *Naukri Limit Reached or Site Error Detected.*\nBot is stopping.")
                        print("🛑 Limit reached")
                        send_remaining_external_tabs(driver)
                        driver.quit()
                        return True

                    # ❗ Detect Q/A via chatbot or input
                    qa_detected = False

                    try:
                        chatbot_popup = driver.find_element(By.CLASS_NAME, "chatbot_Nav")
                        if chatbot_popup.is_displayed():
                            qa_detected = True
                    except:
                        pass

                    inputs = driver.find_elements(By.XPATH, "//input[not(@type='hidden')] | //textarea")
                    visible_inputs = [i for i in inputs if i.is_displayed() and not i.get_attribute("value")]
                    if visible_inputs:
                        qa_detected = True

                    if qa_detected:
                        print(f"⏭️ Skipping job due to Q/A: {job_url}")
                        send_telegram_message(f"❓ *Skipped Q/A job* for\n `{title}`\n🔗 [Job Link]({job_url})")
                        visited_jobs.add(job_url)
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        continue

                    # ✅ Applied
                    send_telegram_message(f"✅ *Applied on Naukri*\n🧑‍💼 `{title}`\n🔗 [Link]({job_url})")
                    visited_jobs.add(job_url)
                    applied_count += 1

                except Exception:
                    if allow_third_party_apply:
                        try:
                            external_link = driver.find_element(By.XPATH, "//a[contains(text(),'Apply')]").get_attribute("href")
                            if external_link:
                                driver.get(external_link)
                                time.sleep(3)
                                final_url = driver.current_url
                                send_telegram_message(f"📤 *3rd-party site apply* for `{title}`\n🔗 [Apply here]({final_url})")
                                visited_jobs.add(job_url)
                                applied_count += 1
                        except Exception as e:
                            send_telegram_message(f"❌ *Error on 3rd-party site* for `{title}`:\n{e}\n🔗 {job_url}")
                            visited_jobs.add(job_url)
                    else:
                        send_telegram_message(f"⏭️ Skipped 3rd-party job: `{title}`")
                        visited_jobs.add(job_url)

                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(2)

                if applied_count >= MAX_JOBS_PER_TITLE:
                    break

            except Exception as e:
                send_telegram_message(f"⚠️ Error applying `{title}`: {e}")
                visited_jobs.add(job_url)
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

        send_telegram_message(f"🎯 Finished  `{title}` on Naukri.\n *Applied jobs =* {applied_count}")

    send_remaining_external_tabs(driver)

    # Close all tabs
    while len(driver.window_handles) > 1:
        driver.switch_to.window(driver.window_handles[-1])
        driver.close()
    driver.switch_to.window(driver.window_handles[0])
    driver.quit()
    print("✅ Browser closed. Cycle complete.")

    # Save visited jobs
    save_visited_jobs(visited_jobs)

    return False



















def run_every_30_minutes():
    print("🚀 Starting job bot in persistent mode...")
    while True:
        driver = get_brave_driver()
        print("🔄 New job cycle started...")

        try:
            limit_reached = naukri_apply(driver)
            if limit_reached:
                send_telegram_message("🛑 *Stopped*: Daily limit reached on Naukri.")
                break
        except Exception as e:
            send_telegram_message(f"❌ *Critical error in cycle:*\n{str(e)}")
            try:
                driver.quit()
            except:
                pass

        for i in range(3600):
            mins = (3600 - i) // 60
            secs = (3600 - i) % 60
            print(f"⏳ Next run in: {mins:02d}:{secs:02d}", end="\r", flush=True)
            time.sleep(1)

if __name__ == "__main__":
    run_every_30_minutes()
