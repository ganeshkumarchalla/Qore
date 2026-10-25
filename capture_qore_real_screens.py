import os
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CAPTURES_DIR = r"c:\Users\ganes\OneDrive\QORE\website_captures"
os.makedirs(CAPTURES_DIR, exist_ok=True)

options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-gpu")
options.add_argument("--force-device-scale-factor=1")

driver = webdriver.Edge(options=options)
driver.set_window_size(1920, 1080)

try:
    print("Navigating to QORE on http://127.0.0.1:8000/...")
    driver.get("http://127.0.0.1:8000/")
    time.sleep(3)

    # 1. Main Home Screen
    path_home = os.path.join(CAPTURES_DIR, "01_qore_home.png")
    driver.save_screenshot(path_home)
    print("Saved:", path_home)

    # Check for Welcome modal / overlay and close it if present
    try:
        close_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Get Started') or contains(text(), 'Dismiss') or contains(text(), 'Skip') or contains(text(), 'Start')]")
        close_btn.click()
        time.sleep(1)
        print("Dismissed modal")
    except Exception as e:
        print("No modal to dismiss or already clear:", e)

    # 2. Look for openqasm/qaoa_cut.qasm in Explorer tree
    try:
        # Search for file element with qaoa_cut.qasm
        qaoa_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'qaoa_cut.qasm')]")
        qaoa_elem.click()
        time.sleep(2)
        print("Clicked on qaoa_cut.qasm")
    except Exception as e:
        print("Could not click qaoa_cut in DOM directly, setting via JS:", e)
        # Try finding via selector or trigger
        files = driver.find_elements(By.CLASS_NAME, "file-item")
        for f in files:
            if "qaoa" in f.text.lower():
                f.click()
                time.sleep(2)
                break

    # Save Studio with QAOA Cut
    path_studio = os.path.join(CAPTURES_DIR, "02_qaoa_cut_studio.png")
    driver.save_screenshot(path_studio)
    print("Saved:", path_studio)

    # Click Run Kernel / Simulate
    try:
        run_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Run') or contains(text(), 'Simulate')]")
        run_btn.click()
        time.sleep(3)
        print("Clicked Run/Simulate button")
    except Exception as e:
        print("Run button click error:", e)

    path_sim = os.path.join(CAPTURES_DIR, "03_qaoa_cut_simulated.png")
    driver.save_screenshot(path_sim)
    print("Saved:", path_sim)

    # Click Lab Tab
    try:
        lab_tab = driver.find_element(By.XPATH, "//*[contains(text(), 'Lab') or contains(@id, 'lab')]")
        lab_tab.click()
        time.sleep(2)
        print("Clicked Lab tab")
    except Exception as e:
        print("Lab tab click error:", e)

    path_lab = os.path.join(CAPTURES_DIR, "04_qaoa_cut_lab_results.png")
    driver.save_screenshot(path_lab)
    print("Saved:", path_lab)

    # Click Forge Tab
    try:
        forge_tab = driver.find_element(By.XPATH, "//*[contains(text(), 'Forge') or contains(@id, 'forge')]")
        forge_tab.click()
        time.sleep(2)
        print("Clicked Forge tab")
    except Exception as e:
        print("Forge tab click error:", e)

    path_forge = os.path.join(CAPTURES_DIR, "05_qaoa_cut_forge_transpiler.png")
    driver.save_screenshot(path_forge)
    print("Saved:", path_forge)

finally:
    driver.quit()
    print("Driver closed.")
